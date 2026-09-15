"""Backup destination (owner ask 2026-09-15, #536: "a drive or whatever cloud that can be
attached and the backup would go there").

Atlas keeps its snapshots in its own data folder (#462) — on the same disk as the data, which
is no protection against a lost laptop. A *destination* is a second folder the owner attaches:
an external drive, or the local folder of a sync service (Google Drive, Dropbox, OneDrive,
iCloud Drive, Nextcloud…), which carries the copy off the machine on its own. Every snapshot
written is copied there (under a temporary name, verified byte for byte, then renamed), the
copies rotate like the originals, and Diagnostics says whether the newest snapshot has landed.

Configuration lives in ``<data dir>/backup-destination.json`` next to the watched folder's;
the last copy and the last failure in ``backup-destination-state.json``. Nothing here talks
to the network: the sync service's own client does the uploading.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("atlas.destination")
CONFIG_NAME = "backup-destination.json"
STATE_NAME = "backup-destination-state.json"
SUBFOLDER = "Atlas backups"
KEEP = 14  # a sync folder has room for two weeks; the data folder keeps seven (#462)
CHUNK = 4 * 1024 * 1024

# what a path says about where it goes — first match wins, most specific first
KINDS: list[tuple[str, str, re.Pattern]] = [
    ("icloud", "iCloud Drive", re.compile(r"com~apple~CloudDocs|iCloud ?Drive", re.I)),
    ("google-drive", "Google Drive", re.compile(r"Google ?Drive|My Drive|Insync", re.I)),
    ("dropbox", "Dropbox", re.compile(r"Dropbox", re.I)),
    ("onedrive", "OneDrive", re.compile(r"OneDrive", re.I)),
    ("nextcloud", "Nextcloud", re.compile(r"Nextcloud|ownCloud", re.I)),
    ("syncthing", "Syncthing", re.compile(r"Syncthing|Sync\b", re.I)),
    ("proton", "Proton Drive", re.compile(r"Proton ?Drive", re.I)),
    ("box", "Box", re.compile(r"(^|[\\/])Box([\\/]|$)")),
]


def _data_dir() -> Path:
    from django.conf import settings

    data_dir = getattr(settings, "DATA_DIR", None)
    return Path(data_dir) if data_dir else Path(settings.MEDIA_ROOT) / "_atlas"


# --- what kind of place is this ------------------------------------------------------------


def _is_removable(path: Path) -> bool:
    """A mounted volume: /Volumes/…, /media/…, /mnt/…, /run/media/… or a Windows drive other
    than the system one."""
    text = str(path)
    if re.match(r"^(/Volumes/|/media/|/mnt/|/run/media/)", text):
        return True
    m = re.match(r"^([A-Za-z]):[\\/]", text)
    if m:
        system = os.environ.get("SystemDrive", "C:")[0].upper()
        return m.group(1).upper() != system
    return False


def describe(path: str | os.PathLike) -> dict:
    """{kind, label} for a folder: which sync service or drive it belongs to, from its path."""
    text = str(path)
    for kind, label, pattern in KINDS:
        if pattern.search(text):
            return {"kind": kind, "label": label}
    if _is_removable(Path(text)):
        return {"kind": "drive", "label": "Attached drive"}
    return {"kind": "folder", "label": "Folder"}


def suggestions(home: Path | None = None) -> list[dict]:
    """Sync folders and mounted drives that exist on this machine, so attaching one is a
    click. Only folders that are there right now; nothing is created."""
    home = home or Path.home()
    candidates: list[Path] = [
        home / "Google Drive",
        home / "Google Drive" / "My Drive",
        home / "GoogleDrive",
        home / "Dropbox",
        home / "OneDrive",
        home / "iCloud Drive",
        home / "Library" / "Mobile Documents" / "com~apple~CloudDocs",
        home / "Nextcloud",
        home / "Proton Drive",
        home / "Box",
        home / "Sync",
        home / "Insync",
    ]
    for pattern in ("OneDrive*", "Dropbox*", "Google Drive*", "iCloud*"):  # "OneDrive - Uni"
        try:
            candidates += sorted(p for p in home.glob(pattern) if p.is_dir())
        except OSError:
            pass
    cloud = home / "Library" / "CloudStorage"
    if cloud.is_dir():
        candidates += sorted(p for p in cloud.iterdir() if p.is_dir())
    for mounts in (
        Path("/Volumes"),
        Path("/media") / os.environ.get("USER", ""),
        Path("/mnt"),
        Path("/run/media") / os.environ.get("USER", ""),
    ):
        if mounts.is_dir():
            try:
                candidates += sorted(p for p in mounts.iterdir() if p.is_dir())
            except OSError:
                pass
    rows, seen = [], set()
    for p in candidates:
        try:
            if not p.is_dir():
                continue
            key = str(p.resolve())
        except OSError:
            continue
        if key in seen or p.name.startswith("."):
            continue
        seen.add(key)
        rows.append({"dir": str(p), **describe(p)})
    return rows


# --- configuration -------------------------------------------------------------------------


def load_config(data_dir: Path | None = None) -> dict:
    path = (data_dir or _data_dir()) / CONFIG_NAME
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        raw = {}
    directory = str(raw.get("dir") or "")
    return {"dir": directory, "enabled": bool(raw.get("enabled")) and bool(directory)}


def save_config(dir_path: str, enabled: bool = True, data_dir: Path | None = None) -> dict:
    """Validate and persist. The folder must exist and be writable; an empty folder detaches."""
    dir_path = (dir_path or "").strip()
    if dir_path:
        folder = Path(dir_path).expanduser()
        if not folder.is_dir():
            raise ValueError(f"{dir_path} is not a folder that exists.")
        probe = folder / ".atlas-write-check"
        try:
            probe.write_text("ok")
            probe.unlink()
        except OSError as exc:
            raise ValueError(
                f"Atlas cannot write into {dir_path} ({exc.__class__.__name__})."
            ) from exc
        dir_path = str(folder)
    data_dir = data_dir or _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    config = {"dir": dir_path, "enabled": bool(enabled and dir_path)}
    (data_dir / CONFIG_NAME).write_text(json.dumps(config, indent=1))
    return config


def _load_state(data_dir: Path) -> dict:
    try:
        return json.loads((data_dir / STATE_NAME).read_text())
    except (OSError, ValueError):
        return {}


def _save_state(data_dir: Path, **changes) -> dict:
    state = {**_load_state(data_dir), **changes}
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / STATE_NAME).write_text(json.dumps(state, indent=1))
    return state


# --- copying ---------------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def target_dir(config: dict | None = None, data_dir: Path | None = None) -> Path | None:
    config = config or load_config(data_dir)
    if not config["enabled"]:
        return None
    return Path(config["dir"]) / SUBFOLDER


def list_copies(directory: Path) -> list[dict]:
    from core.snapshots import PREFIX

    if not directory.is_dir():
        return []
    rows = []
    for path in directory.glob(f"{PREFIX}*.zip"):
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "mtime": stat.st_mtime,
            }
        )
    rows.sort(key=lambda r: (r["mtime"], r["name"]), reverse=True)
    return rows


def prune_copies(directory: Path, keep: int | None = None) -> list[str]:
    keep = KEEP if keep is None else keep
    removed = []
    for row in list_copies(directory)[keep:]:
        try:
            Path(row["path"]).unlink()
            removed.append(row["name"])
        except OSError:
            log.warning("could not remove old copy %s", row["path"])
    return removed


def copy_snapshot(
    source: Path, data_dir: Path | None = None, keep: int | None = None
) -> dict | None:
    """Copy one snapshot into the destination (temporary name, verified, renamed), rotate the
    copies, remember the outcome. Returns the record, or None when no destination is attached.
    Raises OSError / ValueError on failure — callers that must not fail wrap it in `mirror`."""
    data_dir = data_dir or _data_dir()
    config = load_config(data_dir)
    folder = target_dir(config, data_dir)
    if folder is None:
        return None
    source = Path(source)
    root = Path(config["dir"])
    if not root.is_dir():  # never recreate an unplugged drive's path on the boot disk
        raise OSError(f"{root} is not reachable — unplugged, or the sync client is not running")
    folder.mkdir(exist_ok=True)
    final = folder / source.name
    partial = folder / (source.name + ".partial")
    try:
        shutil.copyfile(source, partial)
        if partial.stat().st_size != source.stat().st_size or _sha256(partial) != _sha256(source):
            raise ValueError(
                "the copy does not match the snapshot (the drive may be full or flaky)"
            )
        os.replace(partial, final)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    removed = prune_copies(folder, keep)
    record = {
        "name": final.name,
        "path": str(final),
        "size_bytes": final.stat().st_size,
        "at": datetime.now(UTC).isoformat(),
        "verified": True,
        "removed": removed,
    }
    _save_state(data_dir, last_copy=record, last_error=None)
    log.info(
        "Snapshot copied to %s (%d bytes); removed %s",
        final,
        record["size_bytes"],
        removed or "none",
    )
    return record


def mirror(source: Path, data_dir: Path | None = None) -> dict | None:
    """`copy_snapshot` that never raises: a failed copy is recorded for Diagnostics and logged,
    because the local snapshot already exists and must count as written."""
    data_dir = data_dir or _data_dir()
    try:
        return copy_snapshot(source, data_dir)
    except Exception as exc:  # noqa: BLE001 - surfaced on Diagnostics
        _save_state(
            data_dir, last_error={"at": datetime.now(UTC).isoformat(), "detail": str(exc)[:500]}
        )
        log.exception("Copy to the backup destination failed")
        return None


def sync_now(data_dir: Path | None = None) -> dict:
    """Copy the newest local snapshot unless it is already there. Returns {copied, name}."""
    from core.snapshots import last_snapshot

    data_dir = data_dir or _data_dir()
    folder = target_dir(data_dir=data_dir)
    if folder is None:
        raise ValueError("No backup destination is attached.")
    newest = last_snapshot()
    if newest is None:
        return {"copied": False, "name": None, "detail": "no snapshot to copy yet"}
    existing = folder / newest["name"]
    if existing.exists() and existing.stat().st_size == newest["size_bytes"]:
        return {"copied": False, "name": newest["name"], "detail": "already there"}
    record = copy_snapshot(Path(newest["path"]), data_dir)
    return {"copied": True, "name": newest["name"], "detail": "copied", "record": record}


# --- status ----------------------------------------------------------------------------------


def _free_bytes(path: Path) -> int | None:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def destination_status(data_dir: Path | None = None, with_suggestions: bool = False) -> dict:
    """What Diagnostics shows: the folder and its kind, whether it is reachable right now (a
    drive may be unplugged), the copies there, whether the newest snapshot has landed, the
    last failure — and, when asked, the sync folders and drives found on this machine."""
    from core.snapshots import last_snapshot

    data_dir = data_dir or _data_dir()
    config = load_config(data_dir)
    state = _load_state(data_dir)
    out: dict = {
        "dir": config["dir"],
        "enabled": config["enabled"],
        "kind": None,
        "label": None,
        "subfolder": SUBFOLDER,
        "reachable": False,
        "free_bytes": None,
        "keep": KEEP,
        "copies": 0,
        "total_bytes": 0,
        "newest_copy": None,
        "in_sync": None,
        "last_copy": state.get("last_copy"),
        "last_error": state.get("last_error"),
    }
    if config["dir"]:
        out.update(describe(config["dir"]))
        root = Path(config["dir"])
        out["reachable"] = root.is_dir()
        if out["reachable"]:
            out["free_bytes"] = _free_bytes(root)
            copies = list_copies(root / SUBFOLDER)
            out["copies"] = len(copies)
            out["total_bytes"] = sum(c["size_bytes"] for c in copies)
            if copies:
                out["newest_copy"] = {k: copies[0][k] for k in ("name", "path", "size_bytes")}
            newest = last_snapshot()  # None → nothing to compare yet → in_sync stays None
            if newest:
                out["in_sync"] = any(
                    c["name"] == newest["name"] and c["size_bytes"] == newest["size_bytes"]
                    for c in copies
                )
    if with_suggestions:
        out["suggestions"] = suggestions()
    return out
