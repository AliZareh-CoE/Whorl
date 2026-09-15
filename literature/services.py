"""Metadata fetching, BibTeX import/export, and bib checkers.

All functions here are plain Python — views stay thin.
"""

import difflib
import re

import bibtexparser
import httpx

from .models import Reference

TIMEOUT = httpx.Timeout(10.0)
USER_AGENT = "Atlas (research project manager; mailto:owner@localhost)"

REQUIRED_FIELDS = {
    "article": ["authors", "title", "venue", "year"],
    "inproceedings": ["authors", "title", "venue", "year"],
    "book": ["authors", "title", "year"],
    "phdthesis": ["authors", "title", "year"],
    "techreport": ["authors", "title", "year"],
    "misc": ["title"],
}


class MetadataError(Exception):
    """Raised when an identifier cannot be resolved to metadata, with a human-readable reason."""


def normalize_doi(doi: str) -> str:
    doi = doi.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.lower()


def normalize_arxiv_id(arxiv_id: str) -> str:
    arxiv_id = arxiv_id.strip()
    arxiv_id = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", arxiv_id, flags=re.I)
    arxiv_id = re.sub(r"^arxiv:", "", arxiv_id, flags=re.I)
    return re.sub(r"v\d+$", "", arxiv_id)


def generate_bibtex_key(authors: list[dict], year, title: str) -> str:
    """lastnameYEARfirstword, made unique with letter suffixes (smith2020attention, ...b, ...c)."""
    family = (authors[0].get("family") if authors else "") or "anon"
    family = re.sub(r"[^a-z]", "", family.lower()) or "anon"
    stopwords = {"a", "an", "the", "on", "of", "in", "for", "and", "to", "with", "from"}
    first_word = "untitled"
    for word in re.findall(r"[a-z]+", (title or "").lower()):
        if word not in stopwords:
            first_word = word
            break
    base = f"{family}{year or 'nd'}{first_word}"
    key, suffix = base, ord("b")
    while Reference.objects.filter(bibtex_key=key).exists():
        key = f"{base}{chr(suffix)}"
        suffix += 1
    return key


# --- metadata fetch -------------------------------------------------------


def _crossref_to_meta(work: dict) -> dict:
    type_map = {
        "journal-article": "article",
        "proceedings-article": "inproceedings",
        "book": "book",
    }
    issued = work.get("issued", {}).get("date-parts", [[None]])
    return {
        "doi": normalize_doi(work.get("DOI", "")),
        "entry_type": type_map.get(work.get("type"), "misc"),
        "title": " ".join(work.get("title") or ["Untitled"]),
        "authors": [
            {"family": a.get("family", ""), "given": a.get("given", "")}
            for a in work.get("author", [])
        ],
        "year": issued[0][0],
        "venue": " ".join(work.get("container-title") or []),
        "abstract": re.sub(r"<[^>]+>", "", work.get("abstract", "")),
        "url": work.get("URL", ""),
        "citation_count": work.get("is-referenced-by-count"),
        "extra": {
            "source": "crossref",
            # formatted citations (literature/citations.py) use these when present
            "volume": work.get("volume", ""),
            "issue": work.get("issue", ""),
            "pages": work.get("page", ""),
        },
    }


def _openalex_to_meta(work: dict) -> dict:
    type_map = {"article": "article", "book": "book", "book-chapter": "inproceedings"}
    doi = work.get("doi") or ""
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    arxiv = ""
    for loc in work.get("locations", []):
        landing = (loc or {}).get("landing_page_url") or ""
        if "arxiv.org" in landing:
            arxiv = normalize_arxiv_id(landing)
            break
    return {
        "doi": normalize_doi(doi) if doi else None,
        "arxiv_id": arxiv,
        "openalex_id": (work.get("id") or "").rsplit("/", 1)[-1],
        "entry_type": type_map.get(work.get("type"), "misc"),
        "title": work.get("title") or "Untitled",
        "authors": [
            {
                "family": (a.get("author", {}).get("display_name", "").rsplit(" ", 1)[-1]),
                "given": " ".join(a.get("author", {}).get("display_name", "").split(" ")[:-1]),
            }
            for a in work.get("authorships", [])
        ],
        "year": work.get("publication_year"),
        "venue": source.get("display_name", "") or "",
        "abstract": _invert_abstract(work.get("abstract_inverted_index")),
        "url": doi or (work.get("primary_location") or {}).get("landing_page_url", "") or "",
        "citation_count": work.get("cited_by_count"),
        "extra": {
            "source": "openalex",
            "volume": (work.get("biblio") or {}).get("volume") or "",
            "issue": (work.get("biblio") or {}).get("issue") or "",
            "pages": "-".join(
                p
                for p in (
                    (work.get("biblio") or {}).get("first_page"),
                    (work.get("biblio") or {}).get("last_page"),
                )
                if p
            ),
        },
    }


