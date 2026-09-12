"""Library v2 import engine: CSL-JSON, RIS, PDF (with DOI sniffing), Zotero local API."""

import json

import httpx
import pytest

from literature import importers, services
from literature.models import Reference
from projects.tests.factories import ProjectFactory

CSL = [
    {
        "id": "smith2020",
        "type": "article-journal",
        "title": "Attention Is Strategic",
        "author": [{"family": "Smith", "given": "Ann"}, {"family": "Lee", "given": "Bo"}],
        "issued": {"date-parts": [[2020, 5]]},
        "container-title": "Journal of Attention",
        "DOI": "10.1000/ATTN.2020",
        "abstract": "We show attention is strategic.",
        "URL": "https://example.org/attn",
    },
    {"id": "x", "type": "book", "title": "Load Theory", "issued": {"date-parts": [[2011]]}},
    {"id": "no-title", "type": "book"},
]

RIS = """TY  - JOUR
TI  - Working Memory and Load
AU  - Lavie, Nilli
AU  - Jane Doe
PY  - 2005
JO  - Cognitive Psychology
DO  - 10.1000/wm.2005
AB  - Load matters.
UR  - https://example.org/wm
ER  -

TY  - CONF
T1  - A Conference Paper
A1  - Roe, Rae
Y1  - 2019/03/01
T2  - Proc. of Things
ER  -
"""


