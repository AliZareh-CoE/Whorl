"""The citation watch (#530): new papers that cite the papers in the library, found on OpenAlex,
stored as `CitingWork` rows and shown in the Library's "New citations" feed — the alert feed a
ResearchRabbit or Google Scholar user sets up by e-mail, inside the library, with "which of my
papers does it cite" on every row and one-click Add / Dismiss.

One request per batch of library papers: `works?filter=cites:W1|W2|…,from_publication_date:…`
(the same `|`-joined batching `discover._works_by_ids` uses live), newest first, a bounded
number of pages. Each citing work is linked to the specific library papers it cites
(`referenced_works` ∩ the batch); a work already in the library is recorded against that
reference and is not news.

Rules: a work is deduplicated by OpenAlex id and its first-seen stamp never moves; a request
that fails (offline, a timeout, a non-200 — OpenAlex meters list queries per day) stamps nothing
and counts as an error, with a breaker after three failed batches; a batch that answers moves the
checked stamp of every paper in it, so the next sweep asks only for what is newer.
"""

from __future__ import annotations

import datetime
import html
import logging

import httpx
from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone

from .models import CitingWork, Reference
from .services import TIMEOUT, USER_AGENT, normalize_doi

log = logging.getLogger(__name__)

OPENALEX_WORKS = "https://api.openalex.org/works"
SELECT = (
    "id,title,doi,publication_year,publication_date,cited_by_count,authorships,"
    "primary_location,referenced_works"
)
CHUNK = 50  # library papers per request — the OR limit discover.py batches at
PER_PAGE = 50
MAX_PAGES = 4  # per batch per sweep: a heavily cited paper's first sweep stays bounded
STALE_DAYS = 7
MAX_STALE_DAYS = 3650
SWEEP_LIMIT = 200
FIRST_WINDOW_DAYS = 365  # a paper never checked: citations published in the last year
OVERLAP_DAYS = 45  # OpenAlex indexes works weeks after their publication date
MAX_CONSECUTIVE_ERRORS = 3


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})


def _params(**params) -> dict:
    params = {k.replace("_", "-"): v for k, v in params.items()}  # per-page, not per_page
    params["mailto"] = "owner@localhost"
    key = getattr(settings, "ATLAS_OPENALEX_API_KEY", "")
    if key:
        params["api_key"] = key
    return params


def _short(work_id: str | None) -> str:
    return (work_id or "").rsplit("/", 1)[-1]


def watched(qs=None):
    """Papers the watch can ask about: an OpenAlex id, or a DOI it can be resolved from."""
    qs = Reference.objects.all() if qs is None else qs
    return qs.filter(Q(openalex_id__gt="") | (Q(doi__isnull=False) & ~Q(doi="")))


def open_alerts(qs=None):
    """Citing works that are news: not dismissed, not (yet) in the library."""
    qs = CitingWork.objects.all() if qs is None else qs
    return qs.filter(dismissed_at__isnull=True, reference__isnull=True)


# --- OpenAlex -----------------------------------------------------------------------------------


def ensure_openalex_ids(references: list[Reference], client: httpx.Client) -> list[Reference]:
    """Fill missing OpenAlex ids by DOI (one batched filter request per 50). Raises on a request
    that did not answer, so an exhausted budget is an error, not a silent skip."""
    missing = [r for r in references if not r.openalex_id and r.doi]
    for start in range(0, len(missing), CHUNK):
        chunk = missing[start : start + CHUNK]
        response = client.get(
            OPENALEX_WORKS,
            params=_params(
                filter="doi:" + "|".join(r.doi for r in chunk), per_page=CHUNK, select="id,doi"
            ),
        )
        if response.status_code != 200:
            raise RuntimeError(f"OpenAlex answered {response.status_code}")
        by_doi = {normalize_doi(r.doi): r for r in chunk}
        for work in response.json().get("results", []):
            ref = by_doi.get(normalize_doi((work.get("doi") or "").replace("https://doi.org/", "")))
            if ref and _short(work.get("id")):
                ref.openalex_id = _short(work.get("id"))
                ref.save(update_fields=["openalex_id", "updated_at"])
    return [r for r in references if r.openalex_id]


