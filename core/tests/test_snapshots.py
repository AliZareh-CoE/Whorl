"""Automatic snapshots (#462): a backup zip a day into the data folder, last seven kept."""

import datetime
import io
import os
import zipfile

import pytest
from django.core.management import call_command
from django.utils import timezone

from core import snapshots
from core.models import BackupRecord
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def snapshot_home(tmp_path, settings, monkeypatch):
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.setenv("ATLAS_SNAPSHOT_DIR", str(tmp_path / "backups"))
    return tmp_path / "backups"


def _age(path, hours):
    stamp = (timezone.now() - datetime.timedelta(hours=hours)).timestamp()
    os.utime(path, (stamp, stamp))


def test_take_snapshot_writes_a_real_backup_and_records_it(snapshot_home):
    ProjectFactory(name="Kept safe")
    result = snapshots.take_snapshot()
    files = snapshots.list_snapshots()
    assert len(files) == 1 and files[0]["path"] == result["path"]
    assert files[0]["name"].startswith(snapshots.PREFIX) and files[0]["name"].endswith(".zip")
    with zipfile.ZipFile(result["path"]) as zf:
        assert "MANIFEST.json" in zf.namelist()
    assert not list(snapshot_home.glob("*.partial"))
    row = BackupRecord.objects.get()
    assert row.kind == "auto" and row.path == result["path"] and row.size_bytes > 0


def test_prune_keeps_the_newest_keep_files(snapshot_home):
    ProjectFactory()
    snapshot_home.mkdir()
    for i in range(10):
        path = snapshot_home / f"{snapshots.PREFIX}old{i}.zip"
        path.write_bytes(b"x")
        _age(path, hours=100 - i)
    result = snapshots.take_snapshot()
    kept = snapshots.list_snapshots()
    assert len(kept) == snapshots.KEEP and kept[0]["path"] == result["path"]
    assert len(result["removed"]) == 10 + 1 - snapshots.KEEP
    # the oldest ones went, the newest old ones stayed
    assert "atlas-snapshot-old0.zip" in result["removed"]
    assert "atlas-snapshot-old9.zip" not in result["removed"]


def test_due_only_with_data_and_when_the_newest_is_a_day_old(snapshot_home):
    assert snapshots.due() is False  # nothing to keep yet
    ProjectFactory()
    assert snapshots.due() is True  # data, no snapshot
    snapshots.take_snapshot()
    assert snapshots.due() is False
    _age(snapshots.list_snapshots()[0]["path"], hours=25)
    assert snapshots.due() is True
    assert snapshots.run_if_due() is not None and len(snapshots.list_snapshots()) == 2
    assert snapshots.run_if_due() is None


def test_run_if_due_remembers_a_failure_instead_of_raising(snapshot_home, monkeypatch):
    ProjectFactory()

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(snapshots, "take_snapshot", boom)
    assert snapshots.run_if_due() is None
    status = snapshots.snapshot_status()
    assert status["last_error"]["detail"] == "disk full" and status["count"] == 0
    monkeypatch.undo()
    monkeypatch.setenv("ATLAS_SNAPSHOT_DIR", str(snapshot_home))
    snapshots.run_if_due()
    assert snapshots.snapshot_status()["last_error"] is None


def test_status_and_api(client_logged_in, snapshot_home):
    ProjectFactory()
    empty = client_logged_in.get("/api/v1/snapshots/").json()
    assert empty["count"] == 0 and empty["last"] is None and empty["files"] == []
    assert empty["dir"] == str(snapshot_home) and empty["keep"] == snapshots.KEEP
    written = client_logged_in.post("/api/v1/snapshots/")
    assert written.status_code == 201 and written.json()["path"].startswith(str(snapshot_home))
    after = client_logged_in.get("/api/v1/snapshots/").json()
    assert after["count"] == 1 and after["last"]["hours_ago"] == 0
    assert after["files"][0]["name"] == after["last"]["name"]
    assert BackupRecord.objects.get().kind == "manual"
    # the diagnostics report carries it, in JSON and in the paste-me text
    report = client_logged_in.get("/api/v1/diagnostics/").json()
    assert report["snapshots"]["count"] == 1
    assert "snapshots: 1 kept in" in report["text"]


def test_management_command_if_due(snapshot_home):
    out = io.StringIO()
    call_command("snapshot", "--if-due", stdout=out)
    assert "Not due" in out.getvalue() and snapshots.list_snapshots() == []
    ProjectFactory()
    out = io.StringIO()
    call_command("snapshot", "--if-due", stdout=out)
    assert "Snapshot written" in out.getvalue() and len(snapshots.list_snapshots()) == 1
    out = io.StringIO()
    call_command("snapshot", "--if-due", stdout=out)
    assert "Not due" in out.getvalue()
    call_command("snapshot", "--keep", "1", stdout=io.StringIO())
    assert len(snapshots.list_snapshots()) == 1


def test_scheduler_starts_once_and_the_desktop_wires_it():
    from pathlib import Path

    try:
        assert snapshots.start_scheduler() is True
        assert snapshots.start_scheduler() is False
        assert snapshots.snapshot_status()["scheduler"] is True
    finally:
        snapshots.stop_scheduler()
    src = Path("core/management/commands/run_desktop.py").read_text()
    assert "start_scheduler()" in src


def test_diagnostics_page_shows_the_section():
    from pathlib import Path

    tsx = Path("frontend/src/app/pages/Diagnostics.tsx").read_text()
    for needle in ('data-testid="snapshots"', 'data-testid="snapshot-now"', "/snapshots/"):
        assert needle in tsx
