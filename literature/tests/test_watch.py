"""Watched folder (#406): PDFs dropped into one folder are imported once."""

import json

import pytest

from literature import watch
from literature.models import Reference

MINI_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\nxref\n0 4\n0000000000 65535 f \n"
    b"0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF\n"
)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    # the importer tries Crossref/OpenAlex for a DOI; a stub PDF has none, but never leave the door open
    monkeypatch.setattr("literature.importers.find_identifiers_in_text", lambda text: (None, None))


@pytest.mark.django_db
def test_scan_imports_new_pdfs_once(tmp_path):
    folder = tmp_path / "inbox"
    folder.mkdir()
    data_dir = tmp_path / "data"
    watch.save_config(str(folder), None, True, data_dir=data_dir)
    (folder / "paper-one.pdf").write_bytes(MINI_PDF)
    (folder / "notes.txt").write_text("not a pdf")
    first = watch.scan_once(data_dir)
    assert first["seen"] == 1 and first["imported"] == 1 and first["failed"] == 0
    assert Reference.objects.count() == 1
    again = watch.scan_once(data_dir)
    assert (
        again["seen"] == 1 and again["imported"] == 0 and again["existing"] == 0
    )  # ledger skipped it
    assert json.loads((data_dir / watch.LEDGER_NAME).read_text())
    (folder / "paper-two.pdf").write_bytes(MINI_PDF + b"\n%second")
    assert watch.scan_once(data_dir)["imported"] == 1
    assert Reference.objects.count() == 2
    st = watch.status(data_dir)
    assert st["enabled"] and st["dir"] == str(folder) and st["last_result"]["imported"] == 1


def test_config_validation(tmp_path):
    with pytest.raises(ValueError):
        watch.save_config(str(tmp_path / "missing"), None, True, data_dir=tmp_path)
    cfg = watch.save_config("", None, True, data_dir=tmp_path)
    assert not cfg["enabled"] and watch.load_config(tmp_path)["enabled"] is False


@pytest.mark.django_db
def test_api_set_scan_and_stop(client, settings, django_user_model, tmp_path, monkeypatch):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    monkeypatch.setattr(watch, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(watch, "start_watcher", lambda data_dir=None: True)
    folder = tmp_path / "drop"
    folder.mkdir()
    bad = client.post(
        "/api/v1/watch-folder/",
        {"dir": str(tmp_path / "nope"), "enabled": True},
        content_type="application/json",
        HTTP_X_API_KEY="k",
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/v1/watch-folder/",
        {"dir": str(folder), "enabled": True},
        content_type="application/json",
        HTTP_X_API_KEY="k",
    ).json()
    assert ok["enabled"] and ok["dir"] == str(folder)
    (folder / "x.pdf").write_bytes(MINI_PDF)
    scanned = client.post("/api/v1/watch-folder/scan/", HTTP_X_API_KEY="k").json()
    assert scanned["imported"] == 1
    off = client.post(
        "/api/v1/watch-folder/",
        {"dir": "", "enabled": False},
        content_type="application/json",
        HTTP_X_API_KEY="k",
    ).json()
    assert not off["enabled"]
    src = open("frontend/src/app/pages/Library.tsx").read()
    assert 'data-testid="watch-folder"' in src and "/watch-folder/scan/" in src
    assert "pub async fn pick_folder" in open("desktop/src/localfs.rs").read()
