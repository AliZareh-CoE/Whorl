"""Writing v2 slice 1 — manuscript studio API: bibliography, cite check, bib, events."""

import pytest

from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from projects.tests.factories import ProjectFactory
from writing.models import Manuscript, ManuscriptFile, SubmissionEvent

pytestmark = pytest.mark.django_db
KEY = "k"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture
def world(settings, django_user_model):
    settings.ATLAS_API_KEY = KEY
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    lavie = ReferenceFactory(
        bibtex_key="lavie2010attention",
        title="Load theory",
        year=2010,
        authors=[{"family": "Lavie"}],
    )
    smith = ReferenceFactory(bibtex_key="smith2020survey", title="A survey")
    ProjectReferenceFactory(project=project, reference=lavie)
    manuscript = Manuscript.objects.create(project=project, title="Load paper", status="drafting")
    return project, manuscript, lavie, smith


def test_bibliography_add_list_remove(client, world):
    _, m, lavie, smith = world
    assert client.get(f"/api/v1/manuscripts/{m.pk}/bibliography/", **HEADERS).json() == []
    added = client.post(
        f"/api/v1/manuscripts/{m.pk}/bibliography/",
        {"reference": lavie.pk},
        content_type="application/json",
        **HEADERS,
    )
    assert added.status_code == 200 and added.json()[0]["cite_key"] == "lavie2010attention"
    assert added.json()[0]["authors"] == "Lavie" and added.json()[0]["year"] == 2010
    # idempotent + override
    again = client.post(
        f"/api/v1/manuscripts/{m.pk}/bibliography/",
        {"reference": lavie.pk, "cite_key_override": "lavie10"},
        content_type="application/json",
        **HEADERS,
    )
    assert len(again.json()) == 1 and again.json()[0]["cite_key"] == "lavie10"
    client.post(
        f"/api/v1/manuscripts/{m.pk}/bibliography/",
        {"reference": smith.pk},
        content_type="application/json",
        **HEADERS,
    )
    bib = client.get(f"/api/v1/manuscripts/{m.pk}/bib/", **HEADERS)
    assert bib.status_code == 200 and bib["Content-Type"].startswith("text/x-bibtex")
    assert "@" in bib.content.decode() and "lavie10" in bib.content.decode()
    gone = client.delete(f"/api/v1/manuscripts/{m.pk}/bibliography/{smith.pk}/", **HEADERS)
    assert gone.status_code == 204
    assert [
        r["reference_id"]
        for r in client.get(f"/api/v1/manuscripts/{m.pk}/bibliography/", **HEADERS).json()
    ] == [lavie.pk]


def test_cite_check_over_tex_files(client, world):
    _, m, lavie, smith = world
    client.post(
        f"/api/v1/manuscripts/{m.pk}/bibliography/",
        {"reference": lavie.pk},
        content_type="application/json",
        **HEADERS,
    )
    ManuscriptFile.objects.create(
        manuscript=m,
        path="main.tex",
        content=r"Intro \cite{lavie2010attention, smith2020survey} and \citep{ghost99}.",
        is_main=True,
    )
    ManuscriptFile.objects.create(
        manuscript=m, path="sections/method.tex", content=r"\textcite{lavie2010attention}"
    )
    out = client.get(f"/api/v1/manuscripts/{m.pk}/cite-check/", **HEADERS).json()
    assert out["tex_files"] == 2 and out["matched"] == ["lavie2010attention"]
    assert out["missing_from_bib"] == ["ghost99", "smith2020survey"] and out["uncited_in_bib"] == []
    assert out["resolvable"] == {"smith2020survey": smith.pk}
    # without files it falls back to latex_source
    ManuscriptFile.objects.all().delete()
    m.latex_source = r"\cite{lavie2010attention}"
    m.save()
    out = client.get(f"/api/v1/manuscripts/{m.pk}/cite-check/", **HEADERS).json()
    # Manuscript.save() mirrors latex_source into a main file, so the count may be 0 or 1
    assert out["tex_files"] in (0, 1) and out["matched"] == ["lavie2010attention"]


def test_events_add_and_delete(client, world):
    _, m, _, _ = world
    made = client.post(
        f"/api/v1/manuscripts/{m.pk}/events/",
        {"kind": "submitted", "date": "2026-09-06", "notes": "to JEP"},
        content_type="application/json",
        **HEADERS,
    )
    assert made.status_code == 201 and made.json()["kind"] == "submitted"
    bad = client.post(
        f"/api/v1/manuscripts/{m.pk}/events/",
        {"kind": "party", "date": "2026-09-06"},
        content_type="application/json",
        **HEADERS,
    )
    assert bad.status_code == 400
    detail = client.get(f"/api/v1/manuscripts/{m.pk}/", **HEADERS).json()
    assert detail["events"][0]["notes"] == "to JEP"
    assert (
        client.delete(
            f"/api/v1/manuscripts/{m.pk}/events/{made.json()['id']}/", **HEADERS
        ).status_code
        == 204
    )
    assert not SubmissionEvent.objects.exists()


def test_create_manuscript_through_api(client, world):
    project, _, _, _ = world
    made = client.post(
        "/api/v1/manuscripts/",
        {"project": "deep", "title": "New paper", "status": "idea"},
        content_type="application/json",
        **HEADERS,
    )
    assert made.status_code == 201 and made.json()["project_name"] == project.name


def test_related_changes_bump_the_manuscript_etag(client, world):
    _, m, lavie, _ = world
    first = client.get(f"/api/v1/manuscripts/{m.pk}/", **HEADERS)
    etag = first["ETag"]
    client.post(
        f"/api/v1/manuscripts/{m.pk}/events/",
        {"kind": "note", "date": "2026-09-06"},
        content_type="application/json",
        **HEADERS,
    )
    again = client.get(f"/api/v1/manuscripts/{m.pk}/", HTTP_IF_NONE_MATCH=etag, **HEADERS)
    assert again.status_code == 200 and again["ETag"] != etag  # not a stale 304
    etag = again["ETag"]
    client.post(
        f"/api/v1/manuscripts/{m.pk}/bibliography/",
        {"reference": lavie.pk},
        content_type="application/json",
        **HEADERS,
    )
    assert (
        client.get(f"/api/v1/manuscripts/{m.pk}/", HTTP_IF_NONE_MATCH=etag, **HEADERS).status_code
        == 200
    )
