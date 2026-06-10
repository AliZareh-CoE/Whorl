"""OpenAlex citation-edge sync for a project's references."""

import httpx
from django.utils import timezone

from projects.models import Project

from .models import CitationEdge, CitationSyncState, Reference
from .services import TIMEOUT, USER_AGENT


def _ensure_openalex_ids(references, client: httpx.Client) -> list[Reference]:
    """Fill in missing openalex_ids by DOI lookup (batched OpenAlex filter)."""
    missing = [r for r in references if not r.openalex_id and r.doi]
    for chunk_start in range(0, len(missing), 50):
        chunk = missing[chunk_start : chunk_start + 50]
        doi_filter = "|".join(r.doi for r in chunk)
        response = client.get(
            "https://api.openalex.org/works",
            params={"filter": f"doi:{doi_filter}", "per-page": 50, "select": "id,doi"},
        )
        if response.status_code != 200:
            continue
        by_doi = {r.doi: r for r in chunk}
        for work in response.json().get("results", []):
            doi = (work.get("doi") or "").replace("https://doi.org/", "").lower()
            ref = by_doi.get(doi)
            if ref:
                ref.openalex_id = (work.get("id") or "").rsplit("/", 1)[-1]
                ref.save(update_fields=["openalex_id", "updated_at"])
    return [r for r in references if r.openalex_id]


def sync_project_citations(project: Project) -> CitationSyncState:
    """Fetch citation edges among the project's references from OpenAlex."""
    state, _ = CitationSyncState.objects.get_or_create(project=project)
    state.status = CitationSyncState.Status.SYNCING
    state.message = ""
    state.save()

    references = list(Reference.objects.filter(project_links__project=project))
    try:
        with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
            resolvable = _ensure_openalex_ids(references, client)
            by_openalex = {r.openalex_id: r for r in resolvable}
            edges_created = 0
            for ref in resolvable:
                response = client.get(
                    f"https://api.openalex.org/works/{ref.openalex_id}",
                    params={"select": "id,referenced_works,cited_by_count"},
                )
                if response.status_code != 200:
                    continue
                work = response.json()
                if work.get("cited_by_count") is not None:
                    ref.citation_count = work["cited_by_count"]
                    ref.save(update_fields=["citation_count", "updated_at"])
                for cited_url in work.get("referenced_works", []):
                    cited_ref = by_openalex.get(cited_url.rsplit("/", 1)[-1])
                    if cited_ref and cited_ref != ref:
                        _, created = CitationEdge.objects.get_or_create(citing=ref, cited=cited_ref)
                        edges_created += int(created)
    except httpx.HTTPError as exc:
        state.status = CitationSyncState.Status.FAILED
        state.message = f"OpenAlex unreachable ({exc.__class__.__name__})"
        state.save()
        return state

    state.status = CitationSyncState.Status.DONE
    state.last_synced_at = timezone.now()
    state.message = (
        f"{len(resolvable)}/{len(references)} references matched on OpenAlex; "
        f"{edges_created} new edge(s)"
    )
    state.save()
    return state
