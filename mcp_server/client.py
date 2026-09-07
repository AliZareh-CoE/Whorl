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
        try:
            response = client.request(method, path, headers=headers or None, **kwargs)
        except httpx.ConnectError as exc:
            # the desktop app was closed (or the dev server isn't up): say so, instead of
            # httpx's "All connection attempts failed"
            raise AtlasClientError(
                f"Atlas is not reachable at {client.base_url} — is the Atlas app running? ({exc})"
            ) from exc
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


# --- versioned protocol library (Backlog #7) ---


def list_protocols(project: str | None = None):
    params = {"project": project} if project else None
    return _request("GET", "/protocols/", params=params)


def add_protocol(project: str, title: str, body: str = ""):
    return _request("POST", "/protocols/", json={"project": project, "title": title, "body": body})


def new_protocol_version(protocol_id: int, body: str | None = None, title: str | None = None):
    """Create the next version of a protocol; omitted fields carry over from the current one."""
    payload = {}
    if body is not None:
        payload["body"] = body
    if title is not None:
        payload["title"] = title
    return _request("POST", f"/protocols/{protocol_id}/new-version/", json=payload)


# --- Library v2: imports ---


def import_references(text: str, fmt: str = "auto", project: str | None = None):
    """Import pasted BibTeX / CSL-JSON / RIS into the library (deduplicated)."""
    payload = {"text": text, "format": fmt}
    if project:
        payload["project"] = project
    return _request("POST", "/references/import/", json=payload)


def import_from_zotero(project: str | None = None):
    """Import the whole library from the Zotero running on this machine (local API)."""
    payload = {"project": project} if project else {}
    return _request("POST", "/references/import-zotero/", json=payload)


def discover_related(reference_id: int, kind: str = "similar", limit: int = 12):
    """Papers around one reference on OpenAlex: similar, references (cites), or cited_by."""
    return _request(
        "GET", f"/references/{reference_id}/discover/", params={"kind": kind, "limit": limit}
    )


def export_bibtex(reference_ids: list[int] | None = None, project: str | None = None) -> str:
    """BibTeX text for explicit ids, or for a whole project's library."""
    params = {}
    if reference_ids:
        params["ids"] = ",".join(str(i) for i in reference_ids)
    elif project:
        params["project"] = project
    base_url = os.environ.get("ATLAS_API_URL", "http://127.0.0.1:8000").rstrip("/")
    with _client() as client:
        response = client.get(f"{base_url}/api/v1/references/export/", params=params)
    if response.status_code >= 400:
        raise AtlasClientError(f"Atlas API {response.status_code} on /references/export/")
    return response.text


def format_citations(reference_ids: list[int], style: str = "apa"):
    """Formatted bibliography (+ per-entry in-text forms) for reference ids in a citation style."""
    return _request(
        "GET",
        "/references/cite/",
        params={"ids": ",".join(str(i) for i in reference_ids), "style": style},
    )


# --- the owner's Today list ---


def list_todos(include_done: bool = False):
    params = {} if include_done else {"done": "false"}
    return _request("GET", "/todos/", params=params)


def add_todo(text: str, project: str | None = None, due_at: str | None = None):
    payload = {"text": text}
    if project:
        payload["project"] = project
    if due_at:
        payload["due_at"] = due_at
    return _request("POST", "/todos/", json=payload)


def complete_todo(todo_id: int, done: bool = True):
    return _request("PATCH", f"/todos/{todo_id}/", json={"done": done})


def get_reference_tldr(reference_id: int):
    """Section-by-section summary of a paper (from its PDF text, else its abstract)."""
    return _request("GET", f"/references/{reference_id}/tldr/")


def get_reference_usage(reference_id: int):
    """Every note, decision, entry, protocol, capture, manuscript and evidence row that links to or cites the paper."""
    return _request("GET", f"/references/{reference_id}/usage/")


def get_writing_progress(manuscript_id: int, days: int = 30):
    """Words per day, today's delta, the streak and the best day for a manuscript."""
    return _request("GET", f"/manuscripts/{manuscript_id}/progress/", params={"days": days})


def list_bots():
    """Every automation with its enabled state, last result and recent runs."""
    return _request("GET", "/bots/")


def run_bot(slug: str):
    """Run one automation now; returns its result line."""
    return _request("POST", f"/bots/{slug}/action/", json={"action": "run"})


def toggle_bot(slug: str):
    """Flip an automation between enabled and disabled; returns the new state."""
    return _request("POST", f"/bots/{slug}/action/", json={"action": "toggle"})


def reorder_todos(ids: list[int]):
    """The given ids take positions 1..n; the rest follow in their current order."""
    return _request("POST", "/todos/reorder/", json={"ids": ids})


def list_library_tags():
    """Library tags with usage counts."""
    return _request("GET", "/library-tags/")


def tag_references(reference_ids: list[int], tag: str, remove: bool = False):
    """Add (or remove) one tag on many references; the tag is created if missing."""
    return _request(
        "POST",
        "/references/bulk/",
        json={"ids": reference_ids, "action": "untag" if remove else "tag", "value": tag},
    )


