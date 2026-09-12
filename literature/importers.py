"""Library import engine (Library v2, slice 1): bring papers in from anywhere.

Every path ends in `create_reference_from_metadata`, so the library stays deduplicated by DOI
(and, for entries without one, by normalised title + year). Supported sources:

- BibTeX          (.bib)   — delegated to services.import_bibtex
- CSL-JSON        (.json)  — Zotero's "Better CSL JSON" / any citeproc export
- RIS             (.ris)   — EndNote / Mendeley / Web of Science exports
- PDF             (.pdf)   — the DOI or arXiv id is read from the first pages, metadata is
                              fetched, and the file is attached; with no id found a stub
                              reference is created from the PDF's title so nothing is lost
- Zotero (local)  — Zotero 7's local API on http://127.0.0.1:23119 (Settings → Advanced →
                    "Allow other applications on this computer to communicate with Zotero")
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field

import httpx
from django.core.files.base import ContentFile

from .models import ProjectReference, Reference
from .services import (
    MetadataError,
    _normalize_title,
    create_reference_from_metadata,
    fetch_metadata_by_arxiv,
    fetch_metadata_by_doi,
    normalize_doi,
)

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>)\]]+)", re.I)
ARXIV_RE = re.compile(r"arxiv[:\s]*(\d{4}\.\d{4,5})(v\d+)?", re.I)
ZOTERO_LOCAL_URL = "http://127.0.0.1:23119"
MAX_PDF_TEXT_PAGES = 3


@dataclass
class ImportResult:
    """What happened to one incoming item."""

    title: str
    reference_id: int | None = None
    created: bool = False
    source: str = ""
    error: str = ""
    needs_metadata: bool = False

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "reference_id": self.reference_id,
            "created": self.created,
            "source": self.source,
            "error": self.error,
            "needs_metadata": self.needs_metadata,
        }


@dataclass
class ImportSummary:
    results: list[ImportResult] = field(default_factory=list)

    @property
    def created(self) -> int:
        return sum(1 for r in self.results if r.created)

    @property
    def existing(self) -> int:
        return sum(1 for r in self.results if r.reference_id and not r.created)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.error)

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "existing": self.existing,
            "failed": self.failed,
            "results": [r.as_dict() for r in self.results],
        }


# --- parsers (pure) ---------------------------------------------------------------------


def _csl_year(item: dict) -> int | None:
    for key in ("issued", "original-date"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            try:
                return int(str(parts[0][0])[:4])
            except ValueError:
                continue
    return None


_CSL_TYPES = {
    "article-journal": "article",
    "article": "article",
    "paper-conference": "inproceedings",
    "chapter": "incollection",
    "book": "book",
    "thesis": "phdthesis",
    "report": "techreport",
    "webpage": "misc",
}


def parse_csl_json(text: str) -> list[dict]:
    """CSL-JSON (a list of items, or a dict with an `items` list) → metadata dicts."""
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("items") or data.get("data") or [data]
    metas = []
    for item in data:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        authors = [
            {"family": a.get("family") or a.get("literal") or "", "given": a.get("given") or ""}
            for a in item.get("author") or []
            if isinstance(a, dict)
        ]
        arxiv = ""
        for candidate in (item.get("URL") or "", item.get("note") or ""):
            m = ARXIV_RE.search(candidate)
            if m:
                arxiv = m.group(1)
                break
        metas.append(
            {
                "doi": normalize_doi(item["DOI"]) if item.get("DOI") else None,
                "arxiv_id": arxiv,
                "entry_type": _CSL_TYPES.get(item.get("type", ""), "misc"),
                "title": str(item["title"]).strip(),
                "authors": authors,
                "year": _csl_year(item),
                "venue": item.get("container-title") or item.get("publisher") or "",
                "abstract": item.get("abstract") or "",
                "url": item.get("URL") or "",
                "extra": {"source": "csl-json", "csl_id": item.get("id")},
            }
        )
    return metas


_RIS_TYPES = {
    "JOUR": "article",
    "CONF": "inproceedings",
    "CPAPER": "inproceedings",
    "CHAP": "incollection",
    "BOOK": "book",
    "THES": "phdthesis",
    "RPRT": "techreport",
    "EJOUR": "article",
}


def parse_ris(text: str) -> list[dict]:
    """RIS tagged format → metadata dicts. Tolerant of CRLF and of the common `TY  - ` spacing."""
    metas: list[dict] = []
    current: dict[str, list[str]] = {}
    tag_re = re.compile(r"^([A-Z][A-Z0-9])\s{1,2}-\s?(.*)$")
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        m = tag_re.match(line)
        if not m:
            continue
        tag, value = m.group(1), m.group(2).strip()
        if tag == "ER":
            if current:
                metas.append(_ris_to_meta(current))
            current = {}
            continue
        current.setdefault(tag, []).append(value)
    if current:
        metas.append(_ris_to_meta(current))
    return [m for m in metas if m["title"]]


def _ris_to_meta(fields: dict[str, list[str]]) -> dict:
    def first(*tags):
        for t in tags:
            if fields.get(t):
                return fields[t][0]
        return ""

    authors = []
    for name in fields.get("AU", []) + fields.get("A1", []):
        if "," in name:
            family, given = name.split(",", 1)
            authors.append({"family": family.strip(), "given": given.strip()})
        else:
            parts = name.rsplit(" ", 1)
            authors.append({"family": parts[-1], "given": parts[0] if len(parts) == 2 else ""})
    year = None
    m = re.match(r"(\d{4})", first("PY", "Y1", "DA"))
    if m:
        year = int(m.group(1))
    return {
        "doi": normalize_doi(first("DO")) if first("DO") else None,
        "entry_type": _RIS_TYPES.get(first("TY"), "misc"),
        "title": first("TI", "T1"),
        "authors": authors,
        "year": year,
        "venue": first("JO", "JF", "T2", "BT"),
        "abstract": first("AB", "N2"),
        "url": first("UR"),
        "extra": {"source": "ris"},
    }


def find_identifiers_in_text(text: str) -> tuple[str | None, str | None]:
    """(doi, arxiv_id) found in free text — used on the first pages of a PDF."""
    doi = None
    m = DOI_RE.search(text)
    if m:
        doi = normalize_doi(m.group(1).rstrip(".,;"))
    arxiv = None
    m = ARXIV_RE.search(text)
    if m:
        arxiv = m.group(1)
    return doi, arxiv


def read_pdf_front_matter(data: bytes) -> tuple[str, str]:
    """(text of the first pages, document title from the PDF metadata) — never raises."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PDF_TEXT_PAGES])
        title = ""
        if reader.metadata and reader.metadata.title:
            title = str(reader.metadata.title).strip()
        return text, title
    except Exception:  # a corrupt PDF must not abort the whole drop
        return "", ""