def lookup_citing(
    work_ids: list[str], since: datetime.date, client: httpx.Client, max_pages: int = MAX_PAGES
) -> list[dict]:
    """Works published on or after `since` that cite any of `work_ids`, newest first, up to
    `max_pages` pages. Raises httpx.HTTPError / RuntimeError / ValueError when OpenAlex did not
    answer (so the caller can tell "none" from "could not ask")."""
    if not work_ids:
        return []
    works: list[dict] = []
    for page in range(1, max_pages + 1):
        response = client.get(
            OPENALEX_WORKS,
            params=_params(
                filter=f"cites:{'|'.join(work_ids)},from_publication_date:{since.isoformat()}",
                sort="publication_date:desc",
                per_page=PER_PAGE,
                page=page,
                select=SELECT,
            ),
        )
        if response.status_code != 200:
            raise RuntimeError(f"OpenAlex answered {response.status_code}")
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("OpenAlex answered with something other than a work list")
        results = body.get("results") or []
        works.extend(w for w in results if isinstance(w, dict))
        if len(results) < PER_PAGE:
            break
    return works


def _date(value) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _store_work(work: dict, by_work_id: dict[str, Reference], now) -> tuple[CitingWork, bool]:
    """Upsert one OpenAlex work as a CitingWork; returns (row, created). Links it to the batch
    papers it cites; when OpenAlex lists none of them (the field can lag), the whole batch
    is linked rather than the alert dropped — OpenAlex asserted it cites at least one."""
    doi = normalize_doi((work.get("doi") or "").replace("https://doi.org/", ""))
    authorships = work.get("authorships") or []
    names = [(a.get("author") or {}).get("display_name", "") for a in authorships[:20]]
    source = ((work.get("primary_location") or {}).get("source") or {}).get("display_name", "")
    defaults = {
        "doi": doi[:255],
        "title": html.unescape(work.get("title") or "Untitled"),
        "authors": [n for n in names if n],
        "year": work.get("publication_year"),
        "published_on": _date(work.get("publication_date")),
        "venue": html.unescape(source or "")[:300],
        "cited_by_count": work.get("cited_by_count"),
    }
    row, created = CitingWork.objects.get_or_create(
        openalex_id=_short(work.get("id")), defaults=defaults
    )
    if not created:
        changed = [k for k, v in defaults.items() if getattr(row, k) != v]
        if changed:
            for k in changed:
                setattr(row, k, defaults[k])
            row.save(update_fields=changed + ["updated_at"])
    cited = [
        by_work_id[_short(w)] for w in work.get("referenced_works") or [] if _short(w) in by_work_id
    ]
    row.cites.add(*(cited or by_work_id.values()))
    if row.reference_id is None:
        own = Reference.objects.filter(
            Q(openalex_id=row.openalex_id) | (Q(doi__iexact=doi) if doi else Q(pk__in=[]))
        ).first()
        if own is not None:
            row.reference = own
            row.save(update_fields=["reference", "updated_at"])
    return row, created


def link_reference(reference: Reference) -> int:
    """A paper that just joined the library: the citing works that *are* this paper stop being
    news (post_save hook). Returns how many rows were linked."""
    match = Q(openalex_id=reference.openalex_id) if reference.openalex_id else Q(pk__in=[])
    if reference.doi:
        match |= Q(doi__iexact=normalize_doi(reference.doi))
    n = 0
    for row in CitingWork.objects.filter(match, reference__isnull=True):
        row.reference = reference
        row.save(update_fields=["reference", "updated_at"])
        n += 1
    return n


def _since(chunk: list[Reference], now) -> datetime.date:
    stamps = [r.cited_by_checked_at for r in chunk]
    if any(s is None for s in stamps):
        return (now - datetime.timedelta(days=FIRST_WINDOW_DAYS)).date()
    return (min(stamps) - datetime.timedelta(days=OVERLAP_DAYS)).date()


def check_references(references, client: httpx.Client | None = None) -> dict:
    """Ask OpenAlex who newly cites these papers, in batches of CHUNK. Returns the summary the
    API and the tools show: checked (papers in batches that answered), new (citing works first
    seen now, as rows), seen (citing works met again), errors (papers in batches that did not
    answer), skipped (no OpenAlex id and no DOI, or a DOI OpenAlex does not know), stopped
    (the breaker)."""
    own = client is None
    client = client or _client()
    out = {"checked": 0, "new": [], "seen": 0, "errors": 0, "skipped": 0, "stopped": False}
    references = list(references)
    todo = [r for r in references if r.openalex_id or r.doi]
    out["skipped"] = len(references) - len(todo)
    streak = 0
    try:
        for start in range(0, len(todo), CHUNK):
            chunk = todo[start : start + CHUNK]
            now = timezone.now()
            try:
                resolved = ensure_openalex_ids(chunk, client)
                by_work_id = {r.openalex_id: r for r in resolved}
                works = lookup_citing(list(by_work_id), _since(chunk, now), client)
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                log.info("citation lookup failed: %s", exc)
                out["errors"] += len(chunk)
                streak += 1
                if streak >= MAX_CONSECUTIVE_ERRORS:
                    out["stopped"] = True
                    break
                continue
            streak = 0
            for work in works:
                if not _short(work.get("id")):
                    continue
                row, created = _store_work(work, by_work_id, now)
                if created and row.reference_id is None:
                    out["new"].append(_row(row))
                elif not created:
                    out["seen"] += 1
            out["skipped"] += len(chunk) - len(resolved)  # a DOI OpenAlex does not know
            for reference in chunk:  # an answered batch stamps every paper in it
                reference.cited_by_checked_at = now
                reference.save(update_fields=["cited_by_checked_at", "updated_at"])
            out["checked"] += len(resolved)
    finally:
        if own:
            client.close()
    return out


