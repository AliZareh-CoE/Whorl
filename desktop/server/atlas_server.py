"""Frozen entrypoint for the bundled Atlas server (#210d).

PyInstaller packages this into a standalone executable that the Tauri desktop app spawns
on launch. It runs the same `run_desktop` command under the SQLite desktop settings, so the
app needs no Python, Postgres, Redis, or Docker on the user's machine.
"""

import os
import sys


def main():
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
