"""Discover papers beyond your library on OpenAlex (Backlog #10, Library v2 slice 3).

Three lenses on any reference, ResearchRabbit-style, each row marked with whether it is
already in the library so the UI can offer "+ add" or "open":

- similar     — OpenAlex `related_works`
- references  — what this paper cites (`referenced_works`)
- cited_by    — what cites this paper (`filter=cites:`), most-cited first

OpenAlex meters *list* queries per day (single-work lookups stay cheap), so the lenses fall
back to per-work lookups when the list budget is spent and explain the situation otherwise;
an optional ATLAS_OPENALEX_API_KEY raises the quota.
"""

from __future__ import annotations

import html

import httpx
from django.conf import settings

from .models import Reference
from .services import TIMEOUT, USER_AGENT, normalize_doi

KINDS = ("similar", "references", "cited_by")
SELECT = "id,title,doi,publication_year,cited_by_count,authorships,primary_location"


class DiscoverError(Exception):
    """OpenAlex could not answer — the message is safe to show to the user."""


def _client() -> httpx.Client:
    params = {}
    key = getattr(settings, "ATLAS_OPENALEX_API_KEY", "")
    if key:
        params["api_key"] = key
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, params=params)


def _explain(response: httpx.Response) -> str:
    """A user-facing reason for a non-200 OpenAlex answer."""
    if response.status_code == 429:
        try:
            body = response.json()
        except ValueError:
            body = {}
        retry = body.get("retryAfter")
        when = ""
        if retry:
            try:
                when = f" — try again in about {max(1, round(int(retry) / 3600))} h"
            except (TypeError, ValueError):
                when = ""
        return (
            "OpenAlex's free daily budget for this network is used up"
            f"{when}. Set ATLAS_OPENALEX_API_KEY for a bigger quota."
        )
    return f"OpenAlex answered HTTP {response.status_code}."


def _openalex_work_id(reference: Reference, client: httpx.Client) -> str | None:
    if reference.openalex_id:
        return reference.openalex_id
    if reference.doi:
        response = client.get(f"https://api.openalex.org/works/doi:{reference.doi}")
        if response.status_code == 200:
            work_id = (response.json().get("id") or "").rsplit("/", 1)[-1] or None
            if work_id:  # remember it — the next lens is one request cheaper
                reference.openalex_id = work_id
                reference.save(update_fields=["openalex_id", "updated_at"])
            return work_id
        if response.status_code == 429:
            raise DiscoverError(_explain(response))
    return None


def _rows(works: list[dict], exclude_ids: set[int] | None = None) -> list[dict]:
    """OpenAlex works → UI rows, annotated with library membership (one query)."""
    dois = [normalize_doi(w["doi"]) for w in works if w.get("doi")]
    oa_ids = [(w.get("id") or "").rsplit("/", 1)[-1] for w in works]
    known = {r.doi: r.pk for r in Reference.objects.filter(doi__in=dois).only("id", "doi")}
    known_oa = {
        r.openalex_id: r.pk
        for r in Reference.objects.filter(openalex_id__in=[i for i in oa_ids if i]).only(
            "id", "openalex_id"
        )
    }
    rows = []
    for work in works:
        doi = normalize_doi(work["doi"]) if work.get("doi") else ""
        oa_id = (work.get("id") or "").rsplit("/", 1)[-1]
        library_id = known.get(doi) or known_oa.get(oa_id)
        if exclude_ids and library_id in exclude_ids:
            continue
        authorships = work.get("authorships") or []
        authors = [(a.get("author") or {}).get("display_name", "") for a in authorships[:3]]
        source = ((work.get("primary_location") or {}).get("source") or {}).get("display_name", "")
        rows.append(
            {
                "openalex_id": oa_id,
                "doi": doi,
                "title": html.unescape(work.get("title") or "Untitled"),
                "year": work.get("publication_year"),
                "venue": html.unescape(source or ""),  # OpenAlex ships "K&uuml;nstliche…"
                "authors": [a for a in authors if a],
                "more_authors": max(0, len(authorships) - 3),
                "citations": work.get("cited_by_count"),
                "in_library": library_id is not None,
                "library_id": library_id,
                # rows without a DOI can be shown but not added (metadata needs an identifier)
                "addable": bool(doi) and library_id is None,
            }
        )
    return rows


def _works_by_ids(client: httpx.Client, ids: list[str], limit: int) -> list[dict]:
    """Batch list query (one credit) with a per-work fallback (cheap single lookups) when the
    daily list budget is exhausted — so "similar" and "it cites" keep working all day."""
    ids = ids[:limit]
    works: list[dict] = []
    rate_limited = False
    for start in range(0, len(ids), 50):
        batch = ids[start : start + 50]
        response = client.get(
            "https://api.openalex.org/works",
            params={"filter": f"openalex_id:{'|'.join(batch)}", "select": SELECT, "per-page": 50},
        )
        if response.status_code == 200:
            works.extend(response.json().get("results", []))
            continue
        if response.status_code == 429:
            rate_limited = True
            break
        raise DiscoverError(_explain(response))
    if rate_limited:
        works = []
        for work_id in ids:
            response = client.get(
                f"https://api.openalex.org/works/{work_id}", params={"select": SELECT}
            )
            if response.status_code == 200:
                works.append(response.json())
            elif response.status_code == 429:
                raise DiscoverError(_explain(response))
    return works[:limit]


def discover(
    reference: Reference, kind: str = "similar", limit: int = 12, client=None
) -> list[dict]:
    """Rows for one lens. Raises DiscoverError with a user-facing reason when OpenAlex can't
    answer (offline, rate-limited); a paper OpenAlex doesn't know yields an empty list."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    own = client is None
    client = client or _client()
    try:
        work_id = _openalex_work_id(reference, client)
        if not work_id:
            return []
        if kind == "cited_by":
            response = client.get(
                "https://api.openalex.org/works",
                params={
                    "filter": f"cites:{work_id}",
                    "sort": "cited_by_count:desc",
                    "select": SELECT,
                    "per-page": min(limit, 50),
                },
            )
            if response.status_code != 200:
                raise DiscoverError(_explain(response))
            works = response.json().get("results", [])
        else:
            field = "related_works" if kind == "similar" else "referenced_works"
            response = client.get(
                f"https://api.openalex.org/works/{work_id}", params={"select": field}
            )
            if response.status_code != 200:
                raise DiscoverError(_explain(response))
            ids = [url.rsplit("/", 1)[-1] for url in response.json().get(field, [])]
            works = _works_by_ids(client, ids, limit) if ids else []
    except httpx.HTTPError as exc:
        raise DiscoverError(f"OpenAlex is unreachable ({exc.__class__.__name__}).") from exc
    except ValueError as exc:
        raise DiscoverError("OpenAlex sent an unreadable answer.") from exc
    finally:
        if own:
            client.close()
    return _rows(works, exclude_ids={reference.pk})


def discover_similar(reference: Reference, limit: int = 8) -> list[dict]:
    """Classic detail-page panel: similar papers NOT yet in the library (legacy row shape)."""
    try:
        rows = [r for r in discover(reference, "similar", limit=20) if r["addable"]]
    except DiscoverError:
        return []
    return [
        {
            "doi": r["doi"],
            "title": r["title"],
            "year": r["year"],
            "citations": r["citations"],
            "first_author": r["authors"][0] if r["authors"] else "",
        }
        for r in rows[:limit]
    ]
