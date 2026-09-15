"""Open-access PDF auto-download.

Four sources, asked one after another until one hands back a real PDF — a later source is
only asked when the earlier ones gave nothing that downloaded: arXiv (a direct PDF for a paper
with an arXiv id), Unpaywall (every open-access location it knows for the DOI), Semantic
Scholar (its own open-access PDF, and the arXiv id of a published paper — stored on the
reference, so the arXiv PDF is tried right there) and OpenAlex (the PDF links of its
locations). Downloads are capped, checked for a real %PDF header, and attached to
Reference.pdf; the outcome and the source that answered are kept in `extra`.
"""

import datetime
import re
from collections.abc import Iterator
from itertools import islice
from time import monotonic

import httpx
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import F, Q
from django.utils import timezone

from .models import Reference
from .services import TIMEOUT, USER_AGENT, normalize_arxiv_id

MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_CANDIDATES = 4  # downloads attempted per paper; the first real PDF wins

# The sweep (#544): papers without a PDF are looked at again once the last answer is older
# than STALE_DAYS, never-looked-at ones first; bounded per run by a count and a wall clock.
STALE_DAYS = 30
SWEEP_LIMIT = 25
BUDGET_SECONDS = 600
DESKTOP_LIMIT = 10
DESKTOP_BUDGET_SECONDS = 120
API_LIMIT = 20
API_BUDGET_SECONDS = 120
OFFLINE_STREAK = 3  # papers in a row with no service answering → the run stops

SOURCE_LABELS = {
    "arxiv": "arXiv",
    "unpaywall": "Unpaywall",
    "s2": "Semantic Scholar",
    "openalex": "OpenAlex",
}
NOT_FOUND = "No open-access PDF found."

UNPAYWALL = "https://api.unpaywall.org/v2/"
S2_PAPER = "https://api.semanticscholar.org/graph/v1/paper/"
S2_FIELDS = "externalIds,openAccessPdf"
OPENALEX_WORKS = "https://api.openalex.org/works/"

_ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:\.pdf)?$", re.I)


def _https(url) -> str:
    """Only ever follow https links handed back by a metadata service."""
    url = url.strip() if isinstance(url, str) else ""
    return url if url.startswith("https://") else ""


def _get_json(client: httpx.Client, url: str, **kwargs):
    """A JSON body, or None when the service did not answer 200 with JSON (never raises)."""
    try:
        response = client.get(url, **kwargs)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def arxiv_pdf_url(reference: Reference) -> str:
    return f"https://arxiv.org/pdf/{reference.arxiv_id}" if reference.arxiv_id else ""


def unpaywall_pdf_urls(doi: str, client: httpx.Client) -> list[str]:
    """Every PDF link Unpaywall knows for the DOI, best location first."""
    body = _get_json(client, f"{UNPAYWALL}{doi}", params={"email": settings.ATLAS_CONTACT_EMAIL})
    if not isinstance(body, dict):
        return []
    locations = [body.get("best_oa_location")] + list(body.get("oa_locations") or [])
    urls: list[str] = []
    for location in locations:
        url = _https(location.get("url_for_pdf")) if isinstance(location, dict) else ""
        if url and url not in urls:
            urls.append(url)
    return urls


def s2_lookup(doi: str, client: httpx.Client) -> tuple[str, str]:
    """(arXiv id, open-access PDF url) from Semantic Scholar for a DOI — either may be empty."""
    headers = {}
    key = getattr(settings, "ATLAS_S2_API_KEY", "")
    if key:
        headers["x-api-key"] = key
    body = _get_json(client, f"{S2_PAPER}DOI:{doi}", params={"fields": S2_FIELDS}, headers=headers)
    if not isinstance(body, dict):
        return "", ""
    ids = body.get("externalIds")
    arxiv_id = normalize_arxiv_id(str(ids.get("ArXiv") or "")) if isinstance(ids, dict) else ""
    pdf = body.get("openAccessPdf")
    url = _https(pdf.get("url")) if isinstance(pdf, dict) else ""
    return arxiv_id, url


def openalex_lookup(doi: str, client: httpx.Client) -> tuple[str, list[str]]:
    """(arXiv id read off an arXiv landing page, PDF urls) from OpenAlex's locations."""
    body = _get_json(
        client, f"{OPENALEX_WORKS}doi:{doi}", params={"mailto": settings.ATLAS_CONTACT_EMAIL}
    )
    if not isinstance(body, dict):
        return "", []
    locations = [body.get("best_oa_location"), body.get("primary_location")] + list(
        body.get("locations") or []
    )
    arxiv_id, urls = "", []
    for location in locations:
        if not isinstance(location, dict):
            continue
        url = _https(location.get("pdf_url"))
        if url and url not in urls:
            urls.append(url)
        if not arxiv_id:
            m = _ARXIV_URL.search(str(location.get("landing_page_url") or ""))
            if m:
                arxiv_id = normalize_arxiv_id(m.group(1))
    return arxiv_id, urls