def _pdf_with_text(text: str) -> bytes:
    """A minimal one-page PDF whose content stream draws `text` in Helvetica."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


# --- parsers ---------------------------------------------------------------------------


def test_parse_csl_json_maps_fields_and_skips_untitled():
    metas = importers.parse_csl_json(json.dumps(CSL))
    assert [m["title"] for m in metas] == ["Attention Is Strategic", "Load Theory"]
    first = metas[0]
    assert first["doi"] == "10.1000/attn.2020"  # normalised
    assert first["entry_type"] == "article"
    assert first["authors"] == [
        {"family": "Smith", "given": "Ann"},
        {"family": "Lee", "given": "Bo"},
    ]
    assert first["year"] == 2020 and first["venue"] == "Journal of Attention"
    assert metas[1]["entry_type"] == "book" and metas[1]["year"] == 2011


def test_parse_csl_json_accepts_a_wrapping_object():
    metas = importers.parse_csl_json(json.dumps({"items": CSL[:1]}))
    assert len(metas) == 1


def test_parse_ris_reads_both_tag_dialects():
    metas = importers.parse_ris(RIS)
    assert len(metas) == 2
    wm, conf = metas
    assert wm["title"] == "Working Memory and Load" and wm["year"] == 2005
    assert wm["doi"] == "10.1000/wm.2005" and wm["venue"] == "Cognitive Psychology"
    assert wm["authors"] == [
        {"family": "Lavie", "given": "Nilli"},
        {"family": "Doe", "given": "Jane"},
    ]
    assert conf["entry_type"] == "inproceedings" and conf["year"] == 2019
    assert conf["venue"] == "Proc. of Things"


def test_find_identifiers_in_text():
    doi, arxiv = importers.find_identifiers_in_text(
        "Published in J. Foo. https://doi.org/10.1234/ABC.def-1; see also arXiv:2101.00001v2"
    )
    assert doi == "10.1234/abc.def-1" and arxiv == "2101.00001"
    assert importers.find_identifiers_in_text("nothing here") == (None, None)


def test_sniff_format_by_extension_then_content():
    assert importers.sniff_format("x.pdf", b"") == "pdf"
    assert importers.sniff_format("x", b"%PDF-1.7 ...") == "pdf"
    assert importers.sniff_format("lib.bib", b"") == "bibtex"
    assert importers.sniff_format("paste.txt", b"@article{k, title={T}}") == "bibtex"
    assert importers.sniff_format("paste.txt", b'[{"title": "T"}]') == "csl-json"
    assert importers.sniff_format("paste.txt", b"TY  - JOUR\n") == "ris"
    with pytest.raises(ValueError):
        importers.sniff_format("mystery.xyz", b"hello")


# --- importing -------------------------------------------------------------------------


@pytest.mark.django_db
def test_import_text_csl_creates_dedupes_and_links():
    project = ProjectFactory()
    summary = importers.import_text(json.dumps(CSL), "csl-json", project)
    assert (summary.created, summary.existing, summary.failed) == (2, 0, 0)
    assert project.project_references.count() == 2
    again = importers.import_text(json.dumps(CSL), "csl-json")
    assert (again.created, again.existing) == (0, 2)  # DOI + title/year dedupe
    assert Reference.objects.count() == 2


@pytest.mark.django_db
def test_import_text_ris_and_bibtex():
    ris = importers.import_text(RIS, "ris")
    assert ris.created == 2
    bib = importers.import_text(
        "@article{k, title={Working Memory and Load}, year={2005}}", "bibtex"
    )
    assert bib.created == 0 and bib.existing == 1  # title+year dedupe across formats


@pytest.mark.django_db
def test_find_existing_ignores_short_titles():
    Reference.objects.create(title="Notes", bibtex_key="k1", year=2020)
    assert importers.find_existing({"title": "Notes", "year": 2020}) is None


@pytest.mark.django_db
def test_import_pdf_reads_doi_and_attaches_file(monkeypatch, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    monkeypatch.setattr(
        importers,
        "fetch_metadata_by_doi",
        lambda doi: {
            "doi": doi,
            "title": "Fetched Title",
            "authors": [{"family": "Smith", "given": "A"}],
            "year": 2021,
            "entry_type": "article",
            "extra": {},
        },
    )
    result = importers.import_pdf("paper.pdf", _pdf_with_text("doi:10.1000/pdf.1 rest"))
    ref = Reference.objects.get(pk=result.reference_id)
    assert result.created and not result.needs_metadata
    assert ref.title == "Fetched Title" and ref.doi == "10.1000/pdf.1"
    assert ref.pdf and ref.pdf.name.endswith(".pdf") and ref.extra["source"] == "pdf-import"
    # dropping the same PDF again: no duplicate, file kept
    again = importers.import_pdf("paper.pdf", _pdf_with_text("doi:10.1000/pdf.1 rest"))
    assert again.reference_id == ref.pk and not again.created


@pytest.mark.django_db
def test_import_pdf_without_identifier_keeps_a_stub(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    result = importers.import_pdf("Weird Scan.pdf", _pdf_with_text("Some Interesting Paper Title"))
    ref = Reference.objects.get(pk=result.reference_id)
    assert result.needs_metadata and ref.extra["needs_metadata"] is True
    assert ref.title == "Some Interesting Paper Title"
    assert ref.pdf


@pytest.mark.django_db
def test_import_pdf_when_metadata_fetch_fails_still_keeps_the_paper(
    monkeypatch, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path

    def boom(doi):
        raise services.MetadataError("offline")

    monkeypatch.setattr(importers, "fetch_metadata_by_doi", boom)
    result = importers.import_pdf("p.pdf", _pdf_with_text("doi:10.1000/off.1"))
    ref = Reference.objects.get(pk=result.reference_id)
    assert result.needs_metadata and ref.doi == "10.1000/off.1"
    assert ref.extra["metadata_error"] == "offline"


@pytest.mark.django_db
def test_import_file_dispatches_and_reports_unknown(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    ok = importers.import_file("lib.ris", RIS.encode())
    assert ok.created == 2
    bad = importers.import_file("photo.png", b"\x89PNG")
    assert bad.failed == 1 and "Can't tell" in bad.results[0].error


# --- Zotero -----------------------------------------------------------------------------


def _zotero_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.django_db
def test_import_from_zotero_pages_through_the_local_api():
    calls = []

    def handler(request):
        calls.append(dict(request.url.params))
        start = int(request.url.params.get("start", 0))
        if start == 0:
            return httpx.Response(200, json={"items": [CSL[0]] * 100})
        return httpx.Response(200, json={"items": [CSL[1]]})

    summary = importers.import_from_zotero(client=_zotero_client(handler))
    assert len(calls) == 2 and calls[0]["format"] == "csljson"
    assert summary.created == 2 and summary.existing == 99
    assert Reference.objects.get(title="Load Theory").extra["source"] == "zotero"


def test_import_from_zotero_explains_when_zotero_is_closed():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(importers.ZoteroUnavailable, match="Allow other applications"):
        importers.fetch_zotero_items(client=_zotero_client(handler))


def test_import_from_zotero_explains_a_disabled_api():
    def handler(request):
        return httpx.Response(403, text="nope")

    with pytest.raises(importers.ZoteroUnavailable, match="HTTP 403"):
        importers.fetch_zotero_items(client=_zotero_client(handler))
