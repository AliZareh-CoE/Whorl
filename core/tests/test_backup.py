"""One-file backup (2026-09-06)."""

import io
import json
import zipfile

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