def _learn_arxiv_id(reference: Reference, arxiv_id: str) -> bool:
    """Store an arXiv id a lookup turned up for a paper that had none. True when stored."""
    if not arxiv_id or reference.arxiv_id:
        return False
    reference.arxiv_id = arxiv_id
    reference.save(update_fields=["arxiv_id", "updated_at"])
    return True


def iter_oa_candidates(reference: Reference, client: httpx.Client) -> Iterator[tuple[str, str]]:
    """(source, url) pairs in the order they are tried; each source is asked only when the
    caller comes back for more, so a hit at Unpaywall never costs a Semantic Scholar call."""
    seen: set[str] = set()

    def fresh(url: str) -> bool:
        if not url or url in seen:
            return False
        seen.add(url)
        return True

    if fresh(arxiv_pdf_url(reference)):
        yield "arxiv", arxiv_pdf_url(reference)
    doi = reference.doi
    if not doi:
        return
    for url in unpaywall_pdf_urls(doi, client):
        if fresh(url):
            yield "unpaywall", url
    arxiv_id, url = s2_lookup(doi, client)
    if _learn_arxiv_id(reference, arxiv_id) and fresh(arxiv_pdf_url(reference)):
        yield "arxiv", arxiv_pdf_url(reference)
    if fresh(url):
        yield "s2", url
    arxiv_id, urls = openalex_lookup(doi, client)
    if _learn_arxiv_id(reference, arxiv_id) and fresh(arxiv_pdf_url(reference)):
        yield "arxiv", arxiv_pdf_url(reference)
    for url in urls:
        if fresh(url):
            yield "openalex", url


def resolve_oa_pdf_url(reference: Reference, client: httpx.Client) -> str | None:
    """The first free-PDF URL a source hands back for this reference, or None."""
    return next((url for _, url in iter_oa_candidates(reference, client)), None)


def _download(client: httpx.Client, url: str) -> tuple[bytes | None, str]:
    """(pdf bytes, "") or (None, why not)."""
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return None, f"Download failed ({exc.__class__.__name__})."
    if response.status_code != 200:
        return None, f"Download failed (HTTP {response.status_code})."
    if len(response.content) > MAX_PDF_BYTES:
        return None, "PDF larger than the 50 MB limit — skipped."
    if not response.content.startswith(b"%PDF"):
        return None, "Resolved URL did not serve a PDF."
    return response.content, ""


def find_pdf(reference: Reference) -> dict:
    """Try to attach an OA PDF. Returns {outcome, attached, source, answered}: `answered` is
    whether any source replied at all (offline, nothing did — then nothing is stamped, so the
    sweep looks again next time). The outcome sentence is also stored in extra as `oa_pdf`,
    with `oa_source` / `oa_tried` / `oa_checked_at`; `pdf_checked_at` and `pdf_source` on the
    row carry the same for the sweep and the rail."""
    if reference.pdf:
        return {
            "outcome": "PDF already attached.",
            "attached": True,
            "source": reference.pdf_source,
            "answered": False,
        }
    source = ""
    tried: list[str] = []
    outcome = NOT_FOUND
    flags = {"answered": False}

    def _seen(response):  # any reply from any source, whatever its status
        flags["answered"] = True

    with httpx.Client(
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        event_hooks={"response": [_seen]},
    ) as client:
        candidates = islice(iter_oa_candidates(reference, client), MAX_CANDIDATES)
        for candidate_source, url in candidates:
            tried.append(candidate_source)
            content, outcome = _download(client, url)
            if content is not None:
                reference.pdf.save(f"{reference.bibtex_key}.pdf", ContentFile(content), save=False)
                source = candidate_source
                outcome = f"PDF attached ({len(content) // 1024} KB) via {SOURCE_LABELS[source]}."
                break
    now = timezone.now()
    extra = {
        **reference.extra,
        "oa_pdf": outcome,
        "oa_checked_at": now.isoformat(),
        "oa_tried": [SOURCE_LABELS[s] for s in dict.fromkeys(tried)],
    }
    if source:
        extra["oa_source"] = source
        reference.pdf_source = source
    else:
        extra.pop("oa_source", None)
    answered = flags["answered"] or bool(source)
    if answered:
        reference.pdf_checked_at = now
    reference.extra = extra
    reference.save()
    return {"outcome": outcome, "attached": bool(source), "source": source, "answered": answered}


