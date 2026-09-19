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

from core.archives import safe_archive_name


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
        use_base_manager=True,  # #570: a hiding default manager must not hide the Trash from a backup
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
                name = safe_archive_name(f"media/{file.relative_to(media_root).as_posix()}")
                if name is None:  # #453: never write a member that unzips outside media/
                    continue
                zf.write(file, name)
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


# ----------------------------------------------------------------------------- restore
# Restore (2026-09-07, #376): a backup zip is *staged* while Atlas runs and *applied* at the
# next launch, before the database is opened — the only moment the SQLite file and the media
# folder can be swapped safely. The previous data is kept next to it as `restore-backup-<ts>/`.
PENDING_NAME = "restore-pending.zip"
RESULT_NAME = "restore-result.json"
REQUIRED_ONE_OF = ("atlas.sqlite3", "database.json")


class RestoreError(ValueError):
    pass


def inspect_backup(path: Path) -> dict:
    """Validate a backup zip and return its manifest (+ what it carries)."""
    if not zipfile.is_zipfile(path):
        raise RestoreError("That file is not a zip archive.")
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if "MANIFEST.json" not in names:
            raise RestoreError("No MANIFEST.json inside — this is not an Atlas backup.")
        if not any(n in names for n in REQUIRED_ONE_OF):
            raise RestoreError("The backup holds neither atlas.sqlite3 nor database.json.")
        for name in names:
            if name.startswith("/") or ".." in Path(name).parts:
                raise RestoreError(f"Unsafe path inside the archive: {name}")
        try:
            manifest = json.loads(zf.read("MANIFEST.json"))
        except ValueError as exc:
            raise RestoreError("MANIFEST.json is not valid JSON.") from exc
        manifest["has_sqlite"] = "atlas.sqlite3" in names
        manifest["has_json"] = "database.json" in names
        manifest["media_files"] = sum(
            1 for n in names if n.startswith("media/") and not n.endswith("/")
        )
        manifest["size_bytes"] = path.stat().st_size
    return manifest


def _data_dir() -> Path:
    data_dir = getattr(settings, "DATA_DIR", None)
    return Path(data_dir) if data_dir else Path(settings.MEDIA_ROOT).parent


def stage_restore(uploaded, data_dir: Path | None = None) -> dict:
    """Save the uploaded zip as the pending restore (validated first)."""
    data_dir = data_dir or _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / PENDING_NAME
    tmp = target.with_suffix(".part")
    with open(tmp, "wb") as out:
        for chunk in (
            uploaded.chunks()
            if hasattr(uploaded, "chunks")
            else iter(lambda: uploaded.read(1 << 20), b"")
        ):
            out.write(chunk)
    try:
        manifest = inspect_backup(tmp)
    except RestoreError:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(target)
    manifest["staged_at"] = datetime.now(UTC).isoformat()
    (data_dir / "restore-pending.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def cancel_restore(data_dir: Path | None = None) -> bool:
    data_dir = data_dir or _data_dir()
    existed = (data_dir / PENDING_NAME).exists()
    (data_dir / PENDING_NAME).unlink(missing_ok=True)
    (data_dir / "restore-pending.json").unlink(missing_ok=True)
    return existed


def restore_status(data_dir: Path | None = None) -> dict:
    data_dir = data_dir or _data_dir()
    pending = None
    if (data_dir / PENDING_NAME).exists():
        try:
            pending = json.loads((data_dir / "restore-pending.json").read_text())
        except (OSError, ValueError):
            pending = {"staged_at": None}
    result = None
    if (data_dir / RESULT_NAME).exists():
        try:
            result = json.loads((data_dir / RESULT_NAME).read_text())
        except (OSError, ValueError):
            result = None
    return {"pending": pending, "last_result": result, "data_dir": str(data_dir)}


def apply_pending_restore(
    data_dir: Path | None = None, db_path: Path | None = None, media_root: Path | None = None
) -> dict | None:
    """Swap the database file and media folder for the staged backup's. Call BEFORE the
    database is opened (the desktop launcher does, right before `migrate`). Returns the
    result written to restore-result.json, or None when nothing was staged."""
    import shutil

    data_dir = data_dir or _data_dir()
    pending = data_dir / PENDING_NAME
    if not pending.exists():
        return None
    db_path = db_path or _sqlite_path()
    media_root = Path(media_root or settings.MEDIA_ROOT)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    keep = data_dir / f"restore-backup-{stamp}"
    result = {
        "applied_at": datetime.now(UTC).isoformat(),
        "kept_previous_in": str(keep),
        "ok": False,
        "detail": "",
    }
    try:
        manifest = inspect_backup(pending)
        keep.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(pending) as zf:
            if manifest["has_sqlite"] and db_path:
                # the previous database (and its WAL/journal) moves aside; the copy comes in
                for suffix in ("", "-wal", "-shm", "-journal"):
                    old = Path(str(db_path) + suffix)
                    if old.exists():
                        shutil.move(str(old), str(keep / old.name))
                with zf.open("atlas.sqlite3") as src, open(db_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                result["database"] = "sqlite file replaced"
            elif manifest["has_json"]:
                # no file to swap: leave database.json next to the result for `loaddata`
                (data_dir / "restore-database.json").write_bytes(zf.read("database.json"))
                result["database"] = (
                    "database.json extracted — run manage.py loaddata restore-database.json"
                )
            if media_root.exists():
                shutil.move(str(media_root), str(keep / "media"))
            media_root.mkdir(parents=True, exist_ok=True)
            count = 0
            for name in zf.namelist():
                if name.startswith("media/") and not name.endswith("/"):
                    target = media_root / Path(name).relative_to("media")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    count += 1
            result["media_files"] = count
        result["ok"] = True
        result["detail"] = f"Restored the backup from {manifest.get('created_at', 'unknown date')}."
    except Exception as exc:  # noqa: BLE001 - the launch must go on; the result says why
        result["detail"] = f"Restore failed: {exc}"
    finally:
        pending.unlink(missing_ok=True)
        (data_dir / "restore-pending.json").unlink(missing_ok=True)
        (data_dir / RESULT_NAME).write_text(json.dumps(result, indent=1))
    return result