def _invert_abstract(inverted: dict | None) -> str:
    if not inverted:
        return ""
    positions = {}
    for word, idxs in inverted.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


def fetch_metadata_by_doi(doi: str) -> dict:
    """Crossref first, OpenAlex as fallback. Raises MetadataError with a clear reason."""
    doi = normalize_doi(doi)
    errors = []
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        try:
            response = client.get(f"https://api.crossref.org/works/{doi}")
            if response.status_code == 200:
                return _crossref_to_meta(response.json()["message"])
            errors.append(f"Crossref returned {response.status_code}")
        except httpx.HTTPError as exc:
            errors.append(f"Crossref unreachable ({exc.__class__.__name__})")
        try:
            response = client.get(f"https://api.openalex.org/works/doi:{doi}")
            if response.status_code == 200:
                return _openalex_to_meta(response.json())
            errors.append(f"OpenAlex returned {response.status_code}")
        except httpx.HTTPError as exc:
            errors.append(f"OpenAlex unreachable ({exc.__class__.__name__})")
    raise MetadataError(f"Could not resolve DOI {doi}: " + "; ".join(errors))


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def fetch_metadata_by_arxiv(arxiv_id: str) -> dict:
    """arXiv papers resolve through arXiv's own Atom export API."""
    import xml.etree.ElementTree as ET

    arxiv_id = normalize_arxiv_id(arxiv_id)
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        try:
            response = client.get(
                "https://export.arxiv.org/api/query", params={"id_list": arxiv_id}
            )
        except httpx.HTTPError as exc:
            raise MetadataError(
                f"Could not resolve arXiv ID {arxiv_id}: arXiv API unreachable "
                f"({exc.__class__.__name__})"
            ) from exc
    if response.status_code != 200:
        raise MetadataError(
            f"Could not resolve arXiv ID {arxiv_id}: arXiv API returned {response.status_code}"
        )
    entry = ET.fromstring(response.text).find("atom:entry", ATOM_NS)
    title_el = entry.find("atom:title", ATOM_NS) if entry is not None else None
    title = (title_el.text or "").strip() if title_el is not None else ""
    if not title or title == "Error":
        raise MetadataError(f"Could not resolve arXiv ID {arxiv_id}: not found on arXiv")
    authors = []
    for author in entry.findall("atom:author", ATOM_NS):
        name = (author.findtext("atom:name", "", ATOM_NS) or "").strip()
        if name:
            parts = name.rsplit(" ", 1)
            authors.append({"family": parts[-1], "given": parts[0] if len(parts) == 2 else ""})
    published = entry.findtext("atom:published", "", ATOM_NS) or ""
    year = int(published[:4]) if re.match(r"^\d{4}", published) else None
    doi = entry.findtext("arxiv:doi", "", ATOM_NS) or ""
    abstract = re.sub(r"\s+", " ", entry.findtext("atom:summary", "", ATOM_NS) or "").strip()
    return {
        "doi": normalize_doi(doi) if doi else None,
        "arxiv_id": arxiv_id,
        "entry_type": "misc",
        "title": re.sub(r"\s+", " ", title),
        "authors": authors,
        "year": year,
        "venue": "arXiv",
        "abstract": abstract,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "extra": {"source": "arxiv"},
    }


def create_reference_from_metadata(meta: dict) -> tuple[Reference, bool]:
    """Create (or return existing by DOI) a Reference from a metadata dict."""
    doi = meta.get("doi") or None
    if doi:
        existing = Reference.objects.filter(doi=doi).first()
        if existing:
            return existing, False
    reference = Reference.objects.create(
        doi=doi,
        arxiv_id=meta.get("arxiv_id") or "",
        openalex_id=meta.get("openalex_id") or "",
        bibtex_key=generate_bibtex_key(meta.get("authors", []), meta.get("year"), meta["title"]),
        entry_type=meta.get("entry_type", "misc"),
        title=meta["title"],
        authors=meta.get("authors", []),
        year=meta.get("year"),
        venue=meta.get("venue", ""),
        abstract=meta.get("abstract", ""),
        url=meta.get("url", ""),
        citation_count=meta.get("citation_count"),
        extra=meta.get("extra", {}),
    )
    return reference, True


