"""#437 (backlog #62): a Related-work LaTeX section drafted from the review matrix."""

import pytest

from literature.models import ProjectReference, Reference, ReviewMark, ReviewTheme
from literature.selectors import related_work_latex
from projects.tests.factories import ProjectFactory
from writing.models import ManuscriptFile, ManuscriptReference
from writing.tests.factories import ManuscriptFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.fixture
def matrix(db):
    project = ProjectFactory(name="Attention & Load")
    a = Reference.objects.create(title="Load theory", bibtex_key="lavie2005", year=2005)
    b = Reference.objects.create(title="Capacity", bibtex_key="cowan2001", year=2001)
    c = Reference.objects.create(title="Unthemed", bibtex_key="norman1995", year=1995)
    la, lb, _lc = (ProjectReference.objects.create(project=project, reference=r) for r in (a, b, c))
    load = ReviewTheme.objects.create(project=project, name="Perceptual load", order=1)
    ReviewTheme.objects.create(project=project, name="Pupillometry", order=2)
    ReviewMark.objects.create(
        theme=load, project_reference=la, note="Load gates distractors early."
    )
    ReviewMark.objects.create(theme=load, project_reference=lb)
    return project, a, b, c


def test_latex_has_sections_findings_bare_cites_and_gaps(matrix):
    project, a, b, c = matrix
    tex, cited = related_work_latex(project)
    assert "\\section{Related work}" in tex
    assert "\\subsection{Perceptual load}" in tex and "\\subsection{Pupillometry}" in tex
    assert "Load gates distractors early~\\citep{lavie2005}." in tex
    assert "Further work on perceptual load includes~\\citep{cowan2001}." in tex
    assert "% No papers marked under this theme yet" in tex
    assert "% Not yet themed" in tex and "norman1995" in tex
    assert {r.bibtex_key for r in cited} == {"lavie2005", "cowan2001"}


def test_escapes_latex_specials(db):
    project = ProjectFactory(name="R&D 100%")
    ref = Reference.objects.create(title="T", bibtex_key="k2020", year=2020)
    link = ProjectReference.objects.create(project=project, reference=ref)
    theme = ReviewTheme.objects.create(project=project, name="Cost_benefit & risk")
    ReviewMark.objects.create(theme=theme, project_reference=link, note="Saves $5 & 10% time")
    tex, _ = related_work_latex(project)
    assert "\\subsection{Cost\\_benefit \\& risk}" in tex
    assert "Saves \\$5 \\& 10\\% time~\\citep{k2020}." in tex
    assert "R\\&D 100\\%" in tex


@pytest.mark.django_db
def test_endpoint_writes_the_file_links_the_bibliography_and_guards_overwrite(
    client, owner, matrix
):
    project, a, b, c = matrix
    manuscript = ManuscriptFactory(project=project, title="Paper")
    url = f"/api/v1/manuscripts/{manuscript.pk}/related-work/"
    r = client.post(url, {}, content_type="application/json", **HEADERS)
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["path"] == "sections/related-work.tex"
    assert body["input_line"] == "\\input{sections/related-work}"
    assert body["cited"] == 2 and body["linked_new"] == 2 and body["themes"] == 2
    file = ManuscriptFile.objects.get(pk=body["file_id"])
    assert file.kind == "tex" and "\\citep{lavie2005}" in file.content
    assert set(
        ManuscriptReference.objects.filter(manuscript=manuscript).values_list(
            "reference__bibtex_key", flat=True
        )
    ) == {"lavie2005", "cowan2001"}
    again = client.post(url, {}, content_type="application/json", **HEADERS)
    assert again.status_code == 409
    forced = client.post(url, {"overwrite": True}, content_type="application/json", **HEADERS)
    assert forced.status_code == 200 and forced.json()["linked_new"] == 0
    assert ManuscriptFile.objects.filter(manuscript=manuscript).count() == 1
    bad = client.post(url, {"path": "notes.txt"}, content_type="application/json", **HEADERS)
    assert bad.status_code == 400


def test_mcp_tool_posts_to_the_endpoint(monkeypatch):
    from mcp_server import client as mcp_client
    from mcp_server import server

    seen = {}
    monkeypatch.setattr(
        mcp_client, "_request", lambda method, path, **kw: seen.update(kw, path=path) or {}
    )
    server.draft_related_work(4, overwrite=True)
    assert seen["path"] == "/manuscripts/4/related-work/" and seen["json"] == {"overwrite": True}


def test_matrix_page_wiring():
    from pathlib import Path

    from django.conf import settings

    src = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Matrix.tsx"
    ).read_text()
    for needle in ("/related-work/", 'data-testid="to-manuscript"', "overwrite: true", "/editor"):
        assert needle in src, needle
