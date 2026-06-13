"""Workspace write-op guards: manuscript nodes are protected (epic #30, slice 2d-ii)."""

import pytest

from documents.models import Document, Folder
from projects.tests.factories import ProjectFactory
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    settings.ATLAS_API_KEY = KEY


class TestGeneralNodesMutable:
    def test_create_folder(self, client):
        p = ProjectFactory()
        resp = client.post(
            "/api/v1/folders/",
            data={"project": p.slug, "parent": None, "name": "Analysis"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 201
        assert Folder.objects.filter(project=p, name="Analysis").exists()

    def test_rename_and_delete_general_document(self, client):
        p = ProjectFactory()
        d = Document.objects.create(project=p, title="old.md", rel_path="old.md", kind="other")
        assert (
            client.patch(
                f"/api/v1/documents/{d.id}/",
                data={"title": "new.md"},
                content_type="application/json",
                **HEADERS,
            ).status_code
            == 200
        )
        assert client.delete(f"/api/v1/documents/{d.id}/", **HEADERS).status_code == 204


class TestManuscriptNodesProtected:
    def _manuscript(self):
        p = ProjectFactory()
        m = ManuscriptFactory(project=p)
        m.files.create(path="main.tex", content="x", kind="tex", is_main=True)  # mirrors to tree
        return p, m

    def test_cannot_delete_manuscript_source(self, client):
        p, m = self._manuscript()
        node = Document.objects.get(role="manuscript_source")
        assert client.delete(f"/api/v1/documents/{node.id}/", **HEADERS).status_code == 403

    def test_cannot_rename_manuscript_source(self, client):
        p, m = self._manuscript()
        node = Document.objects.get(role="manuscript_source")
        resp = client.patch(
            f"/api/v1/documents/{node.id}/",
            data={"title": "hijack"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 403

    def test_cannot_delete_manuscript_root_folder(self, client):
        p, m = self._manuscript()
        m.refresh_from_db()
        assert client.delete(f"/api/v1/folders/{m.root_folder_id}/", **HEADERS).status_code == 403


class TestWriteFileEndpoint:
    def test_create_and_update_general_file(self, client):
        p = ProjectFactory()
        r1 = client.post(
            f"/api/v1/projects/{p.slug}/write-file/",
            data={"path": "notes/idea.md", "content": "v1"},
            content_type="application/json",
            **HEADERS,
        )
        assert r1.status_code == 201 and r1.json()["created"] is True
        assert Document.objects.get(project=p, rel_path="notes/idea.md").content == "v1"
        r2 = client.post(
            f"/api/v1/projects/{p.slug}/write-file/",
            data={"path": "notes/idea.md", "content": "v2"},
            content_type="application/json",
            **HEADERS,
        )
        assert r2.status_code == 200
        assert Document.objects.get(project=p, rel_path="notes/idea.md").content == "v2"

    def test_rejects_traversal_and_manuscript_path(self, client):
        p = ProjectFactory()
        assert (
            client.post(
                f"/api/v1/projects/{p.slug}/write-file/",
                data={"path": "../escape.md", "content": "x"},
                content_type="application/json",
                **HEADERS,
            ).status_code
            == 400
        )
        assert (
            client.post(
                f"/api/v1/projects/{p.slug}/write-file/",
                data={"path": "manuscript-1/main.tex", "content": "x"},
                content_type="application/json",
                **HEADERS,
            ).status_code
            == 409
        )
