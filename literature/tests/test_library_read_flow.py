"""#450 (backlog #85): the reading flow runs over any filtered Library set, not one queue."""

from pathlib import Path

import pytest
from django.conf import settings

from literature import library
from literature.models import ProjectReference, Reference
from projects.tests.factories import ProjectFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.mark.django_db
def test_flow_honours_filters_and_resolves_the_link(client, owner):
    a_proj, b_proj = ProjectFactory(name="A"), ProjectFactory(name="B")
    both = Reference.objects.create(title="Shared paper", bibtex_key="shared2020", year=2020)
    Reference.objects.create(title="Unfiled paper", bibtex_key="lone2019", year=2019)
    tagged = Reference.objects.create(title="Tagged paper", bibtex_key="tag2021", year=2021)
    ProjectReference.objects.create(project=a_proj, reference=both, reading_status="read")
    unread = ProjectReference.objects.create(
        project=b_proj, reference=both, reading_status="to_read"
    )
    library.bulk([tagged.pk], "tag", value="pilot")
    data = client.get("/api/v1/references/reading-flow/?tag=pilot", **HEADERS).json()
    assert [p["reference"]["bibtex_key"] for p in data["papers"]] == ["tag2021"]
    assert data["papers"][0]["id"] is None and data["papers"][0]["project"] is None
    data = client.get("/api/v1/references/reading-flow/?q=paper&sort=title", **HEADERS).json()
    by = {p["reference"]["bibtex_key"]: p for p in data["papers"]}
    assert by["shared2020"]["id"] == unread.pk and by["shared2020"]["project"] == b_proj.slug
    assert by["lone2019"]["id"] is None
    data = client.get(f"/api/v1/references/reading-flow/?project={a_proj.slug}", **HEADERS).json()
    assert [p["project"] for p in data["papers"]] == [a_proj.slug]
    assert data["papers"][0]["reading_status"] == "read"


def test_ui_wiring():
    app = Path(settings.BASE_DIR) / "frontend" / "src" / "app"
    flow = (app / "pages" / "ReadingFlow.tsx").read_text()
    for needle in (
        "/references/reading-flow/",
        "const libraryMode",
        "in no project yet",
        'navigate("/library")',
    ):
        assert needle in flow, needle
    assert 'path="library/read"' in (app / "main.tsx").read_text()
    lib = (app / "pages" / "Library.tsx").read_text()
    assert 'data-testid="read-these"' in lib and "/library/read?" in lib
