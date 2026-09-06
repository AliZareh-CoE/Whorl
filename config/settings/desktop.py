"""Self-contained desktop settings (#210, owner: "one click install … and it just works").

The desktop app shouldn't need Docker, Postgres, or Redis. This settings module runs Atlas
against a SQLite database in a per-user data directory, with background jobs in immediate
(in-process) mode and static files served by WhiteNoise — exactly what the bundled Tauri
sidecar launches. Nothing here touches the dev/prod (Postgres) settings.

    ATLAS_DATA_DIR   where the SQLite db, media, and secret live (default: ~/.atlas)
"""

import os
import secrets
from pathlib import Path

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Per-user writable home for the db, uploaded files, and a stable secret key. The Tauri
# shell sets ATLAS_DATA_DIR to the OS app-data path; standalone runs fall back to ~/.atlas.
DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", str(Path.home() / ".atlas")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# A persisted secret so sessions/CSRF survive restarts (a fresh random one would log you out).
_secret_file = DATA_DIR / "secret_key"
if not _secret_file.exists():
    _secret_file.write_text(secrets.token_urlsafe(64))
SECRET_KEY = _secret_file.read_text().strip()

# A persisted API key so Claude Code (via the bundled atlas-mcp) and any other API client can
# talk to the installed app. Minted once on first launch; an explicit ATLAS_API_KEY still wins.
# The frozen `atlas-mcp` reads this same file, so registering Atlas in Claude Code needs no
# copying of secrets (see core/mcp_connect.py + the "Connect Claude Code" page).
_api_key_file = DATA_DIR / "api_key"
if not os.environ.get("ATLAS_API_KEY"):
    if not _api_key_file.exists():
        _api_key_file.write_text(secrets.token_urlsafe(32))
    ATLAS_API_KEY = _api_key_file.read_text().strip()

# SQLite — a single file in the data dir, no server (#266). After a multi-day saga bundling a
# full PostgreSQL server into the Windows installer (initdb exit-1, missing client tools, a
# console crash loop, a psycopg connect hang, a pg_ctl pipe-inheritance hang…), the owner and I
# went with what every other single-user desktop app uses: SQLite. It opens in milliseconds,
# needs no initdb/process/connection step, and retires the entire Postgres-on-Windows problem
# class. Postgres-only features degrade gracefully: trigram GinIndexes are skipped on SQLite
# (PostgresAddIndex) and global search falls back to icontains (core/search.py). The web/server
# deployment keeps Postgres unchanged — only this desktop settings module changed.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(DATA_DIR / "atlas.sqlite3"),
        # WAL + a busy timeout keep the single-user app responsive and crash-tolerant.
        "OPTIONS": {"timeout": 20, "init_command": "PRAGMA journal_mode=WAL;"},
    }
}

MEDIA_ROOT = DATA_DIR / "media"
STATIC_ROOT = DATA_DIR / "staticfiles"
# WhiteNoise (already in MIDDLEWARE) serves the collected static files directly from the app.
# Use the PLAIN storage (not CompressedManifest): on a localhost desktop, per-file gzip+brotli
# compression and hashing are pointless work that made the first-launch collectstatic take
# minutes on Windows (the window timed out waiting). Plain storage just copies the files — fast
# — and WhiteNoise still serves them. (#246)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# No Redis in a single-user desktop build: run background jobs in-process, immediately.
HUEY = {"huey_class": "huey.MemoryHuey", "name": "atlas", "immediate": True}

# A local desktop app talks only to itself; keep CSRF/sessions sane for 127.0.0.1. The port
# follows ATLAS_PORT because the shell steps aside to a free port when 8000 is already taken.
_port = os.environ.get("ATLAS_PORT", "8000")
CSRF_TRUSTED_ORIGINS = [f"http://127.0.0.1:{_port}", f"http://localhost:{_port}"]

# Templates and the doctor use this to speak to a desktop user (first-run login hint).
ATLAS_DESKTOP = True
