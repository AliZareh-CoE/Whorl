"""#536 — the backup destination: an attached drive or sync folder every snapshot is copied to."""

import io
import json
from pathlib import Path

import pytest
from django.core.management import call_command

from core import destination, snapshots
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def home(tmp_path, settings, monkeypatch):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.DATA_DIR = tmp_path / "data"
    monkeypatch.setenv("ATLAS_SNAPSHOT_DIR", str(tmp_path / "backups"))
    drive = tmp_path / "Google Drive" / "My Drive"
    drive.mkdir(parents=True)
    return {"root": tmp_path, "drive": drive, "data": tmp_path / "data"}


def test_describe_knows_the_sync_services_and_drives():
    assert (
        destination.describe("/Users/ali/Library/CloudStorage/GoogleDrive-a@b/My Drive")["kind"]
        == "google-drive"
    )
    assert destination.describe("C:\\Users\\ali\\OneDrive - University")["label"] == "OneDrive"
    assert destination.describe("/home/ali/Dropbox/backups")["kind"] == "dropbox"
    assert (
        destination.describe("/Users/ali/Library/Mobile Documents/com~apple~CloudDocs")["kind"]
        == "icloud"
    )
    assert destination.describe("/home/ali/Nextcloud")["kind"] == "nextcloud"
    assert destination.describe("/Volumes/LaCie/atlas")["kind"] == "drive"
    assert destination.describe("/media/ali/USB")["kind"] == "drive"
    assert destination.describe("E:\\backups")["kind"] == "drive"
    assert destination.describe("/home/ali/backups") == {"kind": "folder", "label": "Folder"}


def test_suggestions_list_what_exists(tmp_path):
    (tmp_path / "Dropbox").mkdir()
    (tmp_path / "OneDrive - Uni").mkdir()
    (tmp_path / "Library" / "CloudStorage" / "OneDrive-Uni").mkdir(parents=True)
    (tmp_path / ".hidden").mkdir()
    rows = destination.suggestions(home=tmp_path)
    assert {(r["dir"], r["kind"]) for r in rows} >= {
        (str(tmp_path / "Dropbox"), "dropbox"),
        (str(tmp_path / "OneDrive - Uni"), "onedrive"),
        (str(tmp_path / "Library" / "CloudStorage" / "OneDrive-Uni"), "onedrive"),
    }
    assert not any("Google" in r["dir"] for r in rows if r["dir"].startswith(str(tmp_path)))


def test_save_config_validates_the_folder(home):
    with pytest.raises(ValueError, match="not a folder"):
        destination.save_config(str(home["root"] / "nowhere"))
    cfg = destination.save_config(str(home["drive"]))
    assert cfg == {"dir": str(home["drive"]), "enabled": True}
    assert destination.load_config() == cfg
    assert not (home["drive"] / ".atlas-write-check").exists()
    assert destination.save_config("") == {"dir": "", "enabled": False}
    assert destination.target_dir() is None


def test_every_snapshot_is_copied_verified_and_rotated(home, monkeypatch):
    ProjectFactory()
    destination.save_config(str(home["drive"]))
    result = snapshots.take_snapshot()
    copy = home["drive"] / "Atlas backups" / Path(result["path"]).name
    assert result["copied"]["name"] == copy.name and result["copied"]["verified"] is True
    assert copy.read_bytes() == Path(result["path"]).read_bytes()
    assert not list((home["drive"] / "Atlas backups").glob("*.partial"))
    status = destination.destination_status()
    assert status["enabled"] and status["reachable"] and status["copies"] == 1
    assert status["in_sync"] is True and status["kind"] == "google-drive"
    assert status["last_copy"]["name"] == copy.name and status["last_error"] is None
    # rotation keeps the newest KEEP copies
    monkeypatch.setattr(destination, "KEEP", 2)
    for _ in range(3):
        snapshots.take_snapshot()
    assert len(destination.list_copies(home["drive"] / "Atlas backups")) == 2
    # the paste-me report and the API carry it
    from core.diagnostics import as_text, collect

    report = collect()
    assert report["backup_destination"]["copies"] == 2
    assert "backup destination:" in as_text(report) and "newest snapshot copied" in as_text(report)


