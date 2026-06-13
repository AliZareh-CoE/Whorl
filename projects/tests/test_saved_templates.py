"""User-saved project templates (file-workspace epic #30, slice 8)."""

import pytest

from documents.models import Document, Folder
from projects.models import ProjectTemplate
from projects.services import (
    instantiate_template,
    save_project_as_template,
    snapshot_project_structure,
)
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _seed_project():
    p = ProjectFactory(name="Source")
    f = Folder.objects.create(project=p, name="analysis")
    Document.objects.create(
        project=p,
        folder=f,
        title="log.md",
        rel_path="analysis/log.md",
        kind="other",
        content="# Log\n",
    )
    Document.objects.create(
        project=p, title="README.md", rel_path="README.md", kind="other", content="# Source\n"
    )
    return p


class TestSnapshotAndApply:
    def test_snapshot_captures_general_tree(self):
        p = _seed_project()
        structure = snapshot_project_structure(p)
        assert "analysis" in structure["folders"]
        assert structure["files"]["analysis/log.md"] == "# Log\n"

    def test_save_and_reinstantiate_into_new_project(self):
        p = _seed_project()
        save_project_as_template(p, "My layout", "snapshot")
        assert ProjectTemplate.objects.filter(name="My layout").exists()
        # apply to a fresh project by the template name
        p2 = ProjectFactory()
        summary = instantiate_template(p2, "My layout")
        assert summary["files"] == 2
        assert Folder.objects.filter(project=p2, name="analysis").exists()
        assert Document.objects.filter(project=p2, rel_path="analysis/log.md").exists()

    def test_snapshot_excludes_manuscript_sources(self):
        from writing.tests.factories import ManuscriptFactory

        p = _seed_project()
        m = ManuscriptFactory(project=p)
        m.files.create(path="main.tex", content="x", kind="tex", is_main=True)  # mirrors
        structure = snapshot_project_structure(p)
        assert not any("manuscript-" in f for f in structure["folders"])
        assert all("manuscript-" not in path for path in structure["files"])


class TestApi:
    def test_save_template_endpoint(self, client):
        p = _seed_project()
        resp = client.post(
            f"/api/v1/projects/{p.slug}/save-template/",
            data={"name": "API layout", "description": "via api"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 201
        assert ProjectTemplate.objects.filter(name="API layout").exists()

    def test_save_template_requires_name(self, client):
        p = _seed_project()
        assert (
            client.post(
                f"/api/v1/projects/{p.slug}/save-template/",
                data={"name": "  "},
                content_type="application/json",
                **HEADERS,
            ).status_code
            == 400
        )

    def test_template_list_merges_saved(self, client):
        p = _seed_project()
        save_project_as_template(p, "Merged layout")
        data = client.get("/api/v1/projects/templates/", **HEADERS).json()
        names = {t["name"] for t in data}
        assert "Merged layout" in names and "Empirical study" in names  # db + code
