"""The self-contained desktop build (#210) stays well-formed.

The bundled desktop app runs Atlas with a bundled, auto-started Postgres (owner's choice —
full parity incl. full-text search) in a per-user data dir, huey immediate, WhiteNoise
static. The full initdb→migrate→serve flow needs a non-root user + the postgres binaries, so
it's exercised live in the desktop-release CI (and was verified by hand); here we guard the
pieces that are checkable anywhere: `manage.py check` loads the settings, they select
Postgres, the binary resolver honours ATLAS_PG_BIN, and run_desktop starts Postgres first.
"""

import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings

BASE_DIR = Path(settings.BASE_DIR)


def test_desktop_check_passes(tmp_path):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "ATLAS_DATA_DIR": str(tmp_path),
        "DEBUG": "False",
        "SECRET_KEY": "test-secret",
        "ATLAS_API_KEY": "test-key",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--settings=config.settings.desktop"],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert (tmp_path / "secret_key").exists()  # persisted so sessions survive restarts


def test_desktop_settings_use_bundled_postgres():
    text = (BASE_DIR / "config" / "settings" / "desktop.py").read_text()
    assert "django.db.backends.postgresql" in text
    assert "ATLAS_PG_PORT" in text
    assert "MemoryHuey" in text  # no Redis — jobs run in-process


def test_pg_bin_resolves_from_env(tmp_path, monkeypatch):
    from core.desktop_runtime import _pg_bin

    fake = tmp_path / "initdb"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv("ATLAS_PG_BIN", str(tmp_path))
    assert _pg_bin("initdb") == str(fake)


def test_pg_bin_resolves_when_env_points_at_pg_root(tmp_path, monkeypatch):
    # ATLAS_PG_BIN may be the pg root (zonky layout), with binaries under bin/ (#210 fix).
    from core.desktop_runtime import _pg_bin

    (tmp_path / "bin").mkdir()
    fake = tmp_path / "bin" / "initdb"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv("ATLAS_PG_BIN", str(tmp_path))
    assert _pg_bin("initdb") == str(fake)


def test_pg_bin_handles_exe_suffix(tmp_path, monkeypatch):
    # the Windows crash: binaries are initdb.exe; the lookup must find them (#210 fix).
    from core.desktop_runtime import _pg_bin

    fake = tmp_path / "initdb.exe"
    fake.write_text("")
    monkeypatch.setenv("ATLAS_PG_BIN", str(tmp_path))
    assert _pg_bin("initdb") == str(fake)


def test_run_desktop_starts_postgres_first():
    text = (BASE_DIR / "core" / "management" / "commands" / "run_desktop.py").read_text()
    assert "ensure_postgres" in text
    runtime = (BASE_DIR / "core" / "desktop_runtime.py").read_text()
    assert "initdb" in runtime and "pg_ctl" in runtime and "atexit" in runtime


def test_postgres_skips_unix_socket_on_windows():
    # the Windows "127.0.0.1 refused to connect" fix: the unix-socket `-k` token must only be
    # passed on POSIX (it breaks pg_ctl start on Windows / paths with spaces); TCP loopback
    # is used everywhere. A start failure must also surface postgres.log, not exit blank.
    runtime = (BASE_DIR / "core" / "desktop_runtime.py").read_text()
    assert 'os.name != "nt"' in runtime
    assert "listen_addresses=127.0.0.1" in runtime
    assert "postgres.log" in runtime and "RuntimeError" in runtime


def test_frozen_server_logs_to_data_dir():
    # so a startup crash isn't invisible behind the windowed (no-console) build.
    entry = (BASE_DIR / "desktop" / "server" / "atlas_server.py").read_text()
    assert "atlas-server.log" in entry and "ATLAS_DATA_DIR" in entry


def test_pyinstaller_freeze_scaffold_present():
    # #210d: the frozen-server entrypoint + spec exist and target the desktop settings.
    server = BASE_DIR / "desktop" / "server"
    entry = (server / "atlas_server.py").read_text()
    spec = (server / "atlas_server.spec").read_text()
    assert "config.settings.desktop" in entry
    assert "run_desktop" in entry
    assert "templates" in spec and "static" in spec  # bundled at the frozen root
    assert "atlas-server" in spec  # the executable name the Tauri sidecar spawns
