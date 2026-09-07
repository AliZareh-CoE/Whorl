"""Backup awareness (#424): when was the last one, and is that too long ago?"""

from __future__ import annotations

from django.utils import timezone

STALE_AFTER_DAYS = 14


def last_backup() -> dict | None:
    from core.models import BackupRecord

    row = BackupRecord.objects.order_by("-created_at").first()
    if row is None:
        return None
    return {
        "at": row.created_at.isoformat(),
        "days_ago": (timezone.now() - row.created_at).days,
        "size_bytes": row.size_bytes,
        "media_files": row.media_files,
        "database": row.database,
    }


def backup_status() -> dict:
    """{last, stale, has_data}: stale when there is data worth keeping and no backup within
    STALE_AFTER_DAYS (or none at all)."""
    from projects.models import Project

    last = last_backup()
    has_data = Project.objects.exists()
    stale = has_data and (last is None or last["days_ago"] >= STALE_AFTER_DAYS)
    return {
        "last": last,
        "stale": stale,
        "has_data": has_data,
        "stale_after_days": STALE_AFTER_DAYS,
    }