def find_duplicates():
    """Probable duplicate clusters in the library with a suggested keep."""
    return _request("GET", "/references/duplicates/")


def merge_references(keep: int, merge: list[int]):
    """Fold references into one (links, tags, notes, PDF move; the rest are deleted)."""
    return _request("POST", "/references/merge/", json={"keep": keep, "merge": merge})


def list_highlights(reference_id: int):
    """Structured highlights of one paper (page, text, comment, colour)."""
    return _request("GET", "/highlights/", params={"reference": reference_id, "page_size": 200})


def add_highlight(
    reference_id: int, text: str, page: int | None = None, project: str = "", comment: str = ""
):
    """Save a highlight; with a project it is mirrored into that project's highlights note."""
    payload = {"reference": reference_id, "text": text, "comment": comment}
    if page:
        payload["page"] = page
    if project:
        payload["project"] = project
    return _request("POST", "/highlights/", json=payload)


def get_highlights_markdown(reference_id: int):
    """All highlights of a paper as one Markdown block."""
    return _request("GET", f"/references/{reference_id}/highlights-markdown/")


def get_reading_notes(reference_id: int):
    """Per-project reading notes for a paper."""
    return _request("GET", f"/references/{reference_id}/reading-notes/")


def set_reading_notes(project_reference_id: int, notes: str):
    """Replace the reading notes on one project link."""
    return _request("PATCH", f"/project-references/{project_reference_id}/", json={"notes": notes})


def fetch_pdf(reference_id: int):
    """Try to attach an open-access PDF (arXiv, then Unpaywall)."""
    return _request("POST", f"/references/{reference_id}/fetch-pdf/")


def search_pdf_text(query: str, project: str = "", limit: int = 30):
    """Papers whose PDF text contains the query, with the first matching page + snippet."""
    params = {"q": query, "limit": limit}
    if project:
        params["project"] = project
    return _request("GET", "/references/text-search/", params=params)


def search_in_pdf(reference_id: int, query: str):
    """Pages of one paper's PDF containing the query, with snippets."""
    return _request("GET", f"/references/{reference_id}/text-search/", params={"q": query})


def get_plan_outline(slug: str):
    """The plan as a Markdown outline with {#id} tokens."""
    return _request("GET", f"/projects/{slug}/outline/")


def set_plan_outline(slug: str, markdown: str, dry_run: bool = False):
    """Make the plan match an outline (dry_run only reports created/renamed/deleted)."""
    return _request(
        "POST", f"/projects/{slug}/outline/", json={"markdown": markdown, "dry_run": dry_run}
    )


def get_roadmap(slug: str):
    """Phases as dated windows with health and a finish forecast."""
    return _request("GET", f"/projects/{slug}/roadmap/")


def set_phase_dates(phase_id: int, start: str | None = None, end: str | None = None):
    """Reschedule a phase (ISO dates; omit one to leave it unchanged)."""
    payload = {}
    if start is not None:
        payload["target_start"] = start
    if end is not None:
        payload["target_end"] = end
    return _request("PATCH", f"/phases/{phase_id}/", json=payload)


def get_week_focus(slug: str):
    """Overdue, due-this-week and next-up items for one project."""
    return _request("GET", f"/projects/{slug}/focus/")


def list_notes(project: str, q: str = ""):
    """Notes of a project (newest edited first), optionally filtered by text."""
    params = {"project": project, "page_size": 100}
    if q:
        params["q"] = q
    return _request("GET", "/notes/", params=params)


def get_note(note_id: int):
    """One note with its body, references and backlinks."""
    return _request("GET", f"/notes/{note_id}/")


def update_note(note_id: int, body: str | None = None, title: str | None = None):
    """Replace a note's body and/or title; [[links]] and @keys are re-synced."""
    payload = {}
    if body is not None:
        payload["body"] = body
    if title is not None:
        payload["title"] = title
    return _request("PATCH", f"/notes/{note_id}/", json=payload)


def get_note_links(note_id: int):
    """Outgoing links, backlinks, references, unresolved links/keys, unlinked mentions."""
    return _request("GET", f"/notes/{note_id}/links/")


def create_note_from_template(project: str, kind: str, reference_id: int | None = None):
    """Create a note from a template (literature needs reference_id)."""
    payload = {"project": project, "kind": kind}
    if reference_id:
        payload["reference"] = reference_id
    return _request("POST", "/notes/from-template/", json=payload)


def export_note(note_id: int, style: str = "apa"):
    """The note as Markdown with a formatted bibliography."""
    return _request("GET", f"/notes/{note_id}/export/", params={"style": style})


def get_manuscript_bibliography(manuscript_id: int):
    """The manuscript's bibliography rows (cite keys, titles)."""
    return _request("GET", f"/manuscripts/{manuscript_id}/bibliography/")


def add_manuscript_reference(manuscript_id: int, reference_id: int, cite_key_override: str = ""):
    """Add a library paper to a manuscript's bibliography."""
    payload = {"reference": reference_id}
    if cite_key_override:
        payload["cite_key_override"] = cite_key_override
    return _request("POST", f"/manuscripts/{manuscript_id}/bibliography/", json=payload)