def stale_references(days: int = STALE_DAYS, limit: int = SWEEP_LIMIT):
    """Watched papers never checked, then the oldest checks (older than `days`)."""
    cutoff = timezone.now() - datetime.timedelta(days=max(1, min(int(days), MAX_STALE_DAYS)))
    qs = watched()
    qs = qs.filter(cited_by_checked_at__isnull=True) | qs.filter(cited_by_checked_at__lt=cutoff)
    return list(
        qs.order_by(F("cited_by_checked_at").asc(nulls_first=True), "pk")[
            : max(1, min(int(limit), 1000))
        ]
    )


def check_stale(days: int = STALE_DAYS, limit: int = SWEEP_LIMIT) -> dict:
    """The sweep: check the stale papers (bounded). Safe to call every hour — once every paper
    was checked within `days` it asks nothing."""
    refs = stale_references(days, limit)
    if not refs:
        return {"checked": 0, "new": [], "seen": 0, "errors": 0, "skipped": 0, "stopped": False}
    return check_references(refs)


def watch_status() -> dict:
    qs = watched()
    newest = (
        qs.exclude(cited_by_checked_at__isnull=True)
        .order_by("-cited_by_checked_at")
        .values_list("cited_by_checked_at", flat=True)
        .first()
    )
    return {
        "new": open_alerts().count(),
        "dismissed": CitingWork.objects.filter(dismissed_at__isnull=False).count(),
        "watched": qs.count(),
        "unchecked": qs.filter(cited_by_checked_at__isnull=True).count(),
        "last_checked_at": newest,
    }


# --- the feed -----------------------------------------------------------------------------------


def _row(work: CitingWork, cites: list[Reference] | None = None) -> dict:
    cites = list(work.cites.all()) if cites is None else cites
    return {
        "id": work.pk,
        "openalex_id": work.openalex_id,
        "doi": work.doi,
        "title": work.title,
        "authors": work.authors,
        "year": work.year,
        "published_on": work.published_on.isoformat() if work.published_on else None,
        "venue": work.venue,
        "cited_by_count": work.cited_by_count,
        "cites": [{"id": r.pk, "bibtex_key": r.bibtex_key, "title": r.title} for r in cites],
        "first_seen_at": work.created_at,
        "dismissed_at": work.dismissed_at,
        "in_library": work.reference_id,
        "addable": bool(work.doi) and work.reference_id is None,
        "url": f"https://doi.org/{work.doi}"
        if work.doi
        else f"https://openalex.org/{work.openalex_id}",
    }


def alerts(
    project: str = "",
    reference_id: int | None = None,
    dismissed: bool = False,
    limit: int = 100,
) -> dict:
    """The feed: citing works not in the library, open (default) or dismissed, newest
    publication first; narrowed to the papers of one project or to one paper. Rows carry the
    library papers each one cites (one prefetch)."""
    qs = CitingWork.objects.filter(reference__isnull=True)
    qs = (
        qs.filter(dismissed_at__isnull=False) if dismissed else qs.filter(dismissed_at__isnull=True)
    )
    if project:
        qs = qs.filter(cites__project_links__project__slug=project)
    if reference_id:
        qs = qs.filter(cites__pk=reference_id)
    # undated works last on Postgres and SQLite alike (the model's ordering puts them first on
    # one and last on the other)
    qs = (
        qs.distinct()
        .prefetch_related("cites")
        .order_by(F("published_on").desc(nulls_last=True), "-created_at", "pk")
    )
    count = qs.count()
    rows = [_row(w, list(w.cites.all())) for w in qs[: max(1, min(int(limit), 500))]]
    return {"count": count, "results": rows}


def dismiss(ids: list[int], undo: bool = False) -> int:
    """Mark citing works seen (or put them back). Returns how many rows changed."""
    now = timezone.now()
    n = 0
    for row in CitingWork.objects.filter(pk__in=ids):
        target = None if undo else now
        if (row.dismissed_at is None) != (target is None):
            row.dismissed_at = target
            row.save(update_fields=["dismissed_at", "updated_at"])
            n += 1
    return n
