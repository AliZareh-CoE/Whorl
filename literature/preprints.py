"""The preprint watch (#529): every arXiv preprint in the library is checked for a published
version, the answer is stored on the reference, and a daily sweep re-checks the stale ones — so
"this has since appeared in a venue" is seen where the paper is read, filed and cited, and the
reference can be upgraded in one click without changing its cite key.

Sources, in order: arXiv's own API (the author-deposited `arxiv:doi` and `journal_ref`, one
request per batch of ids) and Semantic Scholar's batch endpoint (it links arXiv records to
their published DOI). OpenAlex keeps the preprint and the paper as separate works, so it is no
help here.

Rules: a found published DOI is stored and never cleared by a later "nothing found" (a paper
that has been published stays published); an answer with nothing found only moves the checked
stamp; a request that fails (offline, a timeout, a non-200) leaves both alone and counts as an
error — a sweep on a train never invents or forgets a publication.
"""

from __future__ import annotations

import datetime
import logging
import re
import time
import xml.etree.ElementTree as ET

import httpx
from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone

from .models import Reference
from .services import (
    ATOM_NS,
    MetadataError,
    fetch_metadata_by_doi,
    normalize_arxiv_id,
    normalize_doi,
)

log = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(15.0)
USER_AGENT = "Atlas (research project manager; mailto:owner@localhost)"
ARXIV_API = "https://export.arxiv.org/api/query"
S2_BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch"
S2_FIELDS = "externalIds,venue,journal,publicationVenue"
ARXIV_DOI_PREFIX = "10.48550/arxiv."
CHUNK = 50  # ids per request to either source
ARXIV_PAUSE = 3.0  # arXiv's terms of use: one request every three seconds
STALE_DAYS = 30
MAX_STALE_DAYS = 3650
SWEEP_LIMIT = 200
MAX_CONSECUTIVE_ERRORS = 3  # failed chunks (both sources) before an offline sweep stops


def is_arxiv_doi(doi: str | None) -> bool:
    return bool(doi) and normalize_doi(doi).startswith(ARXIV_DOI_PREFIX)


def is_preprint(reference: Reference) -> bool:
    """An arXiv paper that has no publisher DOI of its own."""
    return bool(reference.arxiv_id) and (not reference.doi or is_arxiv_doi(reference.doi))


def preprint_q() -> Q:
    """The same rule as a queryset filter (Postgres and SQLite)."""
    return Q(arxiv_id__gt="") & (
        Q(doi__isnull=True) | Q(doi="") | Q(doi__istartswith=ARXIV_DOI_PREFIX)
    )


def preprints(qs=None):
    qs = Reference.objects.all() if qs is None else qs
    return qs.filter(preprint_q())


def published_available(qs=None):
    return preprints(qs).exclude(published_doi="")


# --- the two sources ---------------------------------------------------------------------


def _client() -> httpx.Client:
    headers = {"User-Agent": USER_AGENT}
    key = getattr(settings, "ATLAS_S2_API_KEY", "")
    if key:
        headers["x-api-key"] = key
    return httpx.Client(timeout=TIMEOUT, headers=headers)


def _clean(doi: str | None) -> str:
    doi = normalize_doi(doi or "")
    return "" if not doi or doi.startswith(ARXIV_DOI_PREFIX) else doi


def lookup_arxiv(arxiv_ids: list[str], client: httpx.Client) -> dict[str, dict]:
    """One arXiv API request for a batch of ids → {arxiv_id: {doi, venue}} for the entries
    whose record carries a publisher DOI. Raises httpx.HTTPError / RuntimeError / ValueError
    when the request did not answer (so the caller can tell "none" from "could not ask")."""
    if not arxiv_ids:
        return {}
    response = client.get(
        ARXIV_API, params={"id_list": ",".join(arxiv_ids), "max_results": len(arxiv_ids)}
    )
    if response.status_code != 200:
        raise RuntimeError(f"arXiv answered {response.status_code}")
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        raise ValueError("arXiv answered with something other than Atom") from exc
    found: dict[str, dict] = {}
    for entry in root.findall("atom:entry", ATOM_NS):
        raw_id = (entry.findtext("atom:id", "", ATOM_NS) or "").strip()
        arxiv_id = normalize_arxiv_id(raw_id)
        doi = _clean(entry.findtext("arxiv:doi", "", ATOM_NS))
        if arxiv_id and doi:
            venue = (entry.findtext("arxiv:journal_ref", "", ATOM_NS) or "").strip()
            version = re.search(r"v(\d+)$", raw_id)
            found[arxiv_id] = {
                "doi": doi,
                "venue": venue[:300],
                "source": "arxiv",
                "version": f"v{version.group(1)}" if version else "",
            }
    return found


