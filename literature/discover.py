"""Discover similar papers on OpenAlex (Backlog #10) — beyond your own library."""

import httpx

from .models import Reference
from .services import TIMEOUT, USER_AGENT, normalize_doi


def _openalex_work_id(reference: Reference, client: httpx.Client) -> str | None:
    if reference.openalex_id:
        return reference.openalex_id
    if reference.doi:
        response = client.get(f"https://api.openalex.org/works/doi:{reference.doi}")
        if response.status_code == 200:
            return (response.json().get("id") or "").rsplit("/", 1)[-1] or None
    return None


def discover_similar(reference: Reference, limit: int = 8) -> list[dict]:
    """OpenAlex related_works for this reference, minus papers already in the library."""
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        work_id = _openalex_work_id(reference, client)
        if not work_id:
            return []
        response = client.get(
            f"https://api.openalex.org/works/{work_id}", params={"select": "related_works"}
        )
        if response.status_code != 200:
            return []
        related_ids = [url.rsplit("/", 1)[-1] for url in response.json().get("related_works", [])]
        if not related_ids:
            return []
        response = client.get(
            "https://api.openalex.org/works",
            params={
                "filter": f"openalex_id:{'|'.join(related_ids[:20])}",
                "select": "id,title,doi,publication_year,cited_by_count,authorships",
                "per-page": 20,
            },
        )
        if response.status_code != 200:
            return []
        works = response.json().get("results", [])

    known_dois = set(Reference.objects.exclude(doi__isnull=True).values_list("doi", flat=True))
    results = []
    for work in works:
        doi = normalize_doi(work.get("doi") or "") if work.get("doi") else ""
        if not doi or doi in known_dois:
            continue
        first_author = ""
        authorships = work.get("authorships") or []
        if authorships:
            first_author = (authorships[0].get("author") or {}).get("display_name", "")
        results.append(
            {
                "doi": doi,
                "title": work.get("title") or "Untitled",
                "year": work.get("publication_year"),
                "citations": work.get("cited_by_count"),
                "first_author": first_author,
            }
        )
    return results[:limit]
