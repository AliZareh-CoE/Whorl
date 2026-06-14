"""The self-contained desktop settings (#210) stay loadable + SQLite-backed.

The bundled desktop app runs Atlas with no Postgres/Redis — SQLite in a per-user data dir,
huey immediate, WhiteNoise static. This guards that `manage.py check` passes under those
settings (catches a Postgres-only setting sneaking into the desktop path) and that the
schema actually migrates onto SQLite.
"""

import subprocess
import sys
from pathlib import Path

from django.conf import settings

BASE_DIR = Path(settings.BASE_DIR)


def _run(args, data_dir):
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "ATLAS_DATA_DIR": str(data_dir),
        "DEBUG": "False",
        "SECRET_KEY": "test-secret",
        "ATLAS_API_KEY": "test-key",
    }
    return subprocess.run(
        [sys.executable, "manage.py", *args, "--settings=config.settings.desktop"],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_desktop_check_passes(tmp_path):
    result = _run(["check"], tmp_path)
    assert result.returncode == 0, result.stderr or result.stdout


def test_desktop_migrates_onto_sqlite(tmp_path):
    result = _run(["migrate", "--no-input"], tmp_path)
    assert result.returncode == 0, result.stderr or result.stdout
    assert (tmp_path / "atlas.sqlite3").exists()
    assert (tmp_path / "secret_key").exists()  # persisted so sessions survive restarts


def test_run_desktop_setup_prepares_db_static_and_login(tmp_path):
    # #210c: the bundled entrypoint migrates, collects static, and creates the single login.
    result = _run(["run_desktop", "--setup-only"], tmp_path)
    assert result.returncode == 0, result.stderr or result.stdout
    assert (tmp_path / "atlas.sqlite3").exists()
    assert (tmp_path / "staticfiles" / "staticfiles.json").exists()  # WhiteNoise manifest
    assert "Created the Atlas login" in result.stdout