def remove_manuscript_reference(manuscript_id: int, reference_id: int):
    """Drop a paper from a manuscript's bibliography."""
    _request("DELETE", f"/manuscripts/{manuscript_id}/bibliography/{reference_id}/")
    return {"removed": reference_id}


def manuscript_cite_check(manuscript_id: int):
    """\\cite keys vs the bibliography, with resolvable missing keys."""
    return _request("GET", f"/manuscripts/{manuscript_id}/cite-check/")


def add_submission_event(manuscript_id: int, kind: str, date: str, notes: str = ""):
    """Log a submission event on a manuscript."""
    return _request(
        "POST",
        f"/manuscripts/{manuscript_id}/events/",
        json={"kind": kind, "date": date, "notes": notes},
    )


def log_reviews(manuscript_id: int, text: str, date: str = "", notes: str = ""):
    """Log received reviews → reviews_received event + point-by-point response note."""
    payload = {"text": text, "notes": notes}
    if date:
        payload["date"] = date
    return _request("POST", f"/manuscripts/{manuscript_id}/reviews/", json=payload)


def get_response_progress(manuscript_id: int):
    """Ticked / total reviewer points in the newest response note (None when there is none)."""
    return _request("GET", f"/manuscripts/{manuscript_id}/response-progress/")["progress"]


def get_manuscript_budget(manuscript_id: int):
    """Usage vs venue limits (words, abstract, figures, tables, references, pages)."""
    return _request("GET", f"/manuscripts/{manuscript_id}/budget/")


def set_venue_limits(manuscript_id: int, limits: dict):
    """Store the venue's limits on the manuscript, e.g. {"words": 8000, "figures": 6}."""
    return _request("PATCH", f"/manuscripts/{manuscript_id}/", json={"venue_limits": limits})


def get_dashboard():
    """Everything the dashboard shows: needs-attention, this week everywhere, projects with
    health, stats, milestones, deadlines, heatmap."""
    return _request("GET", "/dashboard/")


def list_inbox():
    """Untriaged captures with detected hints (paper / note / todo / …)."""
    return _request("GET", "/quick-capture/", params={"processed": "false", "page_size": 100})


def convert_capture(
    capture_id: int, target: str, project: str = "", phase_id: int = 0, due: str = ""
):
    """Turn a capture into a paper / note / todo / milestone / decision."""
    payload = {"target": target}
    if project:
        payload["project"] = project
    if phase_id:
        payload["phase"] = phase_id
    if due:
        payload["due"] = due
    return _request("POST", f"/quick-capture/{capture_id}/convert/", json=payload)


def set_review_mark(slug: str, reference, theme, marked: bool = True, note: str = ""):
    """Set one review-matrix cell (theme may be a name; it is created when missing)."""
    return _request(
        "POST",
        f"/projects/{slug}/review-matrix/mark/",
        json={"reference": str(reference), "theme": str(theme), "marked": marked, "note": note},
    )


def add_review_theme(slug: str, name: str):
    """Add a column to the review matrix."""
    return _request("POST", f"/projects/{slug}/review-matrix/themes/", json={"name": name})


def add_hypothesis(project: str, statement: str, status: str = "proposed"):
    """Propose a hypothesis in a project."""
    return _request(
        "POST", "/hypotheses/", json={"project": project, "statement": statement, "status": status}
    )


def set_hypothesis_status(hypothesis_id: int, status: str):
    """Set a hypothesis status (proposed/testing/supported/contradicted/inconclusive/abandoned)."""
    return _request("PATCH", f"/hypotheses/{hypothesis_id}/", json={"status": status})


def add_evidence(
    hypothesis_id: int, direction: str, summary: str, reference_id: int = 0, note_id: int = 0
):
    """Attach evidence (supports/contradicts/mixed) from a paper and/or note to a hypothesis."""
    payload = {"hypothesis": hypothesis_id, "direction": direction, "summary": summary}
    if reference_id:
        payload["reference"] = reference_id
    if note_id:
        payload["note"] = note_id
    return _request("POST", "/evidence/", json=payload)


def log_experiment(
    project: str,
    title: str,
    body: str = "",
    hypothesis_ids: list[int] | None = None,
    date: str = "",
):
    """Add a lab-notebook entry, optionally linked to hypotheses."""
    payload = {"project": project, "title": title, "body": body, "hypotheses": hypothesis_ids or []}
    if date:
        payload["date"] = date
    return _request("POST", "/experiments/", json=payload)


def suggest_review_themes(slug: str):
    """Theme candidates recurring across the project's papers (titles + abstracts)."""
    return _request("GET", f"/projects/{slug}/review-matrix/suggest/")


def get_diagnostics(network: bool = False):
    """Version, paths, LaTeX engine, jobs, update feed, last failed compile, server log tail."""
    return _request("GET", "/diagnostics/" + ("?network=1" if network else ""))


def get_achievements():
    """The achievements ledger: tiers, progress, score, rank, next-up, souls counters."""
    return _request("GET", "/achievements/")
