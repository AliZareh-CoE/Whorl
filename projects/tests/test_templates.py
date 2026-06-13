"""Project templates scaffold organized folders (file-workspace epic #30, slice 7)."""

import pytest

from documents.models import Document, Folder
from projects.project_templates import TEMPLATES, template_choices, template_list
from projects.services import instantiate_template
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    settings.ATLAS_API_KEY = KEY


class TestInstantiate:
    def test_empirical_creates_nested_tree(self):
        p = ProjectFactory(name="Memory Study")
        summary = instantiate_template(p, "empirical")
        assert summary["files"] == 4
        names = set(Folder.objects.filter(project=p).values_list("name", flat=True))
        assert {"literature", "data", "raw", "analysis", "manuscript", "notes"} <= names
        readme = Document.objects.get(project=p, rel_path="README.md")
        assert "Memory Study" in readme.content  # {name} interpolated
        assert readme.kind == "other" and readme.role == "general"
        # nested file landed under its folder
        assert Document.objects.filter(project=p, rel_path="data/DATA-DICTIONARY.md").exists()

    def test_idempotent(self):
        p = ProjectFactory()
        instantiate_template(p, "empirical")
        before = Document.objects.filter(project=p).count()
        again = instantiate_template(p, "empirical")
        assert again["files"] == 0
        assert Document.objects.filter(project=p).count() == before

    def test_unknown_key_is_noop(self):
        p = ProjectFactory()
        assert instantiate_template(p, "nope") == {"folders": 0, "files": 0}
        assert Folder.objects.filter(project=p).count() == 0

    def test_every_template_instantiates(self):
        for key in TEMPLATES:
            p = ProjectFactory()
            summary = instantiate_template(p, key)
            assert summary["files"] >= 1


class TestApi:
    def test_template_list_endpoint(self, client):
        data = client.get("/api/v1/projects/templates/", **HEADERS).json()
        keys = {t["key"] for t in data}
        assert "empirical" in keys
        assert all({"key", "name", "description", "folders"} <= set(t) for t in data)

    def test_create_with_template_scaffolds(self, client):
        resp = client.post(
            "/api/v1/projects/",
            data={"name": "Scaffolded", "slug": "scaffolded", "template": "minimal"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 201
        assert Folder.objects.filter(project__slug="scaffolded", name="notes").exists()


def test_choices_include_empty_and_all():
    keys = [c[0] for c in template_choices()]
    assert keys[0] == "" and set(TEMPLATES) <= set(keys)
    assert len(template_list()) == len(TEMPLATES)
