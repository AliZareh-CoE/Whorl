"""One-file backup (2026-09-06)."""

import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from django.core.files.base import ContentFile

from core import backup
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def test_backup_zip_has_database_media_and_manifest(client_logged_in, settings, tmp_path):
    from documents.models import Document

    settings.MEDIA_ROOT = tmp_path / "media"
    project = ProjectFactory(name="Backed up")
    Document.objects.create(
        project=project, title="A file", file=ContentFile(b"hello", name="a.txt")
    )
    response = client_logged_in.get("/api/v1/backup.zip")
    assert response.status_code == 200 and response["Content-Type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = zf.namelist()
    assert "MANIFEST.json" in names and "README.txt" in names
    manifest = json.loads(zf.read("MANIFEST.json"))
    assert manifest["media_files"] == 1 and any(n.startswith("media/") for n in names)
    if backup._sqlite_path():
        assert "atlas.sqlite3" in names and "database.sql" in names
    else:
        assert "database.json" in names and b"Backed up" in zf.read("database.json")


def test_sqlite_dump_is_consistent(tmp_path, settings):
    import sqlite3

    db = tmp_path / "t.sqlite3"
    con = sqlite3.connect(str(db))
    con.execute("create table t(x)")
    con.execute("insert into t values (42)")
    con.commit()
    assert b"42" in backup._dump_sqlite(db)
    copy = tmp_path / "copy.sqlite3"
    copy.write_bytes(backup._sqlite_bytes(db))
    assert sqlite3.connect(str(copy)).execute("select x from t").fetchone() == (42,)


# --- restore (#376) ---------------------------------------------------------------------


def _make_backup_zip(tmp_path, media_name="media/docs/a.txt", with_sqlite=True):
    path = tmp_path / "backup.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "MANIFEST.json",
            json.dumps({"created_at": "2026-09-01T00:00:00+00:00", "media_files": 1}),
        )
        if with_sqlite:
            db = sqlite3.connect(":memory:")
            db.execute("create table t(x)")
            db.execute("insert into t values (42)")
            db.commit()
            dump = tmp_path / "restored.sqlite3"
            disk = sqlite3.connect(str(dump))
            db.backup(disk)
            disk.close()
            zf.write(dump, "atlas.sqlite3")
        else:
            zf.writestr("database.json", "[]")
        zf.writestr(media_name, "restored media")
    return path


def test_inspect_rejects_non_backups(tmp_path):
    (tmp_path / "x.zip").write_bytes(b"not a zip")
    with pytest.raises(backup.RestoreError, match="not a zip"):
        backup.inspect_backup(tmp_path / "x.zip")
    with zipfile.ZipFile(tmp_path / "y.zip", "w") as zf:
        zf.writestr("hello.txt", "hi")
    with pytest.raises(backup.RestoreError, match="MANIFEST"):
        backup.inspect_backup(tmp_path / "y.zip")
    with zipfile.ZipFile(tmp_path / "z.zip", "w") as zf:
        zf.writestr("MANIFEST.json", "{}")
        zf.writestr("atlas.sqlite3", "x")
        zf.writestr("media/../../evil", "x")
    with pytest.raises(backup.RestoreError, match="Unsafe"):
        backup.inspect_backup(tmp_path / "z.zip")


def test_stage_apply_and_keep_previous(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "atlas.sqlite3"
    old = sqlite3.connect(str(db_path))
    old.execute("create table old(y)")
    old.commit()
    old.close()
    media = data_dir / "media"
    (media / "docs").mkdir(parents=True)
    (media / "docs" / "old.txt").write_text("old media")
    with open(_make_backup_zip(tmp_path), "rb") as fh:
        staged = backup.stage_restore(fh, data_dir=data_dir)
    assert staged["has_sqlite"] and staged["media_files"] == 1
    assert backup.restore_status(data_dir)["pending"]["staged_at"]
    result = backup.apply_pending_restore(data_dir, db_path=db_path, media_root=media)
    assert result["ok"], result
    assert sqlite3.connect(str(db_path)).execute("select x from t").fetchone() == (42,)
    assert (media / "docs" / "a.txt").read_text() == "restored media"
    kept = Path(result["kept_previous_in"])
    assert (kept / "atlas.sqlite3").exists() and (kept / "media" / "docs" / "old.txt").exists()
    status = backup.restore_status(data_dir)
    assert status["pending"] is None and status["last_result"]["ok"]
    assert backup.apply_pending_restore(data_dir, db_path=db_path, media_root=media) is None


def test_cancel_and_api_flow(client_logged_in, settings, tmp_path):
    settings.DATA_DIR = tmp_path / "data"
    settings.MEDIA_ROOT = tmp_path / "data" / "media"
    assert client_logged_in.get("/api/v1/restore/").json()["pending"] is None
    bad = client_logged_in.post(
        "/api/v1/restore/", {"file": io.BytesIO(b"nope")}, format="multipart"
    )
    assert bad.status_code == 400 and "zip" in bad.json()["detail"]
    with open(_make_backup_zip(tmp_path, with_sqlite=False), "rb") as fh:
        response = client_logged_in.post("/api/v1/restore/", {"file": fh})
    assert response.status_code == 202 and response.json()["staged"]["has_json"]
    assert client_logged_in.get("/api/v1/restore/").json()["pending"]["media_files"] == 1
    assert client_logged_in.delete("/api/v1/restore/").status_code == 204
    assert client_logged_in.get("/api/v1/restore/").json()["pending"] is None


def test_restore_backup_command(tmp_path, settings):
    from django.core.management import call_command

    settings.DATA_DIR = tmp_path / "data"
    settings.MEDIA_ROOT = tmp_path / "data" / "media"
    out = io.StringIO()
    call_command("restore_backup", str(_make_backup_zip(tmp_path, with_sqlite=False)), stdout=out)
    assert "Staged backup" in out.getvalue()
    assert (tmp_path / "data" / "restore-database.json").exists()
    assert (tmp_path / "data" / "media" / "docs" / "a.txt").read_text() == "restored media"