_REF_YEAR = re.compile(r"(?<![\d-])((?:19|20)\d{2})(?![\d-])")  # not a page of a range
_REF_PAGES = re.compile(
    r"(?:pp?\.?\s*|pages?\s+|:\s*)?(?<![\d.])(\d{1,6}(?:\s*[-–—]\s*\d{1,6})?)(?![\d.])\s*$"
)
_REF_VOL = re.compile(r"(?:vol(?:ume)?\.?\s*)?(\d{1,4})(?:\s*\((\d{1,4})\))?\s*(?:[:,]|$)")


def parse_journal_ref(text: str) -> dict:
    """The parts of an arXiv `journal_ref` line ("CVPR 2016, pp. 770-778", "Nature 521,
    436-444 (2015)", "J. Mach. Learn. Res. 15(1):1929-1958, 2014"): {venue, volume, issue,
    pages, year}. Every part is best-effort and blank when the line does not carry it; the
    venue is what is left once year, volume and pages are taken out."""
    raw = " ".join((text or "").split())
    out = {"venue": "", "volume": "", "issue": "", "pages": "", "year": None}
    if not raw:
        return out
    rest = raw
    years = list(_REF_YEAR.finditer(rest))
    if years:
        m = years[-1]  # the last standalone year: "15(1):1929-1958, 2014" → 2014
        out["year"] = int(m.group(1))
        rest = (rest[: m.start()] + rest[m.end() :]).replace("()", "")
    rest = rest.strip(" ,;:")
    m = _REF_PAGES.search(rest)
    if m:
        out["pages"] = re.sub(r"\s*[-–—]\s*", "-", m.group(1))
        rest = rest[: m.start()].strip(" ,;:")
    m = _REF_VOL.search(rest)
    if m:
        out["volume"], out["issue"] = m.group(1), m.group(2) or ""
        rest = (rest[: m.start()] + rest[m.end() :]).strip(" ,;:")
    else:
        tail = re.search(r"\s(\d{1,4})$", rest)
        if tail and out["pages"]:
            out["volume"] = tail.group(1)
            rest = rest[: tail.start()]
    out["venue"] = rest.strip(" ,;:()")[:300]
    return out


