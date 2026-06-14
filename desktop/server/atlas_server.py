"""Frozen entrypoint for the bundled Atlas server (#210d).

PyInstaller packages this into a standalone executable that the Tauri desktop app spawns
on launch. It runs the same `run_desktop` command under the SQLite desktop settings, so the
app needs no Python, Postgres, Redis, or Docker on the user's machine.
"""

import os
import sys
from pathlib import Path


def _log_to_data_dir():
    """Send the frozen server's stdout/stderr to <data-dir>/atlas-server.log.

    The Tauri shell launches this with no console (windowed build), so otherwise a startup
    failure — a Postgres error, a bad migration, any traceback — is invisible and the window
    just shows "127.0.0.1 refused to connect". Logging to the per-user data dir gives the
    owner (and us) a file to read. It also means a stray print() can't crash on a None stdout.
    """
    data_dir = Path(os.environ.get("ATLAS_DATA_DIR") or (Path.home() / ".atlas"))
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        stream = open(data_dir / "atlas-server.log", "a", buffering=1, encoding="utf-8")
        sys.stdout = stream
        sys.stderr = stream
    except OSError:
        pass  # never let logging setup block startup


def main():
    _log_to_data_dir()
    # base.py reads these at import time; set defaults before Django loads so the frozen
    # binary doesn't depend on a .env file (the desktop settings override the rest).
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.desktop")
    os.environ.setdefault("DEBUG", "False")
    os.environ.setdefault("ATLAS_API_KEY", "")

    import django

    django.setup()
    from django.core.management import call_command

    call_command("run_desktop", *sys.argv[1:])


if __name__ == "__main__":
    main()
