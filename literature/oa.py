"""Open-access PDF auto-download.

Four sources, asked one after another until one hands back a real PDF — a later source is
only asked when the earlier ones gave nothing that downloaded: arXiv (a direct PDF for a paper
with an arXiv id), Unpaywall (every open-access location it knows for the DOI), Semantic
Scholar (its own open-access PDF, and the arXiv id of a published paper — stored on the
reference, so the arXiv PDF is tried right there) and OpenAlex (the PDF links of its
locations). Downloads are capped, checked for a real %PDF header, and attached to
Reference.pdf; the outcome and the source that answered are kept in `extra`.
"""

import re
from collections.abc import Iterator
from itertools import islice

import httpx
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import Reference
from .services import TIMEOUT, USER_AGENT, normalize_arxiv_id

MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_CANDIDATES = 4  # downloads attempted per paper; the first real PDF wins

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


def fetch_and_attach_pdf(reference: Reference) -> str:
    """Try to attach an OA PDF. Returns a human-readable outcome (also stored in extra as
    `oa_pdf`, with `oa_source` — arxiv / unpaywall / s2 / openalex — when a PDF was attached,
    `oa_tried` naming the sources whose links were downloaded, and `oa_checked_at`)."""
    if reference.pdf:
        return "PDF already attached."
    source = ""
    tried: list[str] = []
    outcome = NOT_FOUND
    with httpx.Client(
        timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True
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
    extra = {
        **reference.extra,
        "oa_pdf": outcome,
        "oa_checked_at": timezone.now().isoformat(),
        "oa_tried": [SOURCE_LABELS[s] for s in dict.fromkeys(tried)],
    }
    if source:
        extra["oa_source"] = source
    else:
        extra.pop("oa_source", None)
    reference.extra = extra
    reference.save()
    return outcome
