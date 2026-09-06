"""The self-contained desktop build (#210, #266) stays well-formed.

The bundled desktop app runs Atlas on a per-user SQLite file (no database server), huey
immediate, WhiteNoise static. Here we guard everything checkable without the frozen binary:
`manage.py check` loads the settings, `run_desktop --setup-only` really provisions a fresh
data dir (migrate on SQLite + static + the login), the port follows ATLAS_PORT, and the old
bundled-Postgres path stays gone.
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


def test_run_desktop_uses_sqlite_no_postgres_step():
    # #266: SQLite needs no server — run_desktop goes straight to migrate (which creates the
    # file). The old ensure_postgres bring-up step is gone (it never started reliably on Windows).
    text = (BASE_DIR / "core" / "management" / "commands" / "run_desktop.py").read_text()
    assert "ensure_postgres" not in text
    assert "migrate" in text and "collectstatic" in text and "waitress" in text


def test_bundled_postgres_runtime_is_gone():
    # The bundled-Postgres lifecycle module and every place that shipped or configured it were
    # removed with the SQLite switch: no dead code, no 50MB of unused binaries per installer,
    # no Postgres advice on the failure page.
    assert not (BASE_DIR / "core" / "desktop_runtime.py").exists()
    assert not (BASE_DIR / "desktop" / "resources" / "pg").exists()
    wf = (BASE_DIR / ".github" / "workflows" / "desktop-release.yml").read_text()
    assert "embedded-postgres-binaries" not in wf and "desktop_runtime" not in wf
    for rel in ("desktop/src/main.rs", "desktop/src/server.rs", "desktop/installer-hooks.nsh"):
        text = (BASE_DIR / rel).read_text()
        assert "ATLAS_PG_BIN" not in text and "postgres.exe" not in text, rel
        assert "postgres.log" not in text and "MSVCR120" not in text, rel


def _desktop_env(tmp_path, **extra):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "ATLAS_DATA_DIR": str(tmp_path),
        "DEBUG": "False",
        "ATLAS_API_KEY": "test-key",
    }
    env.update(extra)
    return env


def test_run_desktop_setup_provisions_a_fresh_data_dir(tmp_path):
    # The real first-launch path the frozen binary runs, end to end on SQLite: migrate creates
    # the database file, static assets are collected (and version-marked), and the single login
    # exists — all inside ATLAS_DATA_DIR, nothing on the machine touched.
    result = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "run_desktop",
            "--setup-only",
            "--settings=config.settings.desktop",
        ],
        cwd=BASE_DIR,
        env=_desktop_env(tmp_path, ATLAS_VERSION="test-build", ATLAS_ADMIN_PASSWORD="pw"),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert (tmp_path / "atlas.sqlite3").exists()
    assert (tmp_path / "staticfiles" / ".collected_version").read_text() == "test-build"
    assert (tmp_path / "staticfiles" / "js").is_dir()
    assert "Created the Atlas login 'atlas'" in result.stdout
    assert "Setup complete." in result.stdout


def test_desktop_csrf_origins_follow_the_chosen_port(tmp_path):
    # The shell steps aside to a free port when 8000 is taken (choose_port in server.rs), so the
    # trusted origins must be built from ATLAS_PORT or every POST would fail the CSRF check.
    code = (
        "import os, django; django.setup(); from django.conf import settings; "
        "print(','.join(settings.CSRF_TRUSTED_ORIGINS))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BASE_DIR,
        env=_desktop_env(
            tmp_path, ATLAS_PORT="8123", DJANGO_SETTINGS_MODULE="config.settings.desktop"
        ),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "http://127.0.0.1:8123,http://localhost:8123"


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


def test_frozen_server_is_windowed():
    # #245: the frozen server runs without a console window — no black box on Windows; its
    # output goes to atlas-server.log instead.
    spec = (BASE_DIR / "desktop" / "server" / "atlas_server.spec").read_text()
    assert "console=False" in spec


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


def test_run_desktop_cleans_up_old_postgres_data():
    # #266 upgrade path: switching a machine from the bundled-Postgres build to SQLite should
    # drop the now-unused pgdata/ + postgres.log so the data dir is clean (no manual wipe).
    text = (BASE_DIR / "core" / "management" / "commands" / "run_desktop.py").read_text()
    assert "pgdata" in text and "rmtree" in text and "postgres.log" in text
