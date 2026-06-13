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
            file=SimpleUploadedFile("f.png", b"\x89PNG\r\nfake"),
        )
        resp = client.get(f"/api/v1/documents/{d.id}/raw/", **HEADERS)
        assert resp.status_code == 200
        assert resp["Content-Type"] == "image/png"
        assert resp["X-Content-Type-Options"] == "nosniff"
        assert resp["Content-Disposition"] == "inline"

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