def fetch_and_attach_pdf(reference: Reference) -> str:
    """Try to attach an OA PDF; the human-readable outcome (see find_pdf)."""
    return find_pdf(reference)["outcome"]


# --- the sweep (#544): the library fills its own PDFs ---------------------------------------


def lookable_q() -> Q:
    """Papers a source can be asked about: a DOI or an arXiv id."""
    return (Q(doi__isnull=False) & ~Q(doi="")) | Q(arxiv_id__gt="")


def missing_pdfs(qs=None):
    """Papers without a PDF that a source could serve one for."""
    qs = Reference.objects.all() if qs is None else qs
    return qs.filter(Q(pdf="") | Q(pdf__isnull=True)).filter(lookable_q())


def stale_missing(days: int = STALE_DAYS, limit: int = SWEEP_LIMIT):
    """The papers the sweep looks at: without a PDF, never looked at first, then the ones whose
    last answer is older than `days`; at most `limit`."""
    days = max(1, min(int(days), 3650))
    cutoff = timezone.now() - datetime.timedelta(days=days)
    qs = missing_pdfs().filter(Q(pdf_checked_at__isnull=True) | Q(pdf_checked_at__lt=cutoff))
    return list(
        qs.order_by(F("pdf_checked_at").asc(nulls_first=True), "pk")[: max(1, min(int(limit), 500))]
    )


def find_pdfs(references, budget_seconds: float = BUDGET_SECONDS) -> dict:
    """Run the finder over these papers in turn. Returns {checked, attached: [{id, bibtex_key,
    title, source}], not_found, errors, skipped, stopped}. `errors` counts papers no source
    answered for (nothing stamped); after OFFLINE_STREAK of those in a row the run stops with
    stopped="offline", and once `budget_seconds` have passed it stops with stopped="budget" —
    the rest wait for the next sweep."""
    out = {
        "checked": 0,
        "attached": [],
        "not_found": 0,
        "errors": 0,
        "skipped": 0,
        "stopped": "",
    }
    start = monotonic()
    streak = 0
    for reference in references:
        if monotonic() - start > budget_seconds:
            out["stopped"] = "budget"
            break
        if reference.pdf or not (reference.doi or reference.arxiv_id):
            out["skipped"] += 1
            continue
        result = find_pdf(reference)
        out["checked"] += 1
        if result["attached"]:
            out["attached"].append(
                {
                    "id": reference.pk,
                    "bibtex_key": reference.bibtex_key,
                    "title": reference.title,
                    "source": result["source"],
                }
            )
            streak = 0
        elif result["answered"]:
            out["not_found"] += 1
            streak = 0
        else:
            out["errors"] += 1
            streak += 1
            if streak >= OFFLINE_STREAK:
                out["stopped"] = "offline"
                break
    return out


def sweep_missing(
    days: int = STALE_DAYS, limit: int = SWEEP_LIMIT, budget_seconds: float = BUDGET_SECONDS
) -> dict:
    """The sweep: the finder over the stale papers without a PDF (bounded). Safe to run daily —
    once every lookable paper has been asked about within `days` it asks nothing."""
    out = find_pdfs(stale_missing(days, limit), budget_seconds)
    out["status"] = watch_status()
    return out


def watch_status() -> dict:
    """What the rail says: how many papers lack a PDF, how many of those a source could serve,
    how many were never looked at, how many PDFs the finder attached in the last 30 days, and
    when it last got an answer."""
    without = Reference.objects.filter(Q(pdf="") | Q(pdf__isnull=True))
    lookable = missing_pdfs()
    month_ago = timezone.now() - datetime.timedelta(days=30)
    newest = (
        Reference.objects.exclude(pdf_checked_at__isnull=True)
        .order_by("-pdf_checked_at")
        .values_list("pdf_checked_at", flat=True)
        .first()
    )
    return {
        "missing": without.count(),
        "lookable": lookable.count(),
        "unchecked": lookable.filter(pdf_checked_at__isnull=True).count(),
        "found_30d": Reference.objects.exclude(pdf="")
        .exclude(pdf__isnull=True)
        .exclude(pdf_source="")
        .filter(pdf_checked_at__gte=month_ago)
        .count(),
        "last_checked_at": newest,
    }
