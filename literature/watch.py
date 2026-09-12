"""Watched folder (2026-09-07, #406): drop a PDF into one folder on disk and it lands in the
library. A daemon thread scans the folder every few seconds while watching is enabled; every
file is imported once (a ledger of path + size + mtime), through the same pipeline as a
drag-drop import (DOI read off page one, metadata fetched, a stub when there is none).

Configuration lives in <data dir>/watch.json so it survives restarts; the desktop launcher
starts the watcher on boot when it is enabled.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("atlas.watch")
CONFIG_NAME = "watch.json"
LEDGER_NAME = "watch-seen.json"
INTERVAL_SECONDS = 15
MAX_PER_SCAN = 25
_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_STOP = threading.Event()
_STATE: dict = {
    "running": False,
    "last_scan": None,
    "last_result": None,
    "last_import": None,
    "error": "",
}


def _data_dir() -> Path:
    """The desktop's data dir; a dev/server install keeps the two small files under MEDIA_ROOT
    (gitignored) rather than beside the code."""
    from django.conf import settings

    data_dir = getattr(settings, "DATA_DIR", None)
    return Path(data_dir) if data_dir else Path(settings.MEDIA_ROOT) / "_atlas"


def load_config(data_dir: Path | None = None) -> dict:
    path = (data_dir or _data_dir()) / CONFIG_NAME
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        raw = {}
    return {
        "dir": str(raw.get("dir") or ""),
        "project": raw.get("project") or None,
        "enabled": bool(raw.get("enabled")) and bool(raw.get("dir")),
    }


def save_config(
    dir_path: str, project: str | None, enabled: bool, data_dir: Path | None = None
) -> dict:
    """Validate and persist. The folder must exist; an empty folder disables watching."""
    dir_path = (dir_path or "").strip()
    if dir_path:
        folder = Path(dir_path).expanduser()
        if not folder.is_dir():
            raise ValueError(f"{dir_path} is not a folder that exists.")
        dir_path = str(folder)
    if project:
        from projects.models import Project

        if not Project.objects.filter(slug=project).exists():
            raise ValueError(f"No project called {project}.")
    data_dir = data_dir or _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    config = {"dir": dir_path, "project": project or None, "enabled": bool(enabled and dir_path)}
    (data_dir / CONFIG_NAME).write_text(json.dumps(config, indent=1))
    return config


def _ledger_path(data_dir: Path) -> Path:
    return data_dir / LEDGER_NAME


def _load_ledger(data_dir: Path) -> dict:
    try:
        return json.loads(_ledger_path(data_dir).read_text())
    except (OSError, ValueError):
        return {}


def _key(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{int(stat.st_mtime)}"


def scan_once(data_dir: Path | None = None) -> dict:
    """Import every new PDF in the watched folder. Returns a summary and records it."""
    from .importers import import_file

    data_dir = data_dir or _data_dir()
    config = load_config(data_dir)
    result = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seen": 0,
        "imported": 0,
        "existing": 0,
        "failed": 0,
        "items": [],
    }
    if not config["dir"]:
        result["error"] = "No folder is being watched."
        _STATE["last_scan"], _STATE["last_result"] = result["at"], result
        return result
    folder = Path(config["dir"])
    if not folder.is_dir():
        result["error"] = f"{folder} is missing."
        _STATE["last_scan"], _STATE["last_result"] = result["at"], result
        return result
    project = None
    if config["project"]:
        from projects.models import Project

        project = Project.objects.filter(slug=config["project"]).first()
    ledger = _load_ledger(data_dir)
    pending = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".pdf" or path.name.startswith("."):
            continue
        result["seen"] += 1
        key = _key(path)
        if ledger.get(str(path)) == key:
            continue
        pending.append((path, key))
    for path, key in pending[:MAX_PER_SCAN]:
        try:
            # a file still being written changes size between two looks — leave it for the next scan
            size = path.stat().st_size
            time.sleep(0.05)
            if path.stat().st_size != size or size == 0:
                continue
            summary = import_file(path.name, path.read_bytes(), project)
            item = summary.results[0] if summary.results else None
            ledger[str(path)] = key
            if item is None or item.error:
                result["failed"] += 1
                result["items"].append(
                    {"file": path.name, "error": (item.error if item else "no result")}
                )
            else:
                result["imported" if item.created else "existing"] += 1
                result["items"].append(
                    {
                        "file": path.name,
                        "reference": item.reference_id,
                        "title": item.title,
                        "created": item.created,
                        "needs_metadata": item.needs_metadata,
                    }
                )
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the folder
            log.exception("watch import failed for %s", path)
            ledger[str(path)] = key
            result["failed"] += 1
            result["items"].append({"file": path.name, "error": str(exc)[:200]})
    try:
        _ledger_path(data_dir).write_text(json.dumps(ledger, indent=0))
    except OSError:
        log.warning("could not write the watch ledger")
    _STATE["last_scan"], _STATE["last_result"] = result["at"], result
    if result["imported"]:
        _STATE["last_import"] = result  # the scan worth talking about (the thread scans every 15 s)
        log.info("watch folder: imported %d new PDF(s) from %s", result["imported"], folder)
    return result


def status(data_dir: Path | None = None) -> dict:
    config = load_config(data_dir)
    return {
        **config,
        "running": bool(_THREAD and _THREAD.is_alive() and not _STOP.is_set()),
        "last_scan": _STATE["last_scan"],
        "last_result": _STATE["last_result"],
        "last_import": _STATE["last_import"],
        "interval": INTERVAL_SECONDS,
    }


def start_watcher(data_dir: Path | None = None) -> bool:
    """Start the polling thread if watching is enabled and it is not running. Idempotent."""
    global _THREAD
    with _LOCK:
        if not load_config(data_dir)["enabled"]:
            return False
        if _THREAD and _THREAD.is_alive() and not _STOP.is_set():
            return True
        _STOP.clear()
        resolved = data_dir or _data_dir()

        def loop():
            from django.db import connection

            while not _STOP.is_set():
                try:
                    if load_config(resolved)["enabled"]:
                        scan_once(resolved)
                    else:
                        break
                except Exception:  # noqa: BLE001 - keep watching
                    log.exception("watch scan failed")
                finally:
                    connection.close()
                _STOP.wait(INTERVAL_SECONDS)

        _THREAD = threading.Thread(target=loop, name="atlas-watch-folder", daemon=True)
        _THREAD.start()
        return True


def stop_watcher() -> None:
    _STOP.set()
