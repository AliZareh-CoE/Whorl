"""Automatic snapshots (#462): the backup you never have to remember.

The one-file backup (core/backup.py) is a download — it only exists when the owner thinks
of it. A snapshot is the same zip written into ``<data dir>/backups/`` by Atlas itself: once
a day while the app runs, kept for the last KEEP days, oldest dropped. The desktop starts a
small scheduler thread at boot; a server install runs ``manage.py snapshot --if-due`` from
cron. Nothing here talks to the network and a failure never reaches the owner as an error —
it is written to the log and shown on Diagnostics as "last snapshot failed".
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
from pathlib import Path

from django.conf import settings
from django.utils import timezone

log = logging.getLogger("atlas.snapshots")

KEEP = 7
EVERY = datetime.timedelta(hours=24)
PREFIX = "atlas-snapshot-"
FIRST_CHECK_SECONDS = 90  # after boot: never slow the launch, and skip an empty first run
CHECK_EVERY_SECONDS = 60 * 60

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_STOP = threading.Event()
_LAST_ERROR: dict | None = None


def snapshot_dir() -> Path:
    """``<data dir>/backups`` on the desktop; ``<project>/backups`` for a source checkout."""
    configured = os.environ.get("ATLAS_SNAPSHOT_DIR")
    if configured:
        return Path(configured)
    base = getattr(settings, "DATA_DIR", None) or settings.BASE_DIR
    return Path(base) / "backups"


def list_snapshots(directory: Path | None = None) -> list[dict]:
    """Newest first: what is actually on disk (a record without a file is not a backup)."""
    directory = directory or snapshot_dir()
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
                "created_at": datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC),
            }
        )
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows


def prune(directory: Path | None = None, keep: int = KEEP) -> list[str]:
    """Drop the oldest snapshots beyond ``keep``; return the names removed."""
    removed = []
    for row in list_snapshots(directory)[keep:]:
        try:
            Path(row["path"]).unlink()
            removed.append(row["name"])
        except OSError as exc:  # noqa: PERF203 - one bad file must not stop the others
            log.warning("Could not remove old snapshot %s: %s", row["path"], exc)
    return removed


def take_snapshot(directory: Path | None = None, *, keep: int = KEEP, kind: str = "auto") -> dict:
    """Write one snapshot zip, record it, rotate. Returns ``{path, size_bytes, manifest,
    removed}``. The zip is built under a temporary name and renamed at the end, so a crash
    mid-write never leaves a half zip that looks like a backup."""
    from core.backup import build_backup
    from core.models import BackupRecord

    directory = directory or snapshot_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d-%H%M%S")
    final = directory / f"{PREFIX}{stamp}.zip"
    n = 1
    while final.exists():  # two in one second (tests, a double click): never overwrite
        n += 1
        final = directory / f"{PREFIX}{stamp}-{n}.zip"
    partial = final.with_suffix(".partial")
    try:
        with open(partial, "wb") as stream:
            manifest = build_backup(stream)
        os.replace(partial, final)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    size = final.stat().st_size
    BackupRecord.objects.create(
        size_bytes=size,
        media_files=manifest.get("media_files", 0),
        database=manifest.get("database", ""),
        kind=kind,
        path=str(final),
    )
    removed = prune(directory, keep=keep)
    log.info("Snapshot written: %s (%d bytes); removed %s", final, size, removed or "none")
    return {"path": str(final), "size_bytes": size, "manifest": manifest, "removed": removed}


def last_snapshot(directory: Path | None = None) -> dict | None:
    rows = list_snapshots(directory)
    return rows[0] if rows else None


def due(now=None, directory: Path | None = None, every: datetime.timedelta = EVERY) -> bool:
    """A snapshot is due when there is something to keep and the newest one on disk is older
    than ``every`` (or there is none). An empty install never snapshots."""
    from projects.models import Project

    if not Project.objects.exists():
        return False
    last = last_snapshot(directory)
    if last is None:
        return True
    now = now or timezone.now()
    return now - last["created_at"] >= every


def run_if_due(directory: Path | None = None) -> dict | None:
    """The scheduler's tick: snapshot when due, remember a failure for Diagnostics."""
    global _LAST_ERROR
    if not due(directory=directory):
        return None
    try:
        result = take_snapshot(directory)
    except Exception as exc:  # noqa: BLE001 - surfaced on Diagnostics, never raised to a thread
        _LAST_ERROR = {"at": timezone.now().isoformat(), "detail": str(exc)[:500]}
        log.exception("Automatic snapshot failed")
        return None
    _LAST_ERROR = None
    return result


def snapshot_status(directory: Path | None = None) -> dict:
    directory = directory or snapshot_dir()
    rows = list_snapshots(directory)
    last = rows[0] if rows else None
    now = timezone.now()
    return {
        "dir": str(directory),
        "keep": KEEP,
        "every_hours": int(EVERY.total_seconds() // 3600),
        "count": len(rows),
        "total_bytes": sum(r["size_bytes"] for r in rows),
        "last": (
            {
                "name": last["name"],
                "path": last["path"],
                "size_bytes": last["size_bytes"],
                "at": last["created_at"].isoformat(),
                "hours_ago": int((now - last["created_at"]).total_seconds() // 3600),
            }
            if last
            else None
        ),
        "scheduler": _THREAD is not None and _THREAD.is_alive(),
        "last_error": _LAST_ERROR,
    }


def start_scheduler(directory: Path | None = None) -> bool:
    """Desktop: one daemon thread that checks hourly whether a snapshot is due. Returns
    whether it was started (False when one is already running)."""
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return False
        _STOP.clear()

        def loop():
            from django.db import close_old_connections

            wait = FIRST_CHECK_SECONDS
            while not _STOP.wait(wait):
                try:
                    run_if_due(directory)
                finally:
                    close_old_connections()
                try:
                    # #527: the desktop has no huey — the retraction watch sweeps from here.
                    # Bounded, and once nothing is stale it asks nothing; a network failure
                    # leaves the verdicts alone and must never take the snapshot thread down.
                    from literature.retractions import check_stale

                    check_stale()
                except Exception:  # noqa: BLE001 — a sweep failure is logged, not fatal
                    log.exception("retraction sweep failed")
                finally:
                    close_old_connections()
                try:
                    # #529: the preprint watch sweeps from the same thread, same rules.
                    from literature.preprints import check_stale as check_stale_preprints

                    check_stale_preprints()
                except Exception:  # noqa: BLE001
                    log.exception("preprint sweep failed")
                finally:
                    close_old_connections()
                try:
                    # #530: the citation watch sweeps from the same thread, same rules.
                    from literature.citing import check_stale as check_stale_citations

                    check_stale_citations()
                except Exception:  # noqa: BLE001
                    log.exception("citation sweep failed")
                finally:
                    close_old_connections()
                try:
                    # #531: the journal / arXiv feeds refresh from the same thread, same rules.
                    from literature.feeds import refresh_stale as refresh_stale_feeds

                    refresh_stale_feeds()
                except Exception:  # noqa: BLE001
                    log.exception("feed sweep failed")
                finally:
                    close_old_connections()
                wait = CHECK_EVERY_SECONDS

        _THREAD = threading.Thread(target=loop, name="atlas-snapshots", daemon=True)
        _THREAD.start()
        return True


def stop_scheduler() -> None:
    global _THREAD
    _STOP.set()
    with _LOCK:
        _THREAD = None
