"""Thin HTTP client over the Atlas DRF API.

Deliberately knows nothing about Django or the ORM — the API is the single contract.
Configuration comes from ATLAS_API_URL and ATLAS_API_KEY environment variables.
"""

import os
from datetime import UTC, datetime

import httpx


class AtlasClientError(Exception):
    pass


def _client() -> httpx.Client:
    base_url = os.environ.get("ATLAS_API_URL", "http://127.0.0.1:8000").rstrip("/")
    api_key = os.environ.get("ATLAS_API_KEY", "")
    if not api_key:
        raise AtlasClientError("ATLAS_API_KEY is not set")
    return httpx.Client(
        base_url=f"{base_url}/api/v1",
        headers={"X-API-Key": api_key},
        timeout=httpx.Timeout(30.0),
    )


# GET responses remembered per (path, params): the API sends weak ETags, so repeat
# reads cost a 304 round-trip instead of a re-serialization.
_etag_cache: dict[tuple, tuple[str, object]] = {}


def _cache_key(path: str, params) -> tuple:
    return (path, tuple(sorted((params or {}).items())))


def _request(method: str, path: str, **kwargs):
    cache_key = None
    headers = {}
    if method == "GET":
        cache_key = _cache_key(path, kwargs.get("params"))
        cached = _etag_cache.get(cache_key)
        if cached:
            headers["If-None-Match"] = cached[0]
    with _client() as client:
        response = client.request(method, path, headers=headers or None, **kwargs)
    if response.status_code == 304 and cache_key:
        return _etag_cache[cache_key][1]
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:300]
        raise AtlasClientError(f"Atlas API {response.status_code} on {path}: {detail}")
    if response.status_code == 204:
        return None
    data = response.json()
    if cache_key is not None and response.headers.get("ETag"):
        if len(_etag_cache) >= 256:  # bound memory in long-lived sessions
            _etag_cache.pop(next(iter(_etag_cache)))
        _etag_cache[cache_key] = (response.headers["ETag"], data)
    return data


def list_projects():
    return _request("GET", "/projects/")


def get_project_overview(slug: str):
    return _request("GET", f"/projects/{slug}/overview/")


def get_plan(slug: str):
    return _request("GET", f"/projects/{slug}/plan/")


def complete_milestone(milestone_id: int):
    return _request(
        "PATCH",
        f"/milestones/{milestone_id}/",
        json={"completed_at": datetime.now(UTC).isoformat()},
    )


def list_documents(slug: str):
    return _request("GET", "/documents/", params={"project": slug})


def search(query: str):
    return _request("GET", "/search/", params={"q": query})


def add_reference_by_doi(doi: str, project: str | None = None):
    payload = {"doi": doi}
    if project:
        payload["project"] = project
    return _request("POST", "/references/by-doi/", json=payload)


def get_reading_queue(slug: str):
    return _request("GET", f"/projects/{slug}/reading-queue/")


def set_reading_status(project_reference_id: int, status: str):
    return _request(
        "PATCH",
        f"/project-references/{project_reference_id}/",
        json={"reading_status": status},
    )


def add_note(project: str, title: str, body: str = ""):
    return _request("POST", "/notes/", json={"project": project, "title": title, "body": body})


def quick_capture(text: str):
    return _request("POST", "/quick-capture/", json={"text": text})


def run_bib_check(slug: str, network: bool = False):
    return _request(
        "GET", f"/projects/{slug}/bib-report/", params={"network": "1" if network else "0"}
    )


def list_prompts(query: str = ""):
    params = {"q": query} if query else None
    return _request("GET", "/prompts/", params=params)


def get_prompt(prompt_id: int):
    return _request("GET", f"/prompts/{prompt_id}/")


def get_review_matrix(slug: str):
    return _request("GET", f"/projects/{slug}/review-matrix/")


def get_weekly_review(project: str | None = None, weeks_back: int = 0):
    params = {"weeks_back": weeks_back}
    if project:
        params["project"] = project
    return _request("GET", "/weekly-review/", params=params)


def get_synthesis_scaffold(slug: str):
    return _request("GET", f"/projects/{slug}/synthesis/")
