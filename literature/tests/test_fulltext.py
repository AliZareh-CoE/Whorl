"""Library v2 slice 8 — search inside your PDFs."""

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command

from core.management.commands.seed_demo import make_demo_pdf
from core.search import search_all
from literature import fulltext, library
from literature.models import Reference, ReferenceText
from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from projects.tests.factories import ProjectFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def papers(db, settings, tmp_path, django_user_model):
    settings.MEDIA_ROOT = tmp_path
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    with_pdf = ReferenceFactory(title="Load theory", bibtex_key="lavie2010load")
    with_pdf.pdf.save(
        "lavie.pdf",
        ContentFile(make_demo_pdf(["Perceptual load gates distractor processing early."])),
        save=True,
    )
    plain = ReferenceFactory(title="Unrelated survey", bibtex_key="smith2020survey")
    ProjectReferenceFactory(project=project, reference=with_pdf)
    return project, with_pdf, plain


def test_saving_a_pdf_indexes_its_text(papers):
    _, ref, plain = papers
    row = ReferenceText.objects.get(reference=ref)
    assert row.page_count == 1 and "Perceptual load" in row.pages[0]
    assert row.source_name == ref.pdf.name and row.error == ""
    assert not ReferenceText.objects.filter(reference=plain).exists()
    # saving again without a new file does not re-extract
    row.body = "stale"
    row.save()
    ref.save()
    assert ReferenceText.objects.get(reference=ref).body == "stale"
    assert fulltext.needs_extraction(ref) is False


def test_corrupt_pdf_records_an_error(papers):
    _, ref, _ = papers
    ref.pdf.save("broken.pdf", ContentFile(b"%PDF-1.4 garbage"), save=True)
    row = ReferenceText.objects.get(reference=ref)
    assert row.error.startswith("Could not read") and row.page_count == 0


def test_search_pages_and_snippets(papers):
    _, ref, _ = papers
    hits = fulltext.search_pages(ref, "DISTRACTOR")
    assert hits == [{"page": 1, "snippet": hits[0]["snippet"]}]
    assert "distractor processing" in hits[0]["snippet"]
    assert fulltext.search_pages(ref, "") == [] and fulltext.search_pages(ref, "zebra") == []


def test_library_filter_and_search_library(papers):
    project, ref, plain = papers
    qs = library.filter_references(Reference.objects.all(), {"q": "distractor"})
    assert [(r.pk, r.pdf_match) for r in qs] == [(ref.pk, True)]
    # a title hit is not a pdf hit
    qs = library.filter_references(Reference.objects.all(), {"q": "survey"})
    assert [(r.pk, r.pdf_match) for r in qs] == [(plain.pk, False)]
    found = fulltext.search_library("perceptual load")
    assert found[0]["reference_id"] == ref.pk and found[0]["page"] == 1
    assert (
        fulltext.search_library("perceptual", queryset=Reference.objects.filter(pk=plain.pk)) == []
    )


def test_global_search_finds_text_inside_pdfs(papers):
    _, ref, _ = papers
    kinds = [(r["type"], r["object"].pk) for r in search_all("distractor")]
    assert ("reference", ref.pk) in kinds


def test_index_command_backfills(papers):
    _, ref, _ = papers
    ReferenceText.objects.all().delete()
    assert fulltext.needs_extraction(ref)
    call_command("index_pdf_text")
    assert ReferenceText.objects.filter(reference=ref).exists()
    assert fulltext.index_missing() == 0


def test_text_search_api(client, papers):
    project, ref, _ = papers
    out = client.get("/api/v1/references/text-search/?q=perceptual&project=deep", **HEADERS)
    assert out.status_code == 200 and out.json()[0]["reference_id"] == ref.pk
    assert (
        client.get("/api/v1/references/text-search/?q=perceptual&project=other", **HEADERS).json()
        == []
    )
    one = client.get(f"/api/v1/references/{ref.pk}/text-search/?q=load", **HEADERS).json()
    assert one[0]["page"] == 1
    listed = client.get("/api/v1/references/?q=distractor", **HEADERS).json()["results"]
    assert [r["id"] for r in listed] == [ref.pk] and listed[0]["pdf_match"] is True
    assert listed[0]["text_status"] == "indexed"
    ReferenceText.objects.all().delete()
    assert client.get(f"/api/v1/references/{ref.pk}/", **HEADERS).json()["text_status"] == "pending"
    redo = client.post(f"/api/v1/references/{ref.pk}/index-text/", **HEADERS)
    assert redo.status_code == 200 and redo.json()["page_count"] == 1
