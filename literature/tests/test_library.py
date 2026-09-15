"""Library v2 query layer: filters, facets, bulk actions, metadata recovery."""

import httpx
import pytest

from literature import library
from literature.models import ProjectReference, Reference
from literature.services import MetadataError
from projects.tests.factories import ProjectFactory


@pytest.fixture
def refs(db):
    a = Reference.objects.create(
        title="Attention and Load",
        bibtex_key="a",
        year=2020,
        venue="J Attn",
        entry_type="article",
        authors=[{"family": "Lavie", "given": "N"}],
        doi="10.1/a",
    )
    b = Reference.objects.create(
        title="Memory Capacity Limits",
        bibtex_key="b",
        year=2018,
        venue="Cog Psych",
        entry_type="article",
        authors=[{"family": "Cowan", "given": "N"}],
    )
    c = Reference.objects.create(
        title="A Scanned Stub",
        bibtex_key="c",
        year=None,
        entry_type="misc",
        extra={"needs_metadata": True},
    )
    from django.core.files.base import ContentFile

    b.pdf.save("b.pdf", ContentFile(b"%PDF-1.4 fake"), save=True)
    return a, b, c


def _params(**kw):
    return {k: str(v) for k, v in kw.items()}


def test_filter_q_searches_title_venue_authors_doi(refs):
    a, b, c = refs
    assert list(library.filter_references(Reference.objects.all(), _params(q="lavie"))) == [a]
    assert list(library.filter_references(Reference.objects.all(), _params(q="cog psych"))) == [b]
    assert list(library.filter_references(Reference.objects.all(), _params(q="10.1/a"))) == [a]


def test_filter_year_pdf_type_needs_metadata_unfiled(refs):
    a, b, c = refs
    qs = Reference.objects.all()
    assert list(library.filter_references(qs, _params(year=2018))) == [b]
    assert list(library.filter_references(qs, _params(year_min=2019))) == [a]
    assert list(library.filter_references(qs, _params(has_pdf="true"))) == [b]
    assert set(library.filter_references(qs, _params(has_pdf="false"))) == {a, c}
    assert list(library.filter_references(qs, _params(needs_metadata="true"))) == [c]
    project = ProjectFactory()
    ProjectReference.objects.create(project=project, reference=a, reading_status="read")
    assert list(library.filter_references(qs, _params(project=project.slug))) == [a]
    assert list(
        library.filter_references(qs, _params(project=project.slug, reading_status="read"))
    ) == [a]
    assert (
        list(library.filter_references(qs, _params(project=project.slug, reading_status="to_read")))
        == []
    )
    assert set(library.filter_references(qs, _params(unfiled="true"))) == {b, c}


def test_filter_sorts(refs):
    a, b, c = refs
    qs = Reference.objects.all()
    assert list(library.filter_references(qs, _params(sort="year"))) == [a, b, c]
    assert list(library.filter_references(qs, _params(sort="title")))[0] == c
    assert list(library.filter_references(qs, _params(sort="nonsense")))[0] == c  # newest first


def test_facets_shape(refs):
    a, b, c = refs
    project = ProjectFactory(name="P")
    ProjectReference.objects.create(project=project, reference=a)
    f = library.facets(Reference.objects.all())
    assert f["total"] == 3 and f["with_pdf"] == 1 and f["without_pdf"] == 2
    assert f["needs_metadata"] == 1 and f["unfiled"] == 2
    assert [y["year"] for y in f["years"]] == [2018, 2020]
    assert f["entry_types"][0] == {"entry_type": "article", "count": 2}
    assert {v["venue"] for v in f["venues"]} == {"J Attn", "Cog Psych"}
    assert f["projects"] == [{"slug": project.slug, "name": "P", "count": 1}]
    assert f["all_projects"][0]["slug"] == project.slug


def test_bulk_link_status_unlink_delete(refs):
    a, b, c = refs
    project = ProjectFactory()
    out = library.bulk([a.pk, b.pk], "link", project.slug)
    assert out["affected"] == 2 and project.project_references.count() == 2
    assert library.bulk([a.pk], "link", project.slug)["affected"] == 0  # idempotent
    out = library.bulk([a.pk, b.pk], "status", project.slug, "read")
    assert out["affected"] == 2
    assert set(project.project_references.values_list("reading_status", flat=True)) == {"read"}
    assert library.bulk([a.pk], "priority", project.slug, "high")["affected"] == 1
    with pytest.raises(ValueError):
        library.bulk([a.pk], "status", project.slug, "bogus")
    with pytest.raises(ValueError):
        library.bulk([a.pk], "link")  # no project
    assert library.bulk([a.pk], "unlink", project.slug)["affected"] == 1
    assert library.bulk([c.pk], "delete")["affected"] == 1
    assert not Reference.objects.filter(pk=c.pk).exists()


def _crossref(items):
    def handler(request):
        assert "query.title" in request.url.params
        return httpx.Response(200, json={"message": {"items": items}})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_find_metadata_by_title_updates_a_stub(refs):
    a, b, c = refs
    c.title = "Working Memory Capacity and Attention Control"
    c.save()
    work = {
        "DOI": "10.5/found",
        "title": ["Working memory capacity and attention control"],
        "author": [{"family": "Engle", "given": "R"}],
        "issued": {"date-parts": [[2002]]},
        "container-title": ["Current Directions"],
        "type": "journal-article",
    }
    assert library.find_metadata(c, client=_crossref([work])) is True
    c.refresh_from_db()
    assert c.doi == "10.5/found" and c.year == 2002 and c.authors[0]["family"] == "Engle"
    assert "needs_metadata" not in c.extra


