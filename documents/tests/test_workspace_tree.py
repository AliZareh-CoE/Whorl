"""Unified workspace tree selector + API (file-workspace epic #30, slice 2a)."""

import pytest

from documents.models import Document, Folder
from documents.selectors import workspace_tree
from projects.tests.factories import ProjectFactory
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _seed():
    project = ProjectFactory()
    folder = Folder.objects.create(project=project, name="Data")
    Document.objects.create(
        project=project, folder=folder, title="readme.md", rel_path="Data/readme.md", kind="other"
    )
    m = ManuscriptFactory(project=project)
    m.files.create(path="main.tex", content="x", kind="tex", is_main=True)  # mirrored to tree
    return project, m


class TestWorkspaceTree:
    def test_includes_general_and_manuscript_nodes(self):
        project, m = _seed()
        tree = workspace_tree(project)
        rels = {f["rel_path"] for f in tree["files"]}
        assert "Data/readme.md" in rels
        assert f"manuscript-{m.pk}/main.tex" in rels
        # folders include both the user folder and the manuscript root
        names = {f["name"] for f in tree["folders"]}
        assert "Data" in names and f"manuscript-{m.pk}" in names

    def test_node_shape_and_roles(self):
        project, _ = _seed()
        tree = workspace_tree(project)
        for f in tree["files"]:
            assert set(f) == {
                "id",
                "name",
                "rel_path",
                "local_path",
                "kind",
                "role",
                "folder_id",
                "size",
                "is_text",
                "version",
                "versions",
                "description",
                "tags",
            }
        readme = next(f for f in tree["files"] if f["rel_path"] == "Data/readme.md")
        assert readme["role"] == "general" and readme["is_text"] is True

    def test_api_endpoint(self, client):
        project, _ = _seed()
        resp = client.get(f"/api/v1/projects/{project.slug}/tree/", **HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "folders" in data and "files" in data
        assert any(f["rel_path"].endswith("main.tex") for f in data["files"])

    def test_requires_auth(self, client):
        project, _ = _seed()
        assert client.get(f"/api/v1/projects/{project.slug}/tree/").status_code == 401


class TestLocalPaths:
    """Desktop builds tell the explorer where a stored file lives; servers never do."""

    def test_server_mode_reports_no_local_path(self, settings):
        settings.ATLAS_DESKTOP = False
        project, _ = _seed()
        assert all(f["local_path"] is None for f in workspace_tree(project)["files"])

    def test_desktop_mode_reports_the_stored_file_path(self, settings, tmp_path):
        from django.core.files.base import ContentFile

        settings.ATLAS_DESKTOP = True
        settings.MEDIA_ROOT = tmp_path
        project, _ = _seed()
        doc = Document.objects.create(
            project=project, title="notes.txt", rel_path="notes.txt", kind="other"
        )
        doc.file.save("notes.txt", ContentFile(b"hi"), save=True)
        tree = workspace_tree(project)
        by_id = {f["id"]: f for f in tree["files"]}
        assert by_id[doc.id]["local_path"] == doc.file.path
        assert str(tmp_path) in by_id[doc.id]["local_path"]
        # a node without a stored file (manuscript mirror, text-only node) has none
        assert any(f["local_path"] is None for f in tree["files"])
