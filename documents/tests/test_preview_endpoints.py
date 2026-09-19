"""Content + raw preview endpoints for the workspace (epic #30, slice 2c-ii)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from documents.models import Document
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    settings.ATLAS_API_KEY = KEY


class TestContentEndpoint:
    def test_returns_inline_text(self, client):
        p = ProjectFactory()
        d = Document.objects.create(
            project=p, title="notes.md", rel_path="notes.md", kind="other", content="# Hi\nbody"
        )
        data = client.get(f"/api/v1/documents/{d.id}/content/", **HEADERS).json()
        assert data["content"] == "# Hi\nbody" and data["kind"] == "other"
        assert data["truncated"] is False

    def test_decodes_uploaded_text_file(self, client):
        p = ProjectFactory()
        d = Document.objects.create(
            project=p,
            title="x.tex",
            rel_path="x.tex",
            kind="tex",
            file=SimpleUploadedFile("x.tex", b"\\documentclass{article}"),
        )
        data = client.get(f"/api/v1/documents/{d.id}/content/", **HEADERS).json()
        assert "documentclass" in data["content"]

    def test_binary_has_no_text_preview(self, client):
        p = ProjectFactory()
        d = Document.objects.create(
            project=p,
            title="f.png",
            rel_path="f.png",
            kind="asset",
            file=SimpleUploadedFile("f.png", b"\x89PNG\r\n"),
        )
        assert client.get(f"/api/v1/documents/{d.id}/content/", **HEADERS).status_code == 415


class TestRawEndpoint:
    def test_image_served_inline_with_nosniff(self, client):
        p = ProjectFactory()
        d = Document.objects.create(
            project=p,
            title="f.png",
            rel_path="f.png",
            kind="asset",
            file=SimpleUploadedFile("f.png", b"\x89PNG\r\n\x1a\nfake"),
        )
        resp = client.get(f"/api/v1/documents/{d.id}/raw/", **HEADERS)
        assert resp.status_code == 200
        assert resp["Content-Type"] == "image/png"
        assert resp["X-Content-Type-Options"] == "nosniff"
        assert resp["Content-Disposition"] == "inline"
        # #254: immutable uploads are cacheable so the workspace preview revalidates cheaply
        assert resp["Cache-Control"] == "private, max-age=86400"

    def test_mislabeled_image_extension_not_inline(self, client):
        # #250: a non-image file named .png (extension claims image/png, bytes say otherwise)
        # must NOT be served inline — the magic bytes are checked, so it 404s.
        p = ProjectFactory()
        d = Document.objects.create(
            project=p,
            title="x.png",
            rel_path="x.png",
            kind="asset",
            file=SimpleUploadedFile("x.png", b"<html><script>alert(1)</script>"),
        )
        assert client.get(f"/api/v1/documents/{d.id}/raw/", **HEADERS).status_code == 404

    def test_svg_is_never_inline(self, client):
        p = ProjectFactory()
        d = Document.objects.create(
            project=p,
            title="x.svg",
            rel_path="x.svg",
            kind="asset",
            file=SimpleUploadedFile("x.svg", b"<svg onload='alert(1)'></svg>"),
        )
        assert client.get(f"/api/v1/documents/{d.id}/raw/", **HEADERS).status_code == 404

    def test_text_node_without_file_not_raw(self, client):
        p = ProjectFactory()
        d = Document.objects.create(
            project=p, title="a.tex", rel_path="a.tex", kind="tex", content="x"
        )
        assert client.get(f"/api/v1/documents/{d.id}/raw/", **HEADERS).status_code == 404


class TestContentSave:
    def test_save_general_text(self, client):
        from documents.models import Document

        p = ProjectFactory()
        d = Document.objects.create(
            project=p, title="n.md", rel_path="n.md", kind="other", content="old"
        )
        resp = client.put(
            f"/api/v1/documents/{d.id}/content/",
            data={"content": "new body"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 200
        d.refresh_from_db()
        assert d.content == "new body"
        # backlog 358: the answer names the version the save left behind, so the pane can
        # show what changed; the note lands on that version; an unchanged save files nothing
        assert resp.json() == {"id": d.id, "saved": True, "version": 2, "filed": 1}
        resp = client.put(
            f"/api/v1/documents/{d.id}/content/",
            data={"content": "newer", "note": "tightened the intro"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.json()["filed"] == 2 and resp.json()["version"] == 3
        assert d.versions.first().note == "tightened the intro"
        resp = client.put(
            f"/api/v1/documents/{d.id}/content/",
            data={"content": "newer"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.json() == {"id": d.id, "saved": False, "unchanged": True, "version": 3}
        assert d.versions.count() == 2

    def test_write_file_answers_the_filed_version(self, client):
        p = ProjectFactory()
        url = f"/api/v1/projects/{p.slug}/write-file/"
        body = {"path": "notes/plan.md", "content": "# one"}
        resp = client.post(url, data=body, content_type="application/json", **HEADERS)
        assert resp.status_code == 201
        assert resp.json()["created"] and resp.json()["version"] == 1
        assert resp.json()["filed"] is None
        body["content"] = "# two"
        resp = client.post(url, data=body, content_type="application/json", **HEADERS)
        assert resp.status_code == 200
        assert (resp.json()["version"], resp.json()["filed"]) == (2, 1)
        resp = client.post(url, data=body, content_type="application/json", **HEADERS)
        assert (resp.json()["version"], resp.json()["filed"]) == (2, None)

    def test_save_rejects_manuscript_source(self, client):
        from documents.models import Document

        p = ProjectFactory()
        d = Document.objects.create(
            project=p,
            title="main.tex",
            rel_path="manuscript-1/main.tex",
            kind="tex",
            role="manuscript_source",
            content="x",
        )
        resp = client.put(
            f"/api/v1/documents/{d.id}/content/",
            data={"content": "hacked"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 409
        d.refresh_from_db()
        assert d.content == "x"

    def test_save_updates_uploaded_file_bytes(self, client):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from documents.models import Document

        p = ProjectFactory()
        d = Document.objects.create(
            project=p,
            title="s.tex",
            rel_path="s.tex",
            kind="tex",
            file=SimpleUploadedFile("s.tex", b"before"),
        )
        client.put(
            f"/api/v1/documents/{d.id}/content/",
            data={"content": "after"},
            content_type="application/json",
            **HEADERS,
        )
        d.refresh_from_db()
        assert d.file.read().decode() == "after"
