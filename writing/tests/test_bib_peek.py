"""#448 (backlog #126): the studio's bibliography rail can peek at a paper's abstract."""

from pathlib import Path

import pytest
from django.conf import settings

from literature.models import Reference
from writing.models import ManuscriptReference
from writing.tests.factories import ManuscriptFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.mark.django_db
def test_bibliography_rows_carry_the_abstract(client, settings, django_user_model):
    settings.ATLAS_API_KEY = KEY
    django_user_model.objects.create_superuser("owner", password="pw")
    ms = ManuscriptFactory()
    ref = Reference.objects.create(title="T", bibtex_key="t2020", abstract="A long abstract.")
    ManuscriptReference.objects.create(manuscript=ms, reference=ref)
    rows = client.get(f"/api/v1/manuscripts/{ms.pk}/bibliography/", **HEADERS).json()
    assert rows[0]["abstract"] == "A long abstract."


def test_rail_and_projects_wiring():
    app = Path(settings.BASE_DIR) / "frontend" / "src" / "app"
    studio = (app / "pages" / "Studio.tsx").read_text()
    for needle in ('data-testid="bib-peek"', 'data-testid="bib-abstract"', "abstract?: string"):
        assert needle in studio, needle
    projects = (app / "pages" / "Projects.tsx").read_text()  # #64: hover prefetch
    assert "prefetchQuery" in projects and '["overview", p.slug]' in projects
