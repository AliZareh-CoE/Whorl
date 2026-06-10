"""Open-access PDF auto-download (Owner idea #4).

Resolution order: arXiv (direct PDF) → Unpaywall (best OA location for the DOI).
Downloads are capped, checked for a real %PDF header, and attached to Reference.pdf.
"""

import httpx
from django.conf import settings
from django.core.files.base import ContentFile

from .models import Reference
from .services import TIMEOUT, USER_AGENT

MAX_PDF_BYTES = 50 * 1024 * 1024


def resolve_oa_pdf_url(reference: Reference, client: httpx.Client) -> str | None:
    """Best free-PDF URL for this reference, or None."""
    if reference.arxiv_id:
        return f"https://arxiv.org/pdf/{reference.arxiv_id}"
    if reference.doi:
        try:
            response = client.get(
                f"https://api.unpaywall.org/v2/{reference.doi}",
                params={"email": settings.ATLAS_CONTACT_EMAIL},
            )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        location = response.json().get("best_oa_location") or {}
        return location.get("url_for_pdf") or None
    return None


def fetch_and_attach_pdf(reference: Reference) -> str:
    """Try to attach an OA PDF. Returns a human-readable outcome (also stored in extra)."""
    if reference.pdf:
        return "PDF already attached."
    with httpx.Client(
        timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        url = resolve_oa_pdf_url(reference, client)
        if not url:
            outcome = "No open-access PDF found."
        else:
            try:
                response = client.get(url)
            except httpx.HTTPError as exc:
                response = None
                outcome = f"Download failed ({exc.__class__.__name__})."
            if response is not None:
                if response.status_code != 200:
                    outcome = f"Download failed (HTTP {response.status_code})."
                elif len(response.content) > MAX_PDF_BYTES:
                    outcome = "PDF larger than the 50 MB limit — skipped."
                elif not response.content.startswith(b"%PDF"):
                    outcome = "Resolved URL did not serve a PDF."
                else:
                    reference.pdf.save(
                        f"{reference.bibtex_key}.pdf", ContentFile(response.content), save=False
                    )
                    outcome = f"PDF attached ({len(response.content) // 1024} KB)."
    reference.extra = {**reference.extra, "oa_pdf": outcome}
    reference.save()
    return outcome