# --- importing --------------------------------------------------------------------------


def find_existing(meta: dict) -> Reference | None:
    """Dedupe beyond the DOI: same arXiv id, or same normalised title + year."""
    if meta.get("doi"):
        found = Reference.objects.filter(doi=meta["doi"]).first()
        if found:
            return found
    if meta.get("arxiv_id"):
        found = Reference.objects.filter(arxiv_id=meta["arxiv_id"]).first()
        if found:
            return found
    key = _normalize_title(meta.get("title", ""))
    if len(key) < 8:  # "Notes" / "Draft" are not identities
        return None
    for candidate in Reference.objects.filter(year=meta.get("year")).only("id", "title"):
        if _normalize_title(candidate.title) == key:
            return candidate
    return None


def _link(reference: Reference, project) -> None:
    if project is not None:
        ProjectReference.objects.get_or_create(project=project, reference=reference)


def parse_bibtex(text: str) -> list[dict]:
    """BibTeX → metadata dicts (the raw entry rides along as `_raw_bibtex`)."""
    import bibtexparser

    from .services import _parse_bibtex_author, _single_entry_db

    metas = []
    for entry in bibtexparser.loads(text).entries:
        year = None
        if re.match(r"^\d{4}", entry.get("year", "")):
            year = int(entry["year"][:4])
        metas.append(
            {
                "doi": normalize_doi(entry["doi"]) if entry.get("doi") else None,
                "entry_type": entry.get("ENTRYTYPE", "misc"),
                "title": re.sub(r"[{}]", "", entry.get("title", "Untitled")),
                "authors": [
                    _parse_bibtex_author(a)
                    for a in re.split(r"\s+and\s+", entry.get("author", ""))
                    if a
                ],
                "year": year,
                "venue": entry.get("journal", "") or entry.get("booktitle", ""),
                "abstract": entry.get("abstract", ""),
                "url": entry.get("url", ""),
                "extra": {"source": "bibtex-import"},
                "_raw_bibtex": bibtexparser.dumps(_single_entry_db(entry)),
            }
        )
    return metas


def import_metadata_list(metas: list[dict], project=None, source: str = "") -> ImportSummary:
    summary = ImportSummary()
    for meta in metas:
        raw_bibtex = meta.pop("_raw_bibtex", "")
        existing = find_existing(meta)
        if existing:
            reference, created = existing, False
        else:
            reference, created = create_reference_from_metadata(meta)
            if raw_bibtex:
                reference.raw_bibtex = raw_bibtex
                reference.save(update_fields=["raw_bibtex", "updated_at"])
        _link(reference, project)
        summary.results.append(
            ImportResult(
                title=reference.title,
                reference_id=reference.pk,
                created=created,
                source=source or meta.get("extra", {}).get("source", ""),
            )
        )
    return summary


def import_text(text: str, fmt: str, project=None) -> ImportSummary:
    """Import pasted text: fmt is 'bibtex', 'csl-json', or 'ris'."""
    if fmt == "bibtex":
        return import_metadata_list(parse_bibtex(text), project, "bibtex")
    if fmt == "csl-json":
        return import_metadata_list(parse_csl_json(text), project, "csl-json")
    if fmt == "ris":
        return import_metadata_list(parse_ris(text), project, "ris")
    raise ValueError(f"Unknown import format: {fmt}")


