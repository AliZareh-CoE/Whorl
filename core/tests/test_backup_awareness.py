"""#424 — the app knows when it was last backed up and says so, calmly."""

import datetime as dt

import pytest
from django.utils import timezone

from core.backups import STALE_AFTER_DAYS, backup_status, last_backup
from core.models import BackupRecord
from projects.models import Project

pytestmark = pytest.mark.django_db


def test_status_never_stale_without_data_and_stale_without_backup():
    assert backup_status() == {
        "last": None,
        "stale": False,
        "has_data": False,
        "stale_after_days": STALE_AFTER_DAYS,
    }
    Project.objects.create(name="One")
    assert backup_status()["stale"] is True and last_backup() is None


def test_download_records_and_freshens(client_logged_in, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    Project.objects.create(name="One")
    r = client_logged_in.get("/api/v1/backup.zip")
    assert r.status_code == 200
    row = BackupRecord.objects.get()
    assert row.size_bytes == len(r.content) and row.database in ("sqlite", "json")
    status = backup_status()
    assert status["stale"] is False and status["last"]["days_ago"] == 0
    # ageing past the threshold makes it stale again
    BackupRecord.objects.filter(pk=row.pk).update(
        created_at=timezone.now() - dt.timedelta(days=STALE_AFTER_DAYS + 1)
    )  # etag: ok
    assert backup_status()["stale"] is True
    # it shows up in the diagnostics report, on the dashboard and in the SPA
    report = client_logged_in.get("/api/v1/diagnostics/").json()
    assert report["backups"]["stale"] is True and "last backup:" in report["text"]
    dash = client_logged_in.get("/api/v1/dashboard/").json()
    assert dash["attention"]["backup"]["stale"] is True
    src = open("frontend/src/app/pages/Dashboard.tsx").read()
    assert 'data-testid="attention-backup"' in src
    assert 'data-testid="last-backup"' in open("frontend/src/app/pages/Diagnostics.tsx").read()
