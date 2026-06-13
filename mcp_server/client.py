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


def get_timeline(slug: str):
    return _request("GET", f"/projects/{slug}/timeline/")


# --- LaTeX manuscript workbench (beyond-Overleaf B4): edit + compile via the API ---


def list_manuscripts(project: str | None = None):
    params = {"project": project} if project else None
    return _request("GET", "/manuscripts/", params=params)


def get_manuscript(manuscript_id: int):
    return _request("GET", f"/manuscripts/{manuscript_id}/")


def list_manuscript_files(manuscript_id: int):
    return _request("GET", "/manuscript-files/", params={"manuscript": manuscript_id})


def read_manuscript_file(file_id: int):
    return _request("GET", f"/manuscript-files/{file_id}/")


def write_manuscript_file(manuscript_id: int, path: str, content: str):
    """Create the file at `path` (or overwrite it if it already exists)."""
    listing = list_manuscript_files(manuscript_id)
    results = listing["results"] if isinstance(listing, dict) and "results" in listing else listing
    existing = next((f for f in results if f["path"] == path), None)
    if existing:
        return _request("PATCH", f"/manuscript-files/{existing['id']}/", json={"content": content})
    return _request(
        "POST",
        "/manuscript-files/",
        json={"manuscript": manuscript_id, "path": path, "content": content},
    )


def set_main_file(file_id: int):
    return _request("PATCH", f"/manuscript-files/{file_id}/", json={"is_main": True})


def compile_manuscript(manuscript_id: int):
    """Queue a compile. Returns immediately; poll get_compile_status for the result."""
    return _request("POST", f"/manuscripts/{manuscript_id}/compile/")


def get_compile_status(manuscript_id: int):
    """Compile state: status (running/ok/failed), parsed diagnostics, pdf_url, log tail."""
    return _request("GET", f"/manuscripts/{manuscript_id}/compile-status/")


def get_compile_diagnostics(manuscript_id: int):
    return get_compile_status(manuscript_id).get("diagnostics", [])


def latex_word_count(manuscript_id: int):
    return _request("GET", f"/manuscripts/{manuscript_id}/word-count/")


def compile_and_wait(manuscript_id: int, timeout_seconds: int = 120):
    """Compile and block until the result is ready (paced by the status round-trip — no
    time import, so the pure-httpx import constraint holds)."""
    compile_manuscript(manuscript_id)
    deadline = datetime.now(UTC).timestamp() + timeout_seconds
    status = get_compile_status(manuscript_id)
    while status.get("status") == "running" and datetime.now(UTC).timestamp() < deadline:
        status = get_compile_status(manuscript_id)
    return status


# --- file workspace (Owner #30) ---


def list_project_templates():
    """Available project scaffolds (built-in + user-saved)."""
    return _request("GET", "/projects/templates/")


def create_project(name: str, slug: str = "", template: str = ""):
    """Create a project, optionally scaffolded from a template key/name."""
    body = {"name": name, "status": "active"}
    if slug:
        body["slug"] = slug
    if template:
        body["template"] = template
    return _request("POST", "/projects/", json=body)


def list_project_files(project: str):
    """The project's whole file tree: {folders, files} (general + manuscript sources)."""
    return _request("GET", f"/projects/{project}/tree/")


def read_project_file(document_id: int):
    """Text content of a file node by id."""
    return _request("GET", f"/documents/{document_id}/content/")


def write_project_file(project: str, path: str, content: str):
    """Create or overwrite a general text file at `path` in the project's tree."""
    return _request(
        "POST", f"/projects/{project}/write-file/", json={"path": path, "content": content}
    )
