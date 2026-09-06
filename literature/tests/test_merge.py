"""Library v2 slice 6: duplicate clusters and merging with every relation carried over."""

import pytest
from django.core.files.base import ContentFile

from literature import library
from literature.models import CitationEdge, LibraryTag, ProjectReference, Reference
from notes.models import Note
from projects.tests.factories import ProjectFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.fixture
def dupes(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    a = Reference.objects.create(
        title="Perceptual load as a necessary condition",
        bibtex_key="a",
        doi="10.1/load",
        year=1995,
        abstract="x",
    )
    b = Reference.objects.create(
        title="Perceptual Load as a Necessary Condition.", bibtex_key="b", year=1995
    )
    c = Reference.objects.create(
        title="PERCEPTUAL LOAD AS A NECESSARY CONDITION",  # same title, different case
        bibtex_key="c",
        venue="JEP:HPP",
    )
    d = Reference.objects.create(title="An unrelated paper on memory", bibtex_key="d", year=2001)
    b.pdf.save("b.pdf", ContentFile(b"%PDF-1.4"), save=True)
    return a, b, c, d


def test_duplicate_groups_cluster_by_doi_and_title(dupes):
    a, b, c, d = dupes
    groups = library.duplicate_groups()
    assert len(groups) == 1
    g = groups[0]
    assert {m["id"] for m in g["members"]} == {a.pk, b.pk, c.pk}
    assert g["reasons"] == [
        "title"
    ]  # DOIs are unique in the database, so title/arXiv are the live signals
    assert g["keep"] == b.pk  # the one with a PDF scores highest
    assert library.facets(Reference.objects.all())["duplicates"] == 3


def test_duplicate_groups_cluster_by_arxiv(db):
    x = Reference.objects.create(title="Alpha version title", bibtex_key="x", arxiv_id="2101.00001")
    y = Reference.objects.create(
        title="Totally different words", bibtex_key="y", arxiv_id="2101.00001"
    )
    groups = library.duplicate_groups()
    assert {m["id"] for m in groups[0]["members"]} == {x.pk, y.pk} and groups[0]["reasons"] == [
        "arxiv"
    ]


def test_merge_moves_every_relation(dupes, settings):
    a, b, c, d = dupes
    p1, p2 = ProjectFactory(), ProjectFactory()
    ProjectReference.objects.create(
        project=p1, reference=a, reading_status="read", priority="high", notes="from a"
    )
    ProjectReference.objects.create(
        project=p1, reference=b, reading_status="skimmed", notes="from b"
    )
    ProjectReference.objects.create(project=p2, reference=c, reading_status="annotated")
    tag = LibraryTag.get_or_create_named("load")
    b.tags.add(tag)
    note = Note.objects.create(project=p1, title="N", body="")
    note.references.add(b)
    CitationEdge.objects.create(citing=b, cited=d)
    CitationEdge.objects.create(citing=d, cited=c)
    CitationEdge.objects.create(citing=a, cited=d)  # duplicate edge once merged → dropped
    out = library.merge_references(a.pk, [b.pk, c.pk])
    a.refresh_from_db()
    assert out["kept"] == a.pk and sorted(out["merged"]) == sorted([b.pk, c.pk])
    assert not Reference.objects.filter(pk__in=[b.pk, c.pk]).exists()
    # project links: p1 kept (best status/priority/notes merged), p2 moved over
    link1 = ProjectReference.objects.get(project=p1, reference=a)
    assert link1.reading_status == "read" and link1.priority == "high" and "from b" in link1.notes
    assert ProjectReference.objects.get(project=p2, reference=a).reading_status == "annotated"
    assert out["moved"]["project_links"] == 1
    assert list(a.tags.values_list("name", flat=True)) == ["load"]
    assert list(note.references.all()) == [a]
    assert a.pdf and a.pdf.name.endswith("b.pdf") and out["moved"]["pdf"] is True
    edges = {(e.citing_id, e.cited_id) for e in CitationEdge.objects.all()}
    assert edges == {(a.pk, d.pk), (d.pk, a.pk)}
    assert sorted(a.extra["merged_from"]) == ["b", "c"]
    assert (
        a.doi == "10.1/load" and a.abstract == "x" and a.venue == "JEP:HPP"
    )  # empty fields filled from c


def test_merge_requires_something_to_merge(dupes):
    a, b, c, d = dupes
    with pytest.raises(ValueError):
        library.merge_references(a.pk, [a.pk])


@pytest.mark.django_db
def test_duplicates_and_merge_endpoints(client, owner, dupes):
    a, b, c, d = dupes
    groups = client.get("/api/v1/references/duplicates/", **HEADERS).json()["groups"]
    assert len(groups) == 1 and groups[0]["keep"] == b.pk
    out = client.post(
        "/api/v1/references/merge/",
        {"keep": b.pk, "merge": [a.pk, c.pk]},
        content_type="application/json",
        **HEADERS,
    ).json()
    assert out["kept"] == b.pk and Reference.objects.count() == 2
    assert (
        client.post(
            "/api/v1/references/merge/",
            {"keep": 999999, "merge": [d.pk]},
            content_type="application/json",
            **HEADERS,
        ).status_code
        == 404
    )
    assert client.get("/api/v1/references/duplicates/", **HEADERS).json()["groups"] == []


def test_ui_wiring():
    from pathlib import Path

    from django.conf import settings

    src = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Library.tsx"
    ).read_text()
    for needle in ("/references/duplicates/", "/references/merge/", "Merge into", "Duplicates"):
        assert needle in src, needle


def test_similar_titles_with_different_years_are_not_duplicates(db):
    Reference.objects.create(
        title="Study of Attention and Memory Interaction 5", bibtex_key="s5", year=1999
    )
    Reference.objects.create(
        title="Study of Attention and Memory Interaction 7", bibtex_key="s7", year=2001
    )
    Reference.objects.create(
        title="Study of Attention and Memory Interaction 8", bibtex_key="s8", year=2001
    )
    groups = library.duplicate_groups()
    assert len(groups) == 1 and {m["bibtex_key"] for m in groups[0]["members"]} == {"s7", "s8"}
