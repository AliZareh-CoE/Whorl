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

# Full Postgres, bundled + auto-started by the app (owner choice, #210g): exact parity
# with the server (incl. full-text search). The desktop runtime runs initdb into the data
# dir and starts a local postgres before Django connects; trust auth on 127.0.0.1 only.
PG_PORT = int(os.environ.get("ATLAS_PG_PORT", "5433"))
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "atlas",
        "USER": "atlas",
        "PASSWORD": "",
        "HOST": "127.0.0.1",
        "PORT": str(PG_PORT),
    }
}

MEDIA_ROOT = DATA_DIR / "media"
STATIC_ROOT = DATA_DIR / "staticfiles"
# WhiteNoise (already in MIDDLEWARE) serves the collected static files directly from the app.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# No Redis in a single-user desktop build: run background jobs in-process, immediately.
HUEY = {"huey_class": "huey.MemoryHuey", "name": "atlas", "immediate": True}

# A local desktop app talks only to itself; keep CSRF/sessions sane for 127.0.0.1.
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]
