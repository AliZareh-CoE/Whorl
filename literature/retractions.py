"""The retraction watch (#527): every paper with a DOI is checked against Crossref's
retraction / withdrawal / removal notices, the verdict is stored on the reference, and a daily
sweep re-checks the stale ones — so a retracted paper is flagged where it is read, filed and
cited, not only in an opt-in report.

Rules: a Crossref answer with a matching notice sets the flag; an answer with none clears it;
anything else (offline, a timeout, a non-200) leaves the stored verdict and the checked stamp
untouched and reports an error — a sweep on a train must never un-retract a paper.
"""

from __future__ import annotations

import datetime
import logging

import httpx
from django.db.models import F
from django.utils import timezone

from .models import Reference

log = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0)
USER_AGENT = "Atlas (research project manager; mailto:owner@localhost)"
KINDS = ("retraction", "withdrawal", "removal")
# Crossmark's vocabulary: a partial retraction is a retraction here (the notice carries the
# specifics); expressions of concern and corrections are softer signals (backlog #321).
NORMALISE = {"partial_retraction": "retraction"}
STALE_DAYS = 30
SWEEP_LIMIT = 200
MAX_CONSECUTIVE_ERRORS = 5  # an offline sweep stops early instead of timing out 200 times
CROSSREF_WORKS = "https://api.crossref.org/works"


def _date_parts(item: dict) -> datetime.date | None:
    parts = (item.get("updated") or {}).get("date-parts") or []
    if not parts or not parts[0]:
        return None
    head = list(parts[0]) + [1, 1]
    try:
        return datetime.date(int(head[0]), int(head[1]), int(head[2]))
    except (TypeError, ValueError):
        return None


def lookup(doi: str, client: httpx.Client) -> dict | None:
    """Ask Crossref for notices that update this DOI. Returns {kind, notice, date} for the
    first retraction-class notice, None when there is none. Raises httpx.HTTPError (and a
    RuntimeError on a non-200) so the caller can tell "clean" from "could not ask"."""
    response = client.get(CROSSREF_WORKS, params={"filter": f"updates:{doi}", "rows": 5})
    if response.status_code != 200:
        raise RuntimeError(f"Crossref answered {response.status_code}")
    for item in response.json().get("message", {}).get("items", []):
        for update in item.get("update-to", []):
            if not isinstance(update, dict):
                continue
            kind = str(update.get("type", "")).lower()
            kind = NORMALISE.get(kind, kind)
            if kind in KINDS:
                return {
                    "kind": kind,
                    "notice": str(item.get("DOI") or ""),
                    "date": _date_parts(update),
                }
    return None


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})


def _row(reference: Reference, error: str = "") -> dict:
    return {
        "id": reference.pk,
        "bibtex_key": reference.bibtex_key,
        "title": reference.title,
        "retracted": bool(reference.retraction_kind),
        "kind": reference.retraction_kind,
        "notice": reference.retraction_notice,
        "date": reference.retraction_date.isoformat() if reference.retraction_date else None,
        "checked_at": reference.retraction_checked_at,
        "error": error,
    }


def check_reference(reference: Reference, client: httpx.Client | None = None) -> dict:
    """Check one paper and store the verdict. Without a DOI nothing is asked (error "no DOI")."""
    if not reference.doi:
        return _row(reference, "no DOI")
    own = client is None
    client = client or _client()
    try:
        found = lookup(reference.doi, client)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        log.info("retraction check failed for %s: %s", reference.bibtex_key, exc)
        return _row(reference, f"check failed ({exc.__class__.__name__})")
    finally:
        if own:
            client.close()
    reference.retraction_kind = found["kind"] if found else ""
    reference.retraction_notice = (found["notice"] if found else "")[:255]
    reference.retraction_date = found["date"] if found else None
    reference.retraction_checked_at = timezone.now()
    reference.save(
        update_fields=[
            "retraction_kind",
            "retraction_notice",
            "retraction_date",
            "retraction_checked_at",
            "updated_at",
        ]
    )
    return _row(reference)


def check_references(references, client: httpx.Client | None = None) -> dict:
    """Check many papers with one HTTP client. Returns the summary the API and the tools show:
    checked (asked and answered), retracted rows, errors, skipped (no DOI)."""
    own = client is None
    client = client or _client()
    out = {
        "checked": 0,
        "retracted": [],
        "errors": 0,
        "skipped": 0,
        "stopped": False,
        "rows": [],
    }
    streak = 0
    try:
        for reference in references:
            row = check_reference(reference, client)
            out["rows"].append(row)
            if row["error"] == "no DOI":
                out["skipped"] += 1
            elif row["error"]:
                out["errors"] += 1
                streak += 1
                if streak >= MAX_CONSECUTIVE_ERRORS:
                    out["stopped"] = True  # the breaker: Crossref is not answering; try later
                    break
            else:
                streak = 0
                out["checked"] += 1
                if row["retracted"]:
                    out["retracted"].append(row)
    finally:
        if own:
            client.close()
    return out


def stale_references(days: int = STALE_DAYS, limit: int = SWEEP_LIMIT):
    """Papers with a DOI never checked, or checked more than `days` ago — never-checked first,
    then the oldest checks."""
    cutoff = timezone.now() - datetime.timedelta(days=max(1, days))
    qs = Reference.objects.exclude(doi__isnull=True).exclude(doi="")
    qs = qs.filter(retraction_checked_at__isnull=True) | qs.filter(retraction_checked_at__lt=cutoff)
    return list(
        qs.order_by(F("retraction_checked_at").asc(nulls_first=True), "pk")[
            : max(1, min(int(limit), 1000))
        ]
    )


def check_stale(days: int = STALE_DAYS, limit: int = SWEEP_LIMIT) -> dict:
    """The sweep: check the stale papers (bounded). Safe to call every hour — once nothing is
    stale it asks nothing."""
    refs = stale_references(days, limit)
    if not refs:
        return {
            "checked": 0,
            "retracted": [],
            "errors": 0,
            "skipped": 0,
            "stopped": False,
            "rows": [],
        }
    return check_references(refs)


def retracted_references(qs=None):
    qs = Reference.objects.all() if qs is None else qs
    return qs.exclude(retraction_kind="")


def watch_status() -> dict:
    """What the rail and Diagnostics say: how many papers are flagged, how many have never
    been checked, and when the newest check ran."""
    with_doi = Reference.objects.exclude(doi__isnull=True).exclude(doi="")
    newest = (
        with_doi.exclude(retraction_checked_at__isnull=True)
        .order_by("-retraction_checked_at")
        .values_list("retraction_checked_at", flat=True)
        .first()
    )
    return {
        "retracted": Reference.objects.exclude(retraction_kind="").count(),
        "unchecked": with_doi.filter(retraction_checked_at__isnull=True).count(),
        "with_doi": with_doi.count(),
        "last_checked_at": newest,
    }
