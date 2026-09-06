"""One-file backup (2026-09-06): everything Atlas knows, as a zip you can keep anywhere.

SQLite installs (the desktop) get a consistent copy of the database through sqlite's online
backup API plus the media folder; other databases get a JSON dump (`dumpdata`) plus media.
Restoring is documented in README › Backups: stop the app, put the files back, start it.
"""

from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings


def _sqlite_path() -> Path | None:
    db = settings.DATABASES["default"]
    if "sqlite" in db.get("ENGINE", "") and db.get("NAME") not in (None, "", ":memory:"):
        return Path(str(db["NAME"]))
    return None


def _dump_sqlite(path: Path) -> bytes:
    """A transactionally consistent copy, even while the app is writing."""
    source = sqlite3.connect(str(path))
    try:
        target = sqlite3.connect(":memory:")
        source.backup(target)
        return b"".join(f"{line}\n".encode() for line in target.iterdump())
    finally:
        source.close()


def _dump_json() -> bytes:
    from django.core.management import call_command

    out = io.StringIO()
    call_command(
        "dumpdata",
        natural_foreign=True,
        natural_primary=True,
        exclude=["contenttypes", "auth.permission", "sessions", "admin.logentry"],
        indent=1,
        stdout=out,
    )
    return out.getvalue().encode()


def build_backup(stream) -> dict:
    """Write the zip into ``stream``; return a small manifest (also stored in the zip)."""
    now = datetime.now(UTC)
    media_root = Path(settings.MEDIA_ROOT)
    manifest = {
        "created_at": now.isoformat(),
        "version": __import__("os").environ.get("ATLAS_VERSION", "dev"),
        "database": "sqlite" if _sqlite_path() else "json",
        "media_files": 0,
    }
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        sqlite_path = _sqlite_path()
        if sqlite_path and sqlite_path.exists():
            zf.writestr("database.sql", _dump_sqlite(sqlite_path))
            # a byte-exact copy too, for a copy-the-file-back restore
            zf.writestr("atlas.sqlite3", _sqlite_bytes(sqlite_path))
        else:
            zf.writestr("database.json", _dump_json())
        if media_root.exists():
            for file in sorted(p for p in media_root.rglob("*") if p.is_file()):
                zf.write(file, f"media/{file.relative_to(media_root).as_posix()}")
                manifest["media_files"] += 1
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=1))
        zf.writestr(
            "README.txt",
            "Atlas backup.\n\nRestore: quit Atlas, copy atlas.sqlite3 (desktop) over the one in "
            "the data folder (Diagnostics shows the path) and the media/ folder next to it, "
            "then start Atlas. A server install loads database.json with "
            "`manage.py loaddata database.json`.\n",
        )
    return manifest


def _sqlite_bytes(path: Path) -> bytes:
    """A byte-exact, consistent copy of the database file (for copy-it-back restores)."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as handle:
        tmp_path = Path(handle.name)
    try:
        src = sqlite3.connect(str(path))
        dst = sqlite3.connect(str(tmp_path))
        src.backup(dst)
        dst.close()
        src.close()
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