def lookup_s2(arxiv_ids: list[str], client: httpx.Client) -> dict[str, dict]:
    """One Semantic Scholar batch request → {arxiv_id: {doi, venue}} for the papers it links
    to a publisher DOI. Same raise-on-no-answer contract as lookup_arxiv."""
    if not arxiv_ids:
        return {}
    response = client.post(
        S2_BATCH,
        params={"fields": S2_FIELDS},
        json={"ids": [f"ARXIV:{i}" for i in arxiv_ids]},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Semantic Scholar answered {response.status_code}")
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Semantic Scholar answered with something other than a list")
    found: dict[str, dict] = {}
    for arxiv_id, row in zip(arxiv_ids, rows, strict=False):
        if not isinstance(row, dict):
            continue
        ids = row.get("externalIds") or {}
        doi = _clean(ids.get("DOI") if isinstance(ids, dict) else "")
        if not doi:
            continue
        venue = (
            (
                (row.get("publicationVenue") or {}).get("name")
                if isinstance(row.get("publicationVenue"), dict)
                else ""
            )
            or (
                (row.get("journal") or {}).get("name")
                if isinstance(row.get("journal"), dict)
                else ""
            )
            or row.get("venue")
            or ""
        )
        found[arxiv_id] = {"doi": doi, "venue": str(venue).strip()[:300], "source": "s2"}
    return found


# --- storing the verdict --------------------------------------------------------------------


def _row(reference: Reference, error: str = "") -> dict:
    return {
        "id": reference.pk,
        "bibtex_key": reference.bibtex_key,
        "title": reference.title,
        "arxiv_id": reference.arxiv_id,
        "published_doi": reference.published_doi,
        "published_venue": reference.published_venue,
        "arxiv_version": reference.extra.get("arxiv_version", ""),
        "checked_at": reference.published_checked_at,
        "error": error,
    }


def _store(reference: Reference, found: dict | None, now) -> None:
    fields = ["published_checked_at", "updated_at"]
    if found and found["doi"] != normalize_doi(reference.published_doi or ""):
        reference.published_doi = found["doi"][:255]
        reference.published_venue = found.get("venue", "")[:300]
        fields += ["published_doi", "published_venue"]
    elif found and found.get("venue") and not reference.published_venue:
        reference.published_venue = found["venue"][:300]
        fields.append("published_venue")
    if found:
        # the arXiv revision the published version matches, and the journal_ref line taken
        # apart (volume, pages, year) for the upgrade and the bibliography
        extra = dict(reference.extra)
        if found.get("version"):
            extra["arxiv_version"] = found["version"]
        parsed = parse_journal_ref(reference.published_venue)
        if parsed["venue"] and (parsed["pages"] or parsed["volume"] or parsed["year"]):
            extra["published_ref"] = parsed
        else:
            extra.pop("published_ref", None)
        if extra != reference.extra:
            reference.extra = extra
            fields.append("extra")
    reference.published_checked_at = now
    reference.save(update_fields=fields)


def check_references(
    references, client: httpx.Client | None = None, pause: float | None = None
) -> dict:
    """Check many preprints in batches: one arXiv request per CHUNK, then one Semantic Scholar
    request for the ids arXiv did not resolve. Returns the summary the API and the tools show:
    checked (asked and answered), published rows (found now or before), errors (papers whose
    chunk no source answered), skipped (not a preprint), stopped (the breaker)."""
    own = client is None
    client = client or _client()
    pause = ARXIV_PAUSE if pause is None else pause
    out = {"checked": 0, "published": [], "errors": 0, "skipped": 0, "stopped": False, "rows": []}
    todo: list[Reference] = []
    for reference in references:
        if is_preprint(reference):
            todo.append(reference)
        else:
            out["skipped"] += 1
            out["rows"].append(_row(reference, "not a preprint"))
    streak = 0
    try:
        for start in range(0, len(todo), CHUNK):
            chunk = todo[start : start + CHUNK]
            by_id = {normalize_arxiv_id(r.arxiv_id): r for r in chunk}
            ids = list(by_id)
            answered = False
            found: dict[str, dict] = {}
            if start and pause:
                time.sleep(pause)
            try:
                found.update(lookup_arxiv(ids, client))
                answered = True
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                log.info("arXiv lookup failed: %s", exc)
            rest = [i for i in ids if i not in found]
            if rest:
                try:
                    found.update(lookup_s2(rest, client))
                    answered = True
                except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                    log.info("Semantic Scholar lookup failed: %s", exc)
            if not answered:
                out["errors"] += len(chunk)
                out["rows"] += [_row(r, "check failed (no source answered)") for r in chunk]
                streak += 1
                if streak >= MAX_CONSECUTIVE_ERRORS:
                    out["stopped"] = True
                    break
                continue
            streak = 0
            now = timezone.now()
            for arxiv_id, reference in by_id.items():
                _store(reference, found.get(arxiv_id), now)
                row = _row(reference)
                out["rows"].append(row)
                out["checked"] += 1
                if reference.published_doi:
                    out["published"].append(row)
    finally:
        if own:
            client.close()
    return out


def check_reference(reference: Reference, client: httpx.Client | None = None) -> dict:
    out = check_references([reference], client, pause=0)
    return out["rows"][0]


def stale_references(days: int = STALE_DAYS, limit: int = SWEEP_LIMIT):
    """Preprints without a published version on record, never checked first, then the oldest
    checks. A preprint whose published version is known is not re-asked."""
    cutoff = timezone.now() - datetime.timedelta(days=max(1, min(int(days), MAX_STALE_DAYS)))
    qs = preprints().filter(published_doi="")
    qs = qs.filter(published_checked_at__isnull=True) | qs.filter(published_checked_at__lt=cutoff)
    return list(
        qs.order_by(F("published_checked_at").asc(nulls_first=True), "pk")[
            : max(1, min(int(limit), 1000))
        ]
    )


def check_stale(days: int = STALE_DAYS, limit: int = SWEEP_LIMIT) -> dict:
    """The sweep: check the stale preprints (bounded). Safe to call every hour."""
    refs = stale_references(days, limit)
    if not refs:
        return {
            "checked": 0,
            "published": [],
            "errors": 0,
            "skipped": 0,
            "stopped": False,
            "rows": [],
        }
    return check_references(refs)


def watch_status() -> dict:
    qs = preprints()
    newest = (
        qs.exclude(published_checked_at__isnull=True)
        .order_by("-published_checked_at")
        .values_list("published_checked_at", flat=True)
        .first()
    )
    return {
        "preprints": qs.count(),
        "published_available": qs.exclude(published_doi="").count(),
        "unchecked": qs.filter(published_checked_at__isnull=True).count(),
        "last_checked_at": newest,
    }


# --- the upgrade ------------------------------------------------------------------------------


class UpgradeConflict(Exception):
    """The published version is already in the library as another reference."""

    def __init__(self, other: Reference):
        super().__init__(f"Already in the library as {other.bibtex_key}.")
        self.other = other


UPGRADE_FIELDS = (
    "entry_type",
    "title",
    "authors",
    "year",
    "venue",
    "abstract",
    "url",
    "openalex_id",
    "citation_count",
)


def upgrade(reference: Reference, doi: str | None = None) -> dict:
    """Make the reference cite the published version: its DOI, venue, year and metadata replace
    the preprint's, the cite key and the arXiv id stay, the preprint's identity is kept in
    extra["preprint"]. Offline, the stored DOI and venue are applied and `metadata` says
    "partial" so a later find-metadata fills the rest. Raises ValueError when no published
    version is known, UpgradeConflict when another reference already carries that DOI."""
    doi = normalize_doi(doi or reference.published_doi or "")
    if not doi:
        raise ValueError("No published version is known for this paper.")
    other = Reference.objects.filter(doi__iexact=doi).exclude(pk=reference.pk).first()
    if other is not None:
        raise UpgradeConflict(other)
    previous = {
        "arxiv_id": reference.arxiv_id,
        "doi": reference.doi,
        "venue": reference.venue,
        "year": reference.year,
        "url": reference.url,
        "entry_type": reference.entry_type,
        "upgraded_at": timezone.now().isoformat(),
    }
    metadata = "full"
    try:
        meta = fetch_metadata_by_doi(doi)
    except MetadataError as exc:
        log.info("upgrade of %s runs offline: %s", reference.bibtex_key, exc)
        parsed = parse_journal_ref(reference.published_venue)
        meta = {
            "doi": doi,
            "entry_type": "article",
            "venue": parsed["venue"] or reference.published_venue,
            "year": parsed["year"],
            "url": f"https://doi.org/{doi}",
            "extra": {k: v for k, v in parsed.items() if k in ("volume", "issue", "pages") and v},
        }
        metadata = "partial"
    reference.doi = doi
    for field in UPGRADE_FIELDS:
        value = meta.get(field)
        if value not in (None, "", []):
            setattr(reference, field, value)
    if reference.venue in ("", "arXiv") and reference.published_venue:
        reference.venue = reference.published_venue
    extra = {**reference.extra, **meta.get("extra", {})}
    extra.pop("needs_metadata", None)
    extra.pop("metadata_error", None)
    extra["preprint"] = previous
    reference.extra = extra
    reference.raw_bibtex = ""  # it described the arXiv entry
    reference.published_doi = ""
    reference.published_venue = ""
    reference.save()
    return {
        "id": reference.pk,
        "bibtex_key": reference.bibtex_key,
        "doi": reference.doi,
        "metadata": metadata,
    }
