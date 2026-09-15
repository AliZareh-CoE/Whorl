"""Library exports in the formats colleagues use (#525): BibTeX, RIS, CSL-JSON and CSV.

Every writer takes an iterable of references (prefetch `tags` and `project_links__project`
for the CSV) and returns text; `render()` picks the writer, media type and file name from the
format key the API and the MCP tool accept.
"""

import csv
import io
import json

from .library import export_bibtex

_RIS_TYPES = {
    "article": "JOUR",
    "inproceedings": "CONF",
    "incollection": "CHAP",
    "book": "BOOK",
    "phdthesis": "THES",
    "mastersthesis": "THES",
    "techreport": "RPRT",
}
_CSL_TYPES = {
    "article": "article-journal",
    "inproceedings": "paper-conference",
    "incollection": "chapter",
    "book": "book",
    "phdthesis": "thesis",
    "mastersthesis": "thesis",
    "techreport": "report",
}


def _authors(reference) -> list[dict]:
    return [
        {"family": (a.get("family") or "").strip(), "given": (a.get("given") or "").strip()}
        for a in (reference.authors or [])
        if isinstance(a, dict) and (a.get("family") or a.get("given"))
    ]


def _biblio(reference) -> dict:
    extra = reference.extra if isinstance(reference.extra, dict) else {}
    return {
        "volume": str(extra.get("volume") or ""),
        "issue": str(extra.get("issue") or ""),
        "pages": str(extra.get("pages") or ""),
    }


def export_ris(references) -> str:
    """RIS (EndNote, Mendeley, Zotero, Web of Science): one record per reference."""
    out: list[str] = []
    for ref in references:
        lines = [f"TY  - {_RIS_TYPES.get(ref.entry_type, 'GEN')}"]
        lines.append(f"TI  - {ref.title}")
        for a in _authors(ref):
            lines.append(f"AU  - {a['family']}, {a['given']}".rstrip(", "))
        if ref.year:
            lines.append(f"PY  - {ref.year}")
        if ref.venue:
            lines.append(f"{'JO' if ref.entry_type == 'article' else 'T2'}  - {ref.venue}")
        biblio = _biblio(ref)
        if biblio["volume"]:
            lines.append(f"VL  - {biblio['volume']}")
        if biblio["issue"]:
            lines.append(f"IS  - {biblio['issue']}")
        if biblio["pages"]:
            start, _sep, end = biblio["pages"].replace("–", "-").partition("-")
            lines.append(f"SP  - {start.strip()}")
            if end.strip():
                lines.append(f"EP  - {end.strip()}")
        if ref.doi:
            lines.append(f"DO  - {ref.doi}")
        if ref.url:
            lines.append(f"UR  - {ref.url}")
        if ref.abstract:
            lines.append(f"AB  - {' '.join(ref.abstract.split())}")
        for tag in ref.tags.all():
            lines.append(f"KW  - {tag.name}")
        lines.append(f"ID  - {ref.bibtex_key}")
        lines.append("ER  - ")
        out.append("\n".join(lines))
    return "\n\n".join(out) + ("\n" if out else "")


def csl_item(reference) -> dict:
    item = {
        "id": reference.bibtex_key,
        "type": _CSL_TYPES.get(reference.entry_type, "document"),
        "title": reference.title,
        "author": _authors(reference),
    }
    if reference.year:
        item["issued"] = {"date-parts": [[reference.year]]}
    if reference.venue:
        item["container-title"] = reference.venue
    biblio = _biblio(reference)
    if biblio["volume"]:
        item["volume"] = biblio["volume"]
    if biblio["issue"]:
        item["issue"] = biblio["issue"]
    if biblio["pages"]:
        item["page"] = biblio["pages"]
    if reference.doi:
        item["DOI"] = reference.doi
    if reference.url:
        item["URL"] = reference.url
    if reference.abstract:
        item["abstract"] = reference.abstract
    keywords = [t.name for t in reference.tags.all()]
    if keywords:
        item["keyword"] = ", ".join(keywords)
    return item


def export_csl_json(references) -> str:
    """CSL-JSON (Zotero, Paperpile, pandoc --citeproc): a JSON array of items."""
    return json.dumps([csl_item(r) for r in references], ensure_ascii=False, indent=2) + "\n"


CSV_COLUMNS = (
    "id",
    "bibtex_key",
    "entry_type",
    "title",
    "authors",
    "year",
    "venue",
    "volume",
    "issue",
    "pages",
    "doi",
    "arxiv_id",
    "url",
    "citation_count",
    "tags",
    "projects",
    "has_pdf",
    "added",
)


def _cell(value):
    """Neutralise spreadsheet formula injection: a cell starting with =, +, -, @, a tab or a
    carriage return (the OWASP list) is quoted."""
    text = "" if value is None else str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_csv(references) -> str:
    """A spreadsheet of the rows (UTF-8 with a BOM so Excel reads accents); one line per paper,
    authors as "Family, Given; …", projects as "slug: reading_status; …"."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for ref in references:
        biblio = _biblio(ref)
        writer.writerow(
            [
                ref.pk,
                _cell(ref.bibtex_key),
                _cell(ref.entry_type),
                _cell(ref.title),
                _cell(
                    "; ".join(f"{a['family']}, {a['given']}".rstrip(", ") for a in _authors(ref))
                ),
                ref.year or "",
                _cell(ref.venue),
                _cell(biblio["volume"]),
                _cell(biblio["issue"]),
                _cell(biblio["pages"]),
                _cell(ref.doi or ""),
                _cell(ref.arxiv_id or ""),
                _cell(ref.url),
                ref.citation_count if ref.citation_count is not None else "",
                _cell("; ".join(t.name for t in ref.tags.all())),
                _cell(
                    "; ".join(
                        f"{link.project.slug}: {link.reading_status}"
                        for link in ref.project_links.all()
                    )
                ),
                "yes" if ref.pdf else "no",
                ref.created_at.date().isoformat() if ref.created_at else "",
            ]
        )
    return "﻿" + buf.getvalue()


FORMATS = {
    "bib": (export_bibtex, "application/x-bibtex; charset=utf-8", "bib"),
    "ris": (export_ris, "application/x-research-info-systems; charset=utf-8", "ris"),
    "csl": (export_csl_json, "application/vnd.citationstyles.csl+json; charset=utf-8", "json"),
    "csv": (export_csv, "text/csv; charset=utf-8", "csv"),
}
ALIASES = {"bibtex": "bib", "csl-json": "csl", "json": "csl"}


def render(references, fmt: str = "bib") -> tuple[str, str, str]:
    """(text, content type, file name) for a format key; ValueError for an unknown one."""
    key = ALIASES.get((fmt or "bib").lower(), (fmt or "bib").lower())
    if key not in FORMATS:
        raise ValueError(f"Unknown export format {fmt!r}; use one of {', '.join(FORMATS)}.")
    writer, content_type, ext = FORMATS[key]
    return writer(references), content_type, f"atlas-library.{ext}"
