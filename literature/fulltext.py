"""Search inside your PDFs (Library v2 slice 8).

Every attached PDF is read once with pypdf into `ReferenceText` (a string per page + the joined
body). The workbench search, the global search, and MCP then match on the paper's full text,
report the page, and can jump the reader to it. Extraction never raises: a scanned or corrupt
PDF stores an `error` and the paper simply has no searchable text.
"""

from __future__ import annotations

import io
import re

from django.db.models import Q, QuerySet

from .models import Reference, ReferenceText

MAX_PAGES = 400
MAX_CHARS_PER_PAGE = 20_000
SNIPPET_RADIUS = 90


def extract_text(reference: Reference) -> ReferenceText | None:
    """(Re)extract the PDF text of one reference. Returns the row, or None without a PDF."""
    if not reference.pdf:
        ReferenceText.objects.filter(reference=reference).delete()
        return None
    row, _ = ReferenceText.objects.get_or_create(reference=reference)
    pages: list[str] = []
    error = ""
    try:
        from pypdf import PdfReader

        with reference.pdf.open("rb") as handle:
            data = handle.read()
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages[:MAX_PAGES]:
            text = re.sub(r"[ \t]+", " ", page.extract_text() or "").strip()
            pages.append(text[:MAX_CHARS_PER_PAGE])
        if not any(pages):
            error = "No text layer (scanned PDF?)."
    except Exception as exc:  # corrupt / encrypted / unreadable — never abort the caller
        error = f"Could not read the PDF ({exc.__class__.__name__})."
    row.source_name = reference.pdf.name
    row.pages = pages
    row.body = "\n\n".join(pages)
    row.page_count = len(pages)
    row.char_count = sum(len(p) for p in pages)
    row.error = error
    row.save()
    return row


def needs_extraction(reference: Reference) -> bool:
    """True when the PDF changed (or was never read) since the stored text."""
    if not reference.pdf:
        return False
    row = ReferenceText.objects.filter(reference=reference).only("source_name").first()
    return row is None or row.source_name != reference.pdf.name


def index_missing(queryset: QuerySet | None = None) -> int:
    """Extract text for every reference with a PDF but no (current) text. Returns the count."""
    queryset = queryset if queryset is not None else Reference.objects.all()
    done = 0
    for reference in queryset.exclude(pdf="").exclude(pdf=None).iterator():
        if needs_extraction(reference):
            extract_text(reference)
            done += 1
    return done


def _snippet(page_text: str, start: int, length: int) -> str:
    lo = max(0, start - SNIPPET_RADIUS)
    hi = min(len(page_text), start + length + SNIPPET_RADIUS)
    out = page_text[lo:hi].replace("\n", " ")
    return ("…" if lo > 0 else "") + out + ("…" if hi < len(page_text) else "")


def search_pages(reference: Reference, q: str, limit: int = 20) -> list[dict]:
    """Where `q` occurs inside one paper's PDF: [{page, snippet}], first hit per page first."""
    q = q.strip()
    row = ReferenceText.objects.filter(reference=reference).first()
    if not q or row is None:
        return []
    needle = re.compile(re.escape(q), re.IGNORECASE)
    hits = []
    for number, text in enumerate(row.pages, start=1):
        for m in needle.finditer(text):
            hits.append({"page": number, "snippet": _snippet(text, m.start(), len(q))})
            if len(hits) >= limit:
                return hits
            break  # one snippet per page keeps the list readable
    return hits


def pdf_match_filter(q: str) -> Q:
    """Q object for `filter_references`: papers whose PDF text contains `q`."""
    return Q(text__body__icontains=q)


def search_library(q: str, limit: int = 30, queryset: QuerySet | None = None) -> list[dict]:
    """Papers whose PDF contains `q`, each with its first matching page and snippet."""
    q = q.strip()
    if not q:
        return []
    queryset = queryset if queryset is not None else Reference.objects.all()
    results = []
    for reference in queryset.filter(pdf_match_filter(q)).select_related("text")[:limit]:
        hits = search_pages(reference, q, limit=3)
        results.append(
            {
                "reference_id": reference.pk,
                "title": reference.title,
                "year": reference.year,
                "bibtex_key": reference.bibtex_key,
                "page": hits[0]["page"] if hits else None,
                "snippet": hits[0]["snippet"] if hits else "",
                "pages": [h["page"] for h in hits],
            }
        )
    return results