def test_find_metadata_refuses_a_poor_title_match(refs):
    a, b, c = refs
    c.title = "Completely Different Words Here Please"
    c.save()
    work = {
        "DOI": "10.5/no",
        "title": ["Something else entirely"],
        "author": [],
        "issued": {"date-parts": [[2000]]},
    }
    with pytest.raises(MetadataError, match="No confident match"):
        library.find_metadata(c, client=_crossref([work]))


def test_find_metadata_by_doi_uses_the_doi_path(refs, monkeypatch):
    a, b, c = refs
    monkeypatch.setattr(
        library,
        "fetch_metadata_by_doi",
        lambda doi: {"doi": doi, "title": "Refreshed", "extra": {}},
    )
    assert library.find_metadata(a) is True
    a.refresh_from_db()
    assert a.title == "Refreshed"


def test_find_metadata_refuses_to_collide_with_an_existing_doi(refs):
    a, b, c = refs
    c.title = "Attention and Load"
    c.save()
    work = {
        "DOI": "10.1/a",
        "title": ["Attention and Load"],
        "author": [],
        "issued": {"date-parts": [[2020]]},
    }
    with pytest.raises(MetadataError, match="already has DOI"):
        library.find_metadata(c, client=_crossref([work]))


def test_bulk_find_metadata_collects_errors(refs, monkeypatch):
    a, b, c = refs

    def fake(ref, client=None):
        if ref.pk == c.pk:
            raise MetadataError("nope")
        return True

    monkeypatch.setattr(library, "find_metadata", fake)
    out = library.bulk([a.pk, c.pk], "find_metadata")
    assert out["affected"] == 1 and len(out["errors"]) == 1


# #524: the author lens


def test_filter_author_matches_family_case_insensitively(refs):
    a, b, c = refs
    b.authors = [{"family": "Cowan", "given": "N"}, {"family": "Lavie", "given": "Nilli"}]
    b.save(update_fields=["authors"])
    c.authors = ["not a dict", {"given": "Anonymous"}]  # malformed rows are skipped
    c.save(update_fields=["authors"])
    ids = {r.pk for r in library.filter_references(Reference.objects.all(), {"author": "lavie"})}
    assert ids == {a.pk, b.pk}
    ids = {r.pk for r in library.filter_references(Reference.objects.all(), {"author": "COWAN"})}
    assert ids == {b.pk}
    assert not library.filter_references(Reference.objects.all(), {"author": "Nobody"}).exists()
    # combines with the other filters
    rows = library.filter_references(Reference.objects.all(), {"author": "Lavie", "year": "2018"})
    assert [r.pk for r in rows] == [b.pk]
    # blank and whitespace are no filter
    assert library.filter_references(Reference.objects.all(), {"author": "  "}).count() == 3


def test_author_facet_counts_papers_not_bylines(refs):
    a, b, c = refs
    b.authors = [
        {"family": "Cowan", "given": "N"},
        {"family": "lavie", "given": "Nilli"},
        {"family": "Lavie", "given": "Nilli"},  # the same person twice on one paper: one count
    ]
    b.save(update_fields=["authors"])
    rows = library.author_facet(Reference.objects.all())
    assert rows[0] == {"name": "Lavie", "given": "Nilli", "count": 2}
    assert rows[1] == {"name": "Cowan", "given": "N", "count": 1}
    assert library.author_facet(Reference.objects.all(), limit=1) == rows[:1]
    f = library.facets(Reference.objects.all())
    assert f["authors"] == rows


def test_api_author_filter_and_facet(client, refs, settings, owner):
    a, b, c = refs
    settings.ATLAS_API_KEY = "k"
    headers = {"HTTP_HOST": "127.0.0.1", "HTTP_X_API_KEY": "k"}
    resp = client.get("/api/v1/references/?author=lavie", **headers)
    assert resp.status_code == 200, resp.content[:300]
    data = resp.json()
    assert [r["id"] for r in data["results"]] == [a.pk]
    data = client.get("/api/v1/references/facets/", **headers).json()
    assert {"name": "Lavie", "given": "N", "count": 1} in data["authors"]
    # the reading flow honours it too
    data = client.get("/api/v1/references/reading-flow/?author=Lavie", **headers).json()
    assert [p["reference"]["id"] for p in data["papers"]] == [a.pk]


def test_project_facet_counts_papers_with_identical_bylines(client, refs, settings, owner):
    """The facets action uses .distinct() for a project; two papers by the same single author
    must still count as two (SELECT DISTINCT authors would fold them)."""
    a, b, c = refs
    project = ProjectFactory(name="P")
    twin = Reference.objects.create(
        title="Load, again", bibtex_key="lavie-twin", year=2021, authors=a.authors
    )
    for ref in (a, twin, b):
        ProjectReference.objects.create(project=project, reference=ref)
    settings.ATLAS_API_KEY = "k"
    headers = {"HTTP_HOST": "127.0.0.1", "HTTP_X_API_KEY": "k"}
    data = client.get(f"/api/v1/references/facets/?project={project.slug}", **headers).json()
    assert data["authors"][0] == {"name": "Lavie", "given": "N", "count": 2}
    assert data["total"] == 3
