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


def test_desktop_settings_use_sqlite():
    # #266: the desktop app uses SQLite (a file — no server), which retired the whole
    # bundled-Postgres-on-Windows saga. Postgres stays on the web/server deployment only.
    text = (BASE_DIR / "config" / "settings" / "desktop.py").read_text()
    assert "django.db.backends.sqlite3" in text
    assert "atlas.sqlite3" in text
    assert "django.db.backends.postgresql" not in text
    assert "MemoryHuey" in text  # no Redis — jobs run in-process


def test_desktop_static_storage_is_plain_for_fast_first_run():
    # #246: CompressedManifest gzip+brotli+hashes every file → minutes-long first-run
    # collectstatic on Windows (the window timed out). Localhost doesn't need any of that.
    text = (BASE_DIR / "config" / "settings" / "desktop.py").read_text()
    assert "django.contrib.staticfiles.storage.StaticFilesStorage" in text
    assert "CompressedManifestStaticFilesStorage" not in text


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


def test_run_desktop_uses_sqlite_no_postgres_step():
    # #266: SQLite needs no server — run_desktop goes straight to migrate (which creates the
    # file). The old ensure_postgres bring-up step is gone (it never started reliably on Windows).
    text = (BASE_DIR / "core" / "management" / "commands" / "run_desktop.py").read_text()
    assert "ensure_postgres" not in text
    assert "migrate" in text and "collectstatic" in text and "waitress" in text


def test_trigram_indexes_are_postgres_only():
    # #266: GinIndex (gin_trgm_ops) is Postgres-only; PostgresAddIndex creates it on Postgres
    # and no-ops on SQLite, so one migration set applies to both backends.
    ops = (BASE_DIR / "core" / "migration_ops.py").read_text()
    assert "PostgresAddIndex" in ops and 'vendor != "postgresql"' in ops
    for mig in (
        "documents/migrations/0002_document_document_title_trgm.py",
        "notes/migrations/0003_note_note_title_trgm.py",
        "literature/migrations/0004_reference_reference_title_trgm.py",
        "projects/migrations/0002_decisionrecord_decision_title_trgm_and_more.py",
    ):
        assert "PostgresAddIndex" in (BASE_DIR / mig).read_text(), mig


def test_run_desktop_logs_progress_and_skips_static_recollect():
    # #241: setup runs at verbosity=1 (no silent black box) and skips the slow static
    # re-collect on repeat launches of the same build, keyed on ATLAS_VERSION.
    text = (BASE_DIR / "core" / "management" / "commands" / "run_desktop.py").read_text()
    assert "verbosity=1" in text
    assert "ATLAS_VERSION" in text and ".collected_version" in text


def test_postgres_skips_unix_socket_on_windows():
    # the Windows "127.0.0.1 refused to connect" fix: the unix-socket `-k` token must only be
    # passed on POSIX (it breaks pg_ctl start on Windows / paths with spaces); TCP loopback
    # is used everywhere. A start failure must also surface postgres.log, not exit blank.
    runtime = (BASE_DIR / "core" / "desktop_runtime.py").read_text()
    assert 'os.name != "nt"' in runtime
    assert "listen_addresses=127.0.0.1" in runtime
    assert "postgres.log" in runtime and "RuntimeError" in runtime


def test_postgres_isolated_from_console_signals():
    # #245: the 0xC000013A crash loop — a console event Ctrl+C'd Postgres's workers because the
    # server ran in a console that Postgres shared. The frozen server is now windowed, and the
    # pg helpers start in their own process group with no console window. #248: the windowed
    # build has no valid stdin, so the helpers are given an explicit DEVNULL stdin or they can
    # fail to spawn on Windows.
    spec = (BASE_DIR / "desktop" / "server" / "atlas_server.spec").read_text()
    assert "console=False" in spec
    runtime = (BASE_DIR / "core" / "desktop_runtime.py").read_text()
    assert "_CREATIONFLAGS" in runtime and 'os.name == "nt"' in runtime
    assert "stdin" in runtime and "DEVNULL" in runtime


def test_setup_cannot_hang_forever():
    # #244: a wedged initdb/pg_ctl or a stuck query must time out (surfacing an error in the
    # log) instead of leaving the desktop window black forever.
    runtime = (BASE_DIR / "core" / "desktop_runtime.py").read_text()
    assert 'setdefault("timeout"' in runtime  # bounded subprocess
    assert "statement_timeout" in runtime  # bounded psycopg queries
    assert "timed out" in runtime


def test_run_surfaces_stderr_on_failure():
    # the windowed build has no console, so a failing Postgres helper must raise WITH its
    # stderr (e.g. initdb's real complaint), not a bare exit code (#224 follow-up).
    import pytest

    from core.desktop_runtime import _run

    with pytest.raises(RuntimeError) as exc:
        _run(["sh", "-c", "echo boom-message 1>&2; exit 1"])
    assert "boom-message" in str(exc.value)


def test_plain_strips_extended_length_prefix():
    # Tauri hands us \\?\C:\... ; initdb mis-resolves its share/ dir from that, so we strip it.
    from core.desktop_runtime import _plain

    assert _plain("\\\\?\\C:\\pg\\bin\\initdb.exe") == "C:\\pg\\bin\\initdb.exe"
    assert _plain("/usr/lib/postgresql/16/bin/initdb") == "/usr/lib/postgresql/16/bin/initdb"


def test_initdb_clears_partial_pgdata():
    # a half-built pgdata from a prior failed launch (no PG_VERSION) is wiped so initdb's
    # "directory not empty" can't make every retry fail.
    runtime = (BASE_DIR / "core" / "desktop_runtime.py").read_text()
    assert "rmtree" in runtime and "PG_VERSION" in runtime


def test_postgres_provisioning_uses_psycopg_not_client_tools():
    # #231: the Windows Postgres bundle ships ONLY initdb/pg_ctl/postgres — not the
    # pg_isready/psql/createdb client tools — so the readiness wait and database creation must
    # go through psycopg (already in the frozen server), never shell out to those binaries.
    runtime = (BASE_DIR / "core" / "desktop_runtime.py").read_text()
    assert "import psycopg" in runtime
    assert "CREATE DATABASE" in runtime
    for missing in ("pg_isready", "psql", "createdb"):
        assert f'_pg_bin("{missing}")' not in runtime, (
            f"must not invoke {missing} (absent on Windows)"
        )


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


def test_ensure_postgres_logs_each_step_and_bounds_the_wait():
    # #265: ensure_postgres was silent, so a hang after Postgres started left atlas-server.log
    # empty and us debugging blind. It now flushes a progress line at every step and waits for
    # the DB with a reliably-bounded raw TCP socket + a thread-timeout around psycopg, so a
    # wedged connect surfaces an error instead of hanging the launch with no output.
    runtime = (BASE_DIR / "core" / "desktop_runtime.py").read_text()
    assert "_log(" in runtime and "flush=True" in runtime
    assert "_wait_for_tcp" in runtime and "settimeout" in runtime
    assert "ThreadPoolExecutor" in runtime and "FuturesTimeout" in runtime
    # the bounded connect must not block on a hung thread when it gives up
    assert "shutdown(wait=False)" in runtime


def test_run_desktop_cleans_up_old_postgres_data():
    # #266 upgrade path: switching a machine from the bundled-Postgres build to SQLite should
    # drop the now-unused pgdata/ + postgres.log so the data dir is clean (no manual wipe).
    text = (BASE_DIR / "core" / "management" / "commands" / "run_desktop.py").read_text()
    assert "pgdata" in text and "rmtree" in text and "postgres.log" in text