def add_reference_by_identifier(identifier: str) -> tuple[Reference, bool]:
    """Accepts a DOI or arXiv ID (raw or as URL) and returns (reference, created)."""
    identifier = identifier.strip()
    if re.search(r"arxiv", identifier, re.I) or re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", identifier):
        meta = fetch_metadata_by_arxiv(identifier)
        existing = Reference.objects.filter(arxiv_id=meta["arxiv_id"]).first()
        if existing:
            return existing, False
    else:
        meta = fetch_metadata_by_doi(identifier)
    return create_reference_from_metadata(meta)


# --- BibTeX ---------------------------------------------------------------


def import_bibtex(text: str) -> list[tuple[Reference, bool]]:
    """Parse pasted BibTeX and create references. Returns [(reference, created), ...]."""
    database = bibtexparser.loads(text)
    results = []
    for entry in database.entries:
        authors = [
            _parse_bibtex_author(a) for a in re.split(r"\s+and\s+", entry.get("author", "")) if a
        ]
        year = None
        if re.match(r"^\d{4}", entry.get("year", "")):
            year = int(entry["year"][:4])
        meta = {
            "doi": normalize_doi(entry["doi"]) if entry.get("doi") else None,
            "entry_type": entry.get("ENTRYTYPE", "misc"),
            "title": re.sub(r"[{}]", "", entry.get("title", "Untitled")),
            "authors": authors,
            "year": year,
            "venue": entry.get("journal", "") or entry.get("booktitle", ""),
            "abstract": entry.get("abstract", ""),
            "url": entry.get("url", ""),
            "extra": {"source": "bibtex-import"},
        }
        reference, created = create_reference_from_metadata(meta)
        if created:
            reference.raw_bibtex = bibtexparser.dumps(_single_entry_db(entry))
            reference.save(update_fields=["raw_bibtex", "updated_at"])
        results.append((reference, created))
    return results


def _single_entry_db(entry):
    database = bibtexparser.bibdatabase.BibDatabase()
    database.entries = [entry]
    return database


def _parse_bibtex_author(author: str) -> dict:
    author = author.strip()
    if "," in author:
        family, given = author.split(",", 1)
        return {"family": family.strip(), "given": given.strip()}
    parts = author.rsplit(" ", 1)
    if len(parts) == 2:
        return {"family": parts[1], "given": parts[0]}
    return {"family": author, "given": ""}


def render_bibtex(reference: Reference, key_override: str = "") -> str:
    """Render one reference as a BibTeX entry with its stable generated key."""
    fields = {
        "title": f"{{{reference.title}}}",
        "author": " and ".join(
            f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in reference.authors
        ),
    }
    if reference.year:
        fields["year"] = str(reference.year)
    if reference.venue:
        venue_field = "booktitle" if reference.entry_type == "inproceedings" else "journal"
        fields[venue_field] = reference.venue
    if reference.doi:
        fields["doi"] = reference.doi
    if reference.url:
        fields["url"] = reference.url
    if reference.arxiv_id:
        fields["eprint"] = reference.arxiv_id
        fields["archiveprefix"] = "arXiv"
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields.items() if value)
    key = key_override or reference.bibtex_key
    return f"@{reference.entry_type}{{{key},\n{body}\n}}"


def export_project_bib(project) -> str:
    references = Reference.objects.filter(project_links__project=project).order_by("bibtex_key")
    return "\n\n".join(render_bibtex(r) for r in references)


