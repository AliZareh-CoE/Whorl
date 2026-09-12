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


class TestResearchScaffold:
    """#438: a template also lays down a plan, questions and review themes — once."""

    def test_empirical_plans_questions_and_themes(self):
        from literature.models import ReviewTheme
        from plans.models import Milestone, Phase, ResearchQuestion, Task

        p = ProjectFactory(name="Memory Study")
        summary = instantiate_template(p, "empirical")
        assert summary["phases"] == 4 and summary["questions"] == 2 and summary["themes"] == 4
        phases = list(Phase.objects.filter(project=p).order_by("order"))
        assert [ph.name for ph in phases] == [
            "Literature & hypotheses",
            "Design & pilot",
            "Data collection",
            "Analysis & write-up",
        ]
        assert phases[0].objective.startswith("Read into the question")
        assert Milestone.objects.filter(phase__project=p).count() == 10
        assert Task.objects.filter(
            milestone__phase__project=p, title="Ethics / approval in place"
        ).exists()
        assert ResearchQuestion.objects.filter(project=p).count() == 2
        assert list(ReviewTheme.objects.filter(project=p).values_list("name", flat=True)) == [
            "Theory",
            "Method",
            "Key finding",
            "Limitation",
        ]

    def test_never_duplicates_and_respects_existing_plan(self):
        from literature.models import ReviewTheme
        from plans.models import Phase, ResearchQuestion

        p = ProjectFactory()
        Phase.objects.create(project=p, name="Mine", order=1)
        again = instantiate_template(p, "empirical")
        assert again["phases"] == 0 and Phase.objects.filter(project=p).count() == 1
        assert again["questions"] == 2 and again["themes"] == 4
        third = instantiate_template(p, "empirical")
        assert third["questions"] == 0 and third["themes"] == 0
        assert ResearchQuestion.objects.filter(project=p).count() == 2
        assert ReviewTheme.objects.filter(project=p).count() == 4

    def test_every_template_outline_parses(self):
        from plans.outline import parse_outline

        for key, template in TEMPLATES.items():
            specs = parse_outline(template["plan"])
            assert specs, key
            assert all(ps.milestones or key == "minimal" for ps in specs), key

    def test_template_list_counts(self, client):
        data = client.get("/api/v1/projects/templates/", **HEADERS).json()
        emp = next(t for t in data if t["key"] == "empirical")
        assert emp["phases"] == 4 and emp["milestones"] == 10
        assert emp["questions"] == 2 and emp["themes"] == 4

    def test_create_via_api_with_template_plans(self, client):
        from plans.models import Phase

        r = client.post(
            "/api/v1/projects/",
            {"name": "Reviewed", "status": "active", "template": "review"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 201, r.content
        assert Phase.objects.filter(project__slug=r.json()["slug"]).count() == 4

    def test_new_project_page_says_so(self):
        from pathlib import Path

        from django.conf import settings

        src = (
            Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "NewProject.tsx"
        ).read_text()
        assert 'data-testid="template-plan"' in src and "review theme" in src