def test_a_failed_copy_never_fails_the_snapshot(home, monkeypatch):
    ProjectFactory()
    destination.save_config(str(home["drive"]))

    def broken(*a, **k):
        raise OSError("No space left on device")

    monkeypatch.setattr(destination.shutil, "copyfile", broken)
    result = snapshots.take_snapshot()
    assert Path(result["path"]).exists() and result["copied"] is None
    status = destination.destination_status()
    assert "No space left" in status["last_error"]["detail"] and status["in_sync"] is False
    monkeypatch.undo()
    # an unplugged drive: not reachable, nothing raised, and the next snapshot must not
    # recreate the drive's path on the boot disk
    home["drive"].rename(home["root"] / "unplugged")
    status = destination.destination_status()
    assert status["reachable"] is False and status["copies"] == 0
    result = snapshots.take_snapshot()
    assert result["copied"] is None and not home["drive"].exists()
    assert "not reachable" in destination.destination_status()["last_error"]["detail"]
    with pytest.raises(OSError, match="not reachable"):
        destination.sync_now()


def test_sync_now_copies_the_newest_once(home):
    ProjectFactory()
    with pytest.raises(ValueError, match="No backup destination"):
        destination.sync_now()
    destination.save_config(str(home["drive"]))
    assert destination.sync_now()["detail"] == "no snapshot to copy yet"
    snapshots.take_snapshot(kind="manual")
    assert destination.sync_now()["detail"] == "already there"
    (home["drive"] / "Atlas backups" / snapshots.last_snapshot()["name"]).unlink()
    assert destination.sync_now()["copied"] is True


def test_api_attach_status_and_sync(client_logged_in, home):
    ProjectFactory()
    snapshots.take_snapshot()
    r = client_logged_in.get("/api/v1/backup-destination/").json()
    assert r["enabled"] is False and "suggestions" in r
    r = client_logged_in.post(
        "/api/v1/backup-destination/",
        {"dir": str(home["root"] / "nope")},
        content_type="application/json",
    )
    assert r.status_code == 400
    r = client_logged_in.post(
        "/api/v1/backup-destination/", {"dir": str(home["drive"])}, content_type="application/json"
    )
    assert r.status_code == 200 and r.json()["in_sync"] is True and r.json()["copies"] == 1
    r = client_logged_in.post("/api/v1/backup-destination/sync/")
    assert r.status_code == 200 and r.json()["detail"] == "already there"
    r = client_logged_in.post(
        "/api/v1/backup-destination/", {"dir": ""}, content_type="application/json"
    )
    assert r.json()["enabled"] is False
    assert client_logged_in.post("/api/v1/backup-destination/sync/").status_code == 400
    assert (
        client_logged_in.get("/api/v1/diagnostics/").json()["backup_destination"]["enabled"]
        is False
    )


def test_snapshot_command_to(home):
    ProjectFactory()
    out = io.StringIO()
    call_command("snapshot", "--to", str(home["drive"]), stdout=out)
    assert "Copied to:" in out.getvalue()
    assert json.loads((home["data"] / destination.CONFIG_NAME).read_text())["enabled"] is True
    assert len(destination.list_copies(home["drive"] / "Atlas backups")) == 1


def test_diagnostics_page_shows_the_destination():
    tsx = Path("frontend/src/app/pages/Diagnostics.tsx").read_text()
    for needle in (
        'data-testid="backup-destination"',
        "/backup-destination/sync/",
        "suggestions",
        "pickFolder",
        'data-testid="destination-attach"',
    ):
        assert needle in tsx, needle