# --- bib checkers v1 ------------------------------------------------------


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def check_duplicates(references) -> list[dict]:
    """DOI exact + fuzzy-title duplicate detection. Returns finding dicts."""
    findings = []
    refs = list(references)
    by_doi: dict[str, Reference] = {}
    for ref in refs:
        if ref.doi:
            if ref.doi in by_doi:
                findings.append(
                    {
                        "check": "duplicate",
                        "level": "error",
                        "message": f"Same DOI ({ref.doi}): “{by_doi[ref.doi].bibtex_key}” and “{ref.bibtex_key}”",
                        "references": [by_doi[ref.doi], ref],
                    }
                )
            else:
                by_doi[ref.doi] = ref
    for i, a in enumerate(refs):
        for b in refs[i + 1 :]:
            if a.doi and b.doi and a.doi == b.doi:
                continue  # already reported
            ta, tb = _normalize_title(a.title), _normalize_title(b.title)
            if not ta or not tb:
                continue
            if ta == tb or difflib.SequenceMatcher(None, ta, tb).ratio() >= 0.92:
                findings.append(
                    {
                        "check": "duplicate",
                        "level": "warning",
                        "message": f"Similar titles: “{a.bibtex_key}” and “{b.bibtex_key}”",
                        "references": [a, b],
                    }
                )
    return findings


def check_missing_fields(references) -> list[dict]:
    findings = []
    for ref in references:
        required = REQUIRED_FIELDS.get(ref.entry_type, ["title"])
        missing = [f for f in required if not getattr(ref, f)]
        if missing:
            findings.append(
                {
                    "check": "missing_fields",
                    "level": "warning",
                    "message": f"“{ref.bibtex_key}” ({ref.entry_type}) missing: {', '.join(missing)}",
                    "references": [ref],
                }
            )
    return findings


def check_doi_resolution(references, client: httpx.Client | None = None) -> list[dict]:
    """HEAD each DOI against doi.org; unresolvable or unreachable DOIs are flagged."""
    findings = []
    own_client = client is None
    client = client or httpx.Client(
        timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=False
    )
    try:
        for ref in references:
            if not ref.doi:
                findings.append(
                    {
                        "check": "doi_resolution",
                        "level": "info",
                        "message": f"“{ref.bibtex_key}” has no DOI to check",
                        "references": [ref],
                    }
                )
                continue
            try:
                response = client.head(f"https://doi.org/{ref.doi}")
                if response.status_code in (404, 410):
                    findings.append(
                        {
                            "check": "doi_resolution",
                            "level": "error",
                            "message": f"DOI {ref.doi} does not resolve (HTTP {response.status_code})",
                            "references": [ref],
                        }
                    )
            except httpx.HTTPError as exc:
                findings.append(
                    {
                        "check": "doi_resolution",
                        "level": "info",
                        "message": f"DOI {ref.doi}: check failed ({exc.__class__.__name__})",
                        "references": [ref],
                    }
                )
    finally:
        if own_client:
            client.close()
    return findings


def check_retractions(references, client: httpx.Client | None = None) -> list[dict]:
    """Flag references whose DOI has a Crossref retraction/withdrawal update pointing at it.
    Since #527 the lookup lives in literature.retractions (the same request), and a paper the
    retraction watch has already flagged is reported without asking again."""
    from .retractions import lookup

    findings = []
    own_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    try:
        for ref in references:
            if not ref.doi:
                continue
            if ref.retraction_kind:
                findings.append(
                    {
                        "check": "retraction",
                        "level": "error",
                        "message": f"“{ref.bibtex_key}” is RETRACTED ({ref.retraction_kind}; notice DOI {ref.retraction_notice})",
                        "references": [ref],
                    }
                )
                continue
            try:
                found = lookup(ref.doi, client)
            except RuntimeError:
                continue
            except httpx.HTTPError as exc:
                findings.append(
                    {
                        "check": "retraction",
                        "level": "info",
                        "message": f"“{ref.bibtex_key}”: retraction check failed ({exc.__class__.__name__})",
                        "references": [ref],
                    }
                )
                continue
            if found:
                findings.append(
                    {
                        "check": "retraction",
                        "level": "error",
                        "message": f"“{ref.bibtex_key}” appears to be RETRACTED (update DOI {found['notice']})",
                        "references": [ref],
                    }
                )
    finally:
        if own_client:
            client.close()
    return findings


def run_bib_report(references, include_network_checks: bool = True) -> dict:
    """All checker categories over the given references, grouped for the report page."""
    references = list(references)
    report = {
        "duplicates": check_duplicates(references),
        "missing_fields": check_missing_fields(references),
        "doi_resolution": [],
        "retractions": [],
    }
    if include_network_checks:
        report["doi_resolution"] = check_doi_resolution(references)
        report["retractions"] = check_retractions(references)
    return report
