"""Matrix v2 — the review matrix as an extraction table."""

import pytest

from literature import matrix
from literature.models import ReviewMark, ReviewTheme
from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
KEY = "k"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture
def world(settings, django_user_model):
    settings.ATLAS_API_KEY = KEY
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    a = ReferenceFactory(
        bibtex_key="lavie2010attention", title="Load", year=2010, authors=[{"family": "Lavie"}]
    )
    b = ReferenceFactory(bibtex_key="smith2020survey", title="Survey", year=2020)
    ProjectReferenceFactory(project=project, reference=a)
    ProjectReferenceFactory(project=project, reference=b)
    return project, a, b


def test_add_theme_and_set_mark(world):
    project, a, b = world
    t = matrix.add_theme(project, "  Sample   size ")
    assert t.name == "Sample size" and t.order == 1
    assert matrix.add_theme(project, "sample size") == t  # case-insensitive reuse
    out = matrix.set_mark(project, "lavie2010attention", "Sample size", note="n=12")
    assert out["marked"] and out["note"] == "n=12" and out["theme_id"] == t.pk
    out = matrix.set_mark(project, a.pk, "Load type", note="perceptual")  # new theme by name
    assert ReviewTheme.objects.get(name="Load type").order == 2
    assert matrix.set_mark(project, a, t, marked=False)["marked"] is False
    assert not ReviewMark.objects.filter(theme=t).exists()
    with pytest.raises(ValueError):
        matrix.set_mark(project, "nobody", t)
    other = ReferenceFactory(bibtex_key="unfiled2021x")
    with pytest.raises(ValueError):
        matrix.set_mark(project, other, t)
    with pytest.raises(ValueError):
        matrix.add_theme(project, "   ")


def test_matrix_table_and_markdown(world):
    project, a, b = world
    matrix.set_mark(project, a, "Sample size", note="n=12")
    matrix.set_mark(project, b, "Sample size")
    matrix.set_mark(project, a, "Load type", note="perceptual")
    table = matrix.matrix(project)
    assert [t["name"] for t in table["themes"]] == ["Sample size", "Load type"]
    assert (
        table["themes"][0]["covered"] == 2
        and table["themes"][1]["covered"] == 1
        and table["papers"] == 2
    )
    row_a = next(r for r in table["rows"] if r["reference_id"] == a.pk)
    assert row_a["covered"] == 2 and row_a["authors"] == "Lavie"
    assert row_a["cells"][str(table["themes"][0]["id"])]["note"] == "n=12"
    assert table["unmarked"] == 0
    md = matrix.matrix_markdown(project)
    assert md.splitlines()[0] == "| Paper | Sample size | Load type |"
    assert "| lavie2010attention | n=12 | perceptual |" in md and "| smith2020survey | ✓ |  |" in md


def test_matrix_api(client, world):
    project, a, b = world
    made = client.post(
        "/api/v1/projects/deep/review-matrix/themes/",
        {"name": "Method"},
        content_type="application/json",
        **HEADERS,
    )
    assert made.status_code == 201
    tid = made.json()["id"]
    cell = client.post(
        "/api/v1/projects/deep/review-matrix/mark/",
        {"reference": "lavie2010attention", "theme": str(tid), "note": "dual-task"},
        content_type="application/json",
        **HEADERS,
    )
    assert cell.status_code == 200 and cell.json()["note"] == "dual-task"
    bad = client.post(
        "/api/v1/projects/deep/review-matrix/mark/",
        {"reference": "ghost", "theme": "x"},
        content_type="application/json",
        **HEADERS,
    )
    assert bad.status_code == 400
    got = client.get("/api/v1/projects/deep/review-matrix/", **HEADERS).json()
    assert got["themes"] == ["Method"] and got["table"]["themes"][0]["covered"] == 1
    renamed = client.patch(
        f"/api/v1/projects/deep/review-matrix/themes/{tid}/",
        {"name": "Methodology"},
        content_type="application/json",
        **HEADERS,
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "Methodology"
    md = client.get("/api/v1/projects/deep/review-matrix/markdown/", **HEADERS)
    assert md.status_code == 200 and "Methodology" in md.content.decode()
    assert (
        client.delete(f"/api/v1/projects/deep/review-matrix/themes/{tid}/", **HEADERS).status_code
        == 204
    )
    assert not ReviewTheme.objects.exists()


@pytest.mark.django_db
def test_suggest_themes_ranks_recurring_phrases_and_skips_existing(client_logged_in):
    from literature.matrix import add_theme, suggest_themes
    from literature.models import ProjectReference
    from literature.tests.factories import ReferenceFactory
    from projects.tests.factories import ProjectFactory

    project = ProjectFactory()
    for i in range(4):
        ref = ReferenceFactory(
            title=f"Working memory load and attention control {i}",
            abstract="Working memory load changes attention control under dual-task demands.",
        )
        ProjectReference.objects.create(project=project, reference=ref)
    names = [s["name"] for s in suggest_themes(project)]
    assert names and all(s["papers"] >= 2 for s in suggest_themes(project))
    top = names[0]
    add_theme(project, top)
    assert top not in [s["name"] for s in suggest_themes(project)]
    data = client_logged_in.get(f"/api/v1/projects/{project.slug}/review-matrix/suggest/").json()
    assert "suggestions" in data and top not in [s["name"] for s in data["suggestions"]]


def test_theme_rows_carry_read_counts(world):
    """#408: the header shows how many marked papers are READ — the gap the queue fills."""
    project, _, _ = world
    theme = ReviewTheme.objects.create(project=project, name="Gap theme")
    links = list(project.project_references.all())
    assert len(links) >= 2
    links[0].reading_status = "read"
    links[0].save()
    links[1].reading_status = "to_read"
    links[1].save()
    for link in links[:2]:
        ReviewMark.objects.create(theme=theme, project_reference=link)
    row = next(t for t in matrix.matrix(project)["themes"] if t["id"] == theme.pk)
    assert row["covered"] == 2 and row["read"] == 1 and row["total"] == len(links)
    src = open("frontend/src/app/pages/Matrix.tsx").read()
    assert 'data-testid="theme-gap-link"' in src and "queue?theme=" in src