def sniff_format(name: str, data: bytes) -> str:
    lower = name.lower()
    if lower.endswith(".pdf") or data[:5] == b"%PDF-":
        return "pdf"
    if lower.endswith(".bib") or lower.endswith(".bibtex"):
        return "bibtex"
    if lower.endswith(".ris"):
        return "ris"
    if lower.endswith(".json"):
        return "csl-json"
    head = data[:200].lstrip()
    if head.startswith(b"@"):
        return "bibtex"
    if head.startswith(b"[") or head.startswith(b"{"):
        return "csl-json"
    if head.startswith(b"TY  -"):
        return "ris"
    raise ValueError(f"Can't tell what {name} is — drop a .pdf, .bib, .ris, or CSL .json file.")


def import_pdf(name: str, data: bytes, project=None) -> ImportResult:
    """One dropped PDF → a reference with the file attached.

    Reads the DOI / arXiv id from the first pages and fetches real metadata; with no id (or
    no network) it still keeps the paper as a stub titled from the PDF, flagged
    `needs_metadata` so the library can offer "find metadata" later.
    """
    text, pdf_title = read_pdf_front_matter(data)
    doi, arxiv = find_identifiers_in_text(text)
    meta: dict | None = None
    error = ""
    try:
        if doi:
            meta = fetch_metadata_by_doi(doi)
        elif arxiv:
            meta = fetch_metadata_by_arxiv(arxiv)
    except MetadataError as exc:
        error = str(exc)
    needs_metadata = meta is None
    if meta is None:
        title = pdf_title or _title_from_text(text) or re.sub(r"\.pdf$", "", name, flags=re.I)
        meta = {
            "doi": doi,
            "arxiv_id": arxiv or "",
            "entry_type": "misc",
            "title": title[:300],
            "authors": [],
            "year": None,
            "extra": {"source": "pdf-import", "needs_metadata": True, "metadata_error": error},
        }
    else:
        meta.setdefault("extra", {})
        meta["extra"] = {**meta["extra"], "source": "pdf-import"}
    existing = find_existing(meta)
    if existing:
        reference, created = existing, False
    else:
        reference, created = create_reference_from_metadata(meta)
    if not reference.pdf:
        reference.pdf.save(f"{reference.bibtex_key}.pdf", ContentFile(data), save=True)
    _link(reference, project)
    return ImportResult(
        title=reference.title,
        reference_id=reference.pk,
        created=created,
        source="pdf",
        needs_metadata=needs_metadata,
        error="" if created or existing else error,
    )


def _title_from_text(text: str) -> str:
    """First plausible title line of the extracted text (non-empty, not a URL/DOI, < 200 chars)."""
    for line in text.splitlines():
        line = line.strip()
        if 12 <= len(line) <= 200 and not DOI_RE.search(line) and "http" not in line.lower():
            if sum(c.isalpha() for c in line) > len(line) * 0.6:
                return line
    return ""


def import_file(name: str, data: bytes, project=None) -> ImportSummary:
    """Import one dropped file of any supported kind."""
    try:
        fmt = sniff_format(name, data)
    except ValueError as exc:
        return ImportSummary([ImportResult(title=name, error=str(exc))])
    if fmt == "pdf":
        return ImportSummary([import_pdf(name, data, project)])
    try:
        return import_text(data.decode("utf-8", errors="replace"), fmt, project)
    except (ValueError, KeyError) as exc:
        return ImportSummary([ImportResult(title=name, error=f"Couldn't parse {name}: {exc}")])


# --- Zotero (local API) ------------------------------------------------------------------


class ZoteroUnavailable(Exception):
    pass


def fetch_zotero_items(
    base_url: str = ZOTERO_LOCAL_URL, client: httpx.Client | None = None
) -> list[dict]:
    """All regular items from the running Zotero's local API as CSL-JSON."""
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    items: list[dict] = []
    try:
        start = 0
        while True:
            try:
                response = client.get(
                    f"{base_url.rstrip('/')}/api/users/0/items",
                    params={
                        "format": "csljson",
                        "itemType": "-attachment || note",
                        "limit": 100,
                        "start": start,
                    },
                )
            except httpx.HTTPError as exc:
                raise ZoteroUnavailable(
                    "Zotero isn't reachable on this machine. Open Zotero 7 and enable "
                    'Settings → Advanced → "Allow other applications on this computer to '
                    f'communicate with Zotero", then try again. ({exc.__class__.__name__})'
                ) from exc
            if response.status_code != 200:
                raise ZoteroUnavailable(
                    f"Zotero's local API answered HTTP {response.status_code}. Make sure the "
                    "local API is enabled in Zotero → Settings → Advanced."
                )
            payload = response.json()
            batch = payload.get("items", payload) if isinstance(payload, dict) else payload
            if not batch:
                break
            items.extend(batch)
            if len(batch) < 100:
                break
            start += 100
    finally:
        if own:
            client.close()
    return items


def import_from_zotero(
    project=None, base_url: str = ZOTERO_LOCAL_URL, client=None
) -> ImportSummary:
    items = fetch_zotero_items(base_url, client)
    metas = parse_csl_json(json.dumps(items))
    for meta in metas:
        meta["extra"]["source"] = "zotero"
    return import_metadata_list(metas, project, "zotero")
