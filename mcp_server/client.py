"""Thin HTTP client over the Atlas DRF API.

Deliberately knows nothing about Django or the ORM — the API is the single contract.
Configuration comes from ATLAS_API_URL and ATLAS_API_KEY environment variables.
"""

import mimetypes
import os
from datetime import UTC, datetime
from urllib.parse import urlencode

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


def get_status_update(slug: str, days: int = 7):
    """#482: a paste-ready markdown status update for the project's last `days` days."""
    return _request("GET", f"/projects/{slug}/status-update/", params={"days": days})


def get_plan(slug: str):
    return _request("GET", f"/projects/{slug}/plan/")


def get_plan_drift(slug: str):
    """How far the plan slipped from what was first written (#516)."""
    return _request("GET", f"/projects/{slug}/plan/drift/")


def get_plan_calibration(slug: str):
    """How the project's milestones actually land against their dates (#519)."""
    return _request("GET", f"/projects/{slug}/plan/calibration/")


def get_plan_review(slug: str):
    """The plan review queue and when the plan was last reviewed (#517)."""
    return _request("GET", f"/projects/{slug}/plan/review/")


def finish_plan_review(
    slug: str, kept: int = 0, completed: int = 0, moved: int = 0, skipped: int = 0, note: str = ""
):
    """Record a plan-review sitting (#517)."""
    return _request(
        "POST",
        f"/projects/{slug}/plan/review/",
        json={
            "kept": kept,
            "completed": completed,
            "moved": moved,
            "skipped": skipped,
            "note": note,
        },
    )


def fix_plan_conflicts(slug: str):
    """Push every due date that contradicts a dependency to the day after its blocker (#513)."""
    return _request("POST", f"/projects/{slug}/plan/reschedule-conflicts/")


def set_milestone_dependencies(milestone_id: int, blocked_by: list[int]):
    """Replace what a milestone waits for (#512)."""
    return _request("PATCH", f"/milestones/{milestone_id}/", json={"blocked_by": list(blocked_by)})


def move_milestone(milestone_id: int, due_date: str | None):
    """Set (or clear, with None) a milestone's due date — the move is logged (#516)."""
    return _request("PATCH", f"/milestones/{milestone_id}/", json={"due_date": due_date})


def complete_milestone(milestone_id: int):
    return _request(
        "PATCH",
        f"/milestones/{milestone_id}/",
        json={"completed_at": datetime.now(UTC).isoformat()},
    )


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


def get_reading_progress(reference_id: int):
    """Where the reader left off in a paper, with the per-project started/finished stamps (#523)."""
    return _request("GET", f"/references/{reference_id}/progress/")


def _library_row(row: dict) -> dict:
    """A compact library row for Claude: the identity, the reading state, no abstract."""
    authors = [
        ", ".join(part for part in ((a.get("family") or ""), (a.get("given") or "")) if part)
        for a in (row.get("authors") or [])
        if isinstance(a, dict)
    ]
    return {
        "id": row.get("id"),
        "bibtex_key": row.get("bibtex_key"),
        "title": row.get("title"),
        "authors": authors,
        "year": row.get("year"),
        "venue": row.get("venue"),
        "doi": row.get("doi"),
        "has_pdf": bool(row.get("pdf")),
        "citation_count": row.get("citation_count"),
        "tags": row.get("tags") or [],
        "projects": row.get("projects") or [],
        "progress": row.get("progress"),
        "retraction": (
            {
                "kind": row.get("retraction_kind"),
                "notice": row.get("retraction_notice"),
                "date": row.get("retraction_date"),
            }
            if row.get("retraction_kind")
            else None
        ),
        "notices": list(row.get("notices") or []),
        "preprint": bool(row.get("preprint")),
        "published": (
            {"doi": row.get("published_doi"), "venue": row.get("published_venue")}
            if row.get("published_doi")
            else None
        ),
    }


def _app_base() -> str:
    return os.environ.get("ATLAS_API_URL", "http://127.0.0.1:8000").rstrip("/")


def library_url(**filters) -> str:
    """The address of a Library view (#526): the app's /library page with the same filters the
    address bar carries — empty values and the default sort are left out, so the link equals what
    the page shows in its own address bar once it loads."""
    params = {
        k: v
        for k, v in filters.items()
        if v not in ("", None, 0, False) and not (k == "sort" and v == "added")
    }
    query = urlencode(params)
    return f"{_app_base()}/library" + (f"?{query}" if query else "")


def browse_library(limit: int = 20, **filters):
    """The Library workbench over the API (#524): GET /references/ with the rail's filters
    (q, author, year, year_min, year_max, entry_type, venue, tag, project, reading_status,
    has_pdf, untagged, unfiled, needs_metadata, retracted, notices, preprints,
    published_available, sort). Rows are trimmed to what a listing needs;
    `url` is the same view in the app (#526)."""
    params = {k: v for k, v in filters.items() if v not in ("", None, 0, False)}
    limit = max(1, min(int(limit or 20), 50))
    data = _request("GET", "/references/", params=params)
    rows = data.get("results", []) if isinstance(data, dict) else list(data)
    return {
        "count": data.get("count", len(rows)) if isinstance(data, dict) else len(rows),
        "url": library_url(**params),
        "results": [_library_row(r) for r in rows[:limit]],
    }


def check_retractions(reference_ids=None, days: int = 30, limit: int = 50):
    """The retraction watch (#527): POST /references/check-retractions/ over chosen ids or the
    stale papers; the answer carries the retracted rows and the watch's status."""
    if reference_ids:
        payload: dict = {"ids": [int(i) for i in reference_ids][:50]}
    else:
        payload = {
            "stale": True,
            "days": int(days or 30),
            "limit": max(1, min(int(limit or 50), 50)),
        }
    return _request("POST", "/references/check-retractions/", json=payload)


def retraction_watch_status():
    return _request("GET", "/references/check-retractions/")


def check_preprints(reference_ids=None, days: int = 30, limit: int = 50):
    """The preprint watch (#529): POST /references/check-published/ over chosen ids or the
    stale preprints; the answer carries the published rows and the watch's status."""
    if reference_ids:
        payload: dict = {"ids": [int(i) for i in reference_ids][:50]}
    else:
        payload = {
            "stale": True,
            "days": int(days or 30),
            "limit": max(1, min(int(limit or 50), 50)),
        }
    return _request("POST", "/references/check-published/", json=payload)


def preprint_watch_status():
    return _request("GET", "/references/check-published/")


def upgrade_preprint(reference_id: int, doi: str = ""):
    """Make a preprint cite its published version (#529); the cite key stays."""
    payload = {"doi": doi} if doi else {}
    return _request("POST", f"/references/{reference_id}/upgrade/", json=payload)


def get_new_citations(
    project: str = "", reference_id: int = 0, dismissed: bool = False, limit: int = 50
):
    """The citation watch's feed (#530): papers outside the library that cite papers in it."""
    params: dict = {"limit": max(1, min(int(limit or 50), 500))}
    if project:
        params["project"] = project
    if reference_id:
        params["reference"] = int(reference_id)
    if dismissed:
        params["dismissed"] = "1"
    data = _request("GET", "/references/new-citations/", params=params)
    if isinstance(data, dict):
        data["url"] = library_url(citing=1, reference=reference_id, seen=int(bool(dismissed)))
    return data


def check_citations(reference_ids=None, days: int = 7, limit: int = 50):
    """The citation watch (#530): POST /references/new-citations/check/ over chosen ids or the
    stale papers; the answer carries the works first seen now and the watch's status."""
    if reference_ids:
        payload: dict = {"ids": [int(i) for i in reference_ids][:50]}
    else:
        payload = {
            "stale": True,
            "days": int(days or 7),
            "limit": max(1, min(int(limit or 50), 50)),
        }
    return _request("POST", "/references/new-citations/check/", json=payload)


def citation_watch_status():
    return _request("GET", "/references/new-citations/check/")


def dismiss_citations(work_ids, undo: bool = False):
    """Mark feed rows seen (#530), or put them back with undo=True."""
    payload: dict = {"ids": [int(i) for i in work_ids][:500]}
    if undo:
        payload["undo"] = True
    return _request("POST", "/references/new-citations/dismiss/", json=payload)


def list_feeds():
    """The followed journal / arXiv feeds (#531) with their open-entry counts, plus the feeds'
    status."""
    page = _request("GET", "/feeds/", params={"page_size": 200})
    feeds = page.get("results", page) if isinstance(page, dict) else page
    for row in feeds:
        if isinstance(row, dict) and row.get("id"):
            row["url"] = library_url(feeds=1, feed=row["id"])  # #532: the feed in the app
    status = _request("GET", "/feeds/refresh/").get("status", {})
    return {"feeds": feeds, "status": status, "url": library_url(feeds=1)}


def add_feed(url: str, project: str = "", title: str = ""):
    """Follow a feed (#531): POST /feeds/ — the address is fetched once and refused when it
    does not answer with a feed."""
    payload: dict = {"url": url}
    if project:
        payload["project"] = project
    if title:
        payload["title"] = title
    return _request("POST", "/feeds/", json=payload)


def update_feed(feed_id: int, title: str = "", project: str = "", mute=None):
    """Rename a feed, move it to a project, or set its mute list (#543): PATCH /feeds/{id}/."""
    payload: dict = {}
    if title:
        payload["title"] = title
    if project:
        payload["project"] = project
    if mute is not None:
        payload["mute"] = [str(t) for t in mute][:50]
    row = _request("PATCH", f"/feeds/{int(feed_id)}/", json=payload)
    if isinstance(row, dict) and row.get("id"):
        row["url"] = library_url(feeds=1, feed=row["id"])
    return row


def remove_feed(feed_id: int):
    """Stop following a feed (#531); its entries go with it."""
    _request("DELETE", f"/feeds/{int(feed_id)}/")
    return {"removed": int(feed_id)}


def refresh_feeds(feed_ids=None, hours: int = 12, limit: int = 20):
    """Fetch feeds now (#531): chosen ids (≤ 20) or the stale ones."""
    if feed_ids:
        payload: dict = {"ids": [int(i) for i in feed_ids][:20]}
    else:
        payload = {"hours": int(hours or 12), "limit": max(1, min(int(limit or 20), 20))}
    return _request("POST", "/feeds/refresh/", json=payload)


def get_feed_items(
    feed_id: int = 0,
    project: str = "",
    dismissed: bool = False,
    q: str = "",
    limit: int = 50,
    muted: bool = False,
):
    """The feeds' entries not in the library (#531), newest first; dismissed or muted (#543)
    ones on request."""
    params: dict = {"limit": max(1, min(int(limit or 50), 500))}
    if feed_id:
        params["feed"] = int(feed_id)
    if project:
        params["project"] = project
    if q:
        params["q"] = q
    if dismissed:
        params["dismissed"] = "1"
    elif muted:
        params["muted"] = "1"
    data = _request("GET", "/feeds/items/", params=params)
    if isinstance(data, dict):
        data["url"] = library_url(
            feeds=1,
            feed=feed_id,
            seen=int(bool(dismissed)),
            muted=int(bool(muted and not dismissed)),
            fq=q,
        )
    return data


def add_feed_item(item_id: int, project: str = ""):
    """Add a feed entry's paper to the library by its DOI / arXiv id (#531)."""
    payload: dict = {"id": int(item_id)}
    if project:
        payload["project"] = project
    return _request("POST", "/feeds/items/add/", json=payload)


def dismiss_feed_items(item_ids, undo: bool = False):
    """Mark feed entries seen (#531), or put them back with undo=True."""
    payload: dict = {"ids": [int(i) for i in item_ids][:500]}
    if undo:
        payload["undo"] = True
    return _request("POST", "/feeds/items/dismiss/", json=payload)


def get_reading_now(limit: int = 5):
    """Papers you are in the middle of — a remembered page, not at the end, newest first (#523)."""
    return _request("GET", "/references/reading-now/", params={"limit": limit})


def set_reading_position(
    reference_id: int, page: int, page_count: int | None = None, project: str = ""
):
    """Remember the page the reader is on (#523); page_count when known, project to stamp started_at."""
    payload: dict = {"page": page}
    if page_count:
        payload["page_count"] = page_count
    if project:
        payload["project"] = project
    return _request("POST", f"/references/{reference_id}/progress/", json=payload)


def add_note(project: str, title: str, body: str = ""):
    return _request("POST", "/notes/", json={"project": project, "title": title, "body": body})


def quick_capture(text: str):
    return _request("POST", "/quick-capture/", json={"text": text})


def run_bib_check(slug: str, network: bool = False):
    return _request(
        "GET", f"/projects/{slug}/bib-report/", params={"network": "1" if network else "0"}
    )


def list_prompts(query: str = "", kind: str = ""):
    params = {}
    if query:
        params["q"] = query
    if kind:
        params["kind"] = kind
    return _request("GET", "/prompts/", params=params or None)


def get_prompt(prompt_id: int, values: dict | None = None):
    """One prompt plus its rendered `text` (typed fill-ins expanded from their rows by the
    server; defaults where nothing was given). Fetching a prompt to use it counts as a use
    (#563), so Claude's copies show in the gallery's Recent strip like the owner's."""
    prompt = _request("GET", f"/prompts/{prompt_id}/")
    rendered = _request("POST", f"/prompts/{prompt_id}/render/", json={"values": values or {}})
    return {**prompt, **rendered}


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


def attach_manuscript_asset(manuscript_id: int, path: str, file_path: str):
    """Upload a binary file (figure, PDF, data) from this machine into the manuscript's source
    tree at `path` — replacing an asset that already sits at that path."""
    if not os.path.isfile(file_path):
        raise AtlasClientError(f"No such file on this machine: {file_path}")
    listing = list_manuscript_files(manuscript_id)
    results = listing["results"] if isinstance(listing, dict) and "results" in listing else listing
    existing = next((f for f in results if f["path"] == path), None)
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    with open(file_path, "rb") as handle:
        files = {"asset": (os.path.basename(file_path), handle, content_type)}
        if existing:
            return _request("PATCH", f"/manuscript-files/{existing['id']}/", files=files)
        return _request(
            "POST",
            "/manuscript-files/",
            data={"manuscript": manuscript_id, "path": path, "kind": "asset"},
            files=files,
        )


def set_main_file(file_id: int):
    return _request("PATCH", f"/manuscript-files/{file_id}/", json={"is_main": True})


def compile_manuscript(manuscript_id: int, force: bool = False):
    """Queue a compile. Returns immediately; poll get_compile_status for the result."""
    return _request(
        "POST", f"/manuscripts/{manuscript_id}/compile/", json={"force": force} if force else None
    )


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


def import_projects_folder(
    path: str, dry_run: bool = True, only: str = "", pdfs: str = "library", markdown: str = "notes"
):
    """Bulk-import a folder of existing projects (#535); `only` is a comma-separated list of
    subfolder names."""
    body: dict = {"path": path, "dry_run": dry_run, "pdfs": pdfs, "markdown": markdown}
    names = [o.strip() for o in (only or "").split(",") if o.strip()]
    if names:
        body["only"] = names
    return _request("POST", "/projects/import-folder/", json=body)


def list_project_files(project: str, tags: list[str] | None = None):
    """The project's whole file tree: {folders, files} (general + manuscript sources);
    `tags` keeps only the files carrying every one of them."""
    if tags:
        return _request("GET", f"/projects/{project}/tree/", params={"tag": list(tags)})
    return _request("GET", f"/projects/{project}/tree/")


def _folder_paths(tree: dict) -> dict[str, int]:
    """Every folder's path ("Data/Pilot") → id, walked from the tree's flat folder rows."""
    rows = {f["id"]: f for f in tree.get("folders", [])}
    out: dict[str, int] = {}
    for fid, row in rows.items():
        parts, node = [], row
        while node is not None:
            parts.append(node["name"])
            node = rows.get(node.get("parent_id"))
        out["/".join(reversed(parts))] = fid
    return out


ORGANIZE_ACTIONS = ("move", "tag", "untag", "duplicate", "delete")


def organize_files(
    project: str, paths: list[str], action: str, folder: str = "", tag: str = ""
) -> dict:
    """Act on many files by tree path through the project's bulk endpoint."""
    if action not in ORGANIZE_ACTIONS:
        raise ValueError(f"action must be one of {', '.join(ORGANIZE_ACTIONS)}.")
    wanted = [p.strip().strip("/") for p in paths if p and p.strip().strip("/")]
    if not wanted:
        raise ValueError("Pass at least one file path.")
    tree = list_project_files(project)
    by_path = {f["rel_path"]: f["id"] for f in tree.get("files", []) if f.get("rel_path")}
    missing = [p for p in wanted if p not in by_path]
    if missing:
        raise ValueError(f"No file at {', '.join(missing)} in {project}.")
    body: dict = {"ids": [by_path[p] for p in wanted], "action": action}
    if action == "move":
        target = folder.strip().strip("/")
        if target:
            folders = _folder_paths(tree)
            if target not in folders:
                raise ValueError(f"No folder at {target} in {project}.")
            body["folder"] = folders[target]
        else:
            body["folder"] = None
    elif action in ("tag", "untag"):
        if not tag.strip():
            raise ValueError("Name the tag.")
        body["tag"] = _find_file_tag(project, tag)["id"]
    return _request("POST", f"/projects/{project}/documents/bulk/", json=body)


def _find_file_tag(project: str, name: str) -> dict:
    page = _request("GET", "/tags/", params={"project": project, "page_size": 200})
    wanted = name.strip().lower()
    for row in page.get("results", []):
        if row["name"].lower() == wanted:
            return row
    raise ValueError(f"No tag named {name!r} in {project}.")


def manage_file_tag(
    project: str,
    tag: str,
    rename: str = "",
    color: str = "",
    merge_into: str = "",
    delete: bool = False,
):
    """Rename, recolour, merge or delete one of a project's file tags (exactly one verb)."""
    verbs = [v for v in (bool(rename), bool(color), bool(merge_into), delete) if v]
    if len(verbs) != 1:
        raise ValueError("Pass exactly one of rename, color, merge_into or delete.")
    row = _find_file_tag(project, tag)
    if delete:
        _request("DELETE", f"/tags/{row['id']}/")
        return {"deleted": row["name"], "files": row.get("count", 0)}
    if merge_into:
        target = _find_file_tag(project, merge_into)
        return _request("POST", f"/tags/{row['id']}/merge/", json={"into": target["id"]})
    return _request(
        "PATCH", f"/tags/{row['id']}/", json={"name": rename} if rename else {"color": color}
    )


def read_project_file(document_id: int, version: int = 0, diff: bool = False):
    """Text content of a file node by id — or of an earlier `version` from its history, or
    (`diff`) what changed from that version to now."""
    if version and diff:
        return _request("GET", f"/documents/{document_id}/versions/{version}/diff/")
    params = {"version": version} if version else None
    return _request("GET", f"/documents/{document_id}/content/", params=params)


def write_project_file(project: str, path: str, content: str, note: str = ""):
    """Create or overwrite a general text file at `path` in the project's tree; an overwrite
    files the previous text as a version, labelled by `note`."""
    body = {"path": path, "content": content}
    if note:
        body["note"] = note
    return _request("POST", f"/projects/{project}/write-file/", json=body)


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


def export_references(
    fmt: str = "bib", reference_ids: list[int] | None = None, project: str | None = None, **filters
) -> str:
    """The library (or a selection) as text in bib / ris / csl / csv (#525): explicit ids,
    else the workbench filters (project, q, author, tag, reading_status, …)."""
    params = {"fmt": fmt or "bib"}
    if reference_ids:
        params["ids"] = ",".join(str(i) for i in reference_ids)
    else:
        if project:
            params["project"] = project
        params.update({k: v for k, v in filters.items() if v not in ("", None, 0, False)})
    with _client() as client:
        response = client.get(f"{_app_base()}/api/v1/references/export/", params=params)
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


def list_todos(include_done: bool = False, when: str = ""):
    params = {} if include_done else {"done": "false"}
    if when:
        params["when"] = when  # "today" | "later"
    return _request("GET", "/todos/", params=params)


def add_todo(
    text: str,
    project: str | None = None,
    due_at: str | None = None,
    due: str | None = None,
    repeat: str | None = None,
):
    payload = {"text": text}
    if project:
        payload["project"] = project
    if due_at:
        payload["due_at"] = due_at
    if due:
        payload["due"] = due  # a later day, all-day: tomorrow / monday / next-week / YYYY-MM-DD
    if repeat:
        payload["repeat"] = repeat  # daily / weekdays / weekly / monthly
    return _request("POST", "/todos/", json=payload)


def snooze_todo(todo_id: int, until: str = "tomorrow"):
    """Push a Today item to tomorrow / monday / next-week / weekend / YYYY-MM-DD; "" = today."""
    return _request("POST", f"/todos/{todo_id}/snooze/", json={"until": until})


def complete_todo(todo_id: int, done: bool = True):
    return _request("PATCH", f"/todos/{todo_id}/", json={"done": done})


def get_reference_tldr(reference_id: int):
    """Section-by-section summary of a paper (from its PDF text, else its abstract)."""
    return _request("GET", f"/references/{reference_id}/tldr/")


def get_related_in_library(reference_id: int):
    """The library's most similar papers to this one — local TF-IDF over title + abstract."""
    return _request("GET", f"/references/{reference_id}/related/")


def get_reference_usage(reference_id: int):
    """Every note, decision, entry, protocol, capture, manuscript and evidence row that links to or cites the paper."""
    return _request("GET", f"/references/{reference_id}/usage/")


def duplicate_manuscript(
    manuscript_id: int,
    title: str | None = None,
    project: str | None = None,
    bibliography: bool = True,
):
    """A fresh manuscript from an existing one: sources, assets, venue limits and bibliography links."""
    payload = {"bibliography": bibliography}
    if title:
        payload["title"] = title
    if project:
        payload["project"] = project
    return _request("POST", f"/manuscripts/{manuscript_id}/duplicate/", json=payload)


def draft_related_work(manuscript_id: int, path: str | None = None, overwrite: bool = False):
    """Write a Related-work .tex section drafted from the project's review matrix into the manuscript."""
    payload = {"overwrite": overwrite}
    if path:
        payload["path"] = path
    return _request("POST", f"/manuscripts/{manuscript_id}/related-work/", json=payload)


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


def fetch_pdf(reference_id: int = 0, reference_ids=None, days: int = 30, limit: int = 20):
    """One paper: POST /references/{id}/fetch-pdf/. Otherwise the sweep (#544): POST
    /references/find-pdfs/ over chosen ids (≤ 20) or the stale papers without a PDF."""
    if reference_id:
        return _request("POST", f"/references/{int(reference_id)}/fetch-pdf/")
    if reference_ids:
        payload: dict = {"ids": [int(i) for i in reference_ids][:20]}
    else:
        payload = {
            "stale": True,
            "days": int(days or 30),
            "limit": max(1, min(int(limit or 20), 20)),
        }
    return _request("POST", "/references/find-pdfs/", json=payload)


def pdf_sweep_status():
    return _request("GET", "/references/find-pdfs/")


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


def get_phase_report(phase_id: int):
    """The phase's report card — planned vs actual, landings, drift, questions (#521)."""
    return _request("GET", f"/phases/{phase_id}/report/")


def close_phase(phase_id: int, lessons: str = ""):
    """Close a phase: status done + a decision record with the report and the lessons (#521)."""
    return _request("POST", f"/phases/{phase_id}/close/", json={"lessons": lessons})


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


def list_notes(project: str, q: str = "", tag: str = ""):
    """Notes of a project (newest edited first), optionally filtered by text and/or #tag."""
    params = {"project": project, "page_size": 100}
    if q:
        params["q"] = q
    if tag:
        params["tag"] = tag.lstrip("#")
    return _request("GET", "/notes/", params=params)


def list_note_tags(project: str):
    """Every #tag in the project's notes with a count (#504)."""
    return _request("GET", "/notes/tags/", params={"project": project})


def get_note(note_id: int):
    """One note with its body, references and backlinks."""
    return _request("GET", f"/notes/{note_id}/")


def list_note_revisions(note_id: int):
    """The note's history, newest first (#505)."""
    return _request("GET", f"/notes/{note_id}/revisions/")


def get_note_revision(note_id: int, revision_id: int):
    """One revision's text and its diff against the note now (#505)."""
    return _request("GET", f"/notes/{note_id}/revisions/{revision_id}/")


def restore_note_revision(note_id: int, revision_id: int):
    """Put a revision back on the note; the current state is filed first (#505)."""
    return _request("POST", f"/notes/{note_id}/revisions/{revision_id}/restore/")


def get_project_graph(slug: str):
    """The project's knowledge graph: nodes with filing dates and tags, links, stats (#506)."""
    return _request("GET", f"/projects/{slug}/graph/")


def get_related_notes(note_id: int, limit: int = 5):
    """Unlinked notes this one is about, with reasons (#510)."""
    return _request("GET", f"/notes/{note_id}/related/", params={"limit": limit})


def get_note_outline(note_id: int):
    """Headings (with line numbers) and measure (words, minutes, tasks…) of a note (#507)."""
    return _request("GET", f"/notes/{note_id}/outline/")


def get_note_graph(note_id: int, depth: int = 2):
    """The subgraph within `depth` hops of a note (#503)."""
    return _request("GET", f"/notes/{note_id}/graph/", params={"depth": depth})


def link_mentions(note_id: int, sources=None):
    """Turn unlinked mentions of a note into [[links]] (#502)."""
    payload = {"sources": list(sources)} if sources else {}
    return _request("POST", f"/notes/{note_id}/link-mentions/", json=payload)


def update_note(note_id: int, body: str | None = None, title: str | None = None):
    """Replace a note's body and/or title; [[links]] and @keys are re-synced (#502: a new
    title rewrites every [[old title]] in the project — the reply's `relinked` says how many)."""
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


def submit_manuscript(manuscript_id: int, force: bool = False, date: str = "", notes: str = ""):
    """#469: submit through the pre-flight; 409 with the report unless force."""
    payload = {"force": force, "notes": notes}
    if date:
        payload["date"] = date
    return _request("POST", f"/manuscripts/{manuscript_id}/submit/", json=payload)


def lint_manuscript(manuscript_id: int):
    """#470: the static style lint — findings with file/line/rule/level/message/fix."""
    return _request("GET", f"/manuscripts/{manuscript_id}/lint/")


def search_manuscript(manuscript_id: int, q: str, regex: bool = False, case: bool = False):
    """#476: find in project — every match across the manuscript's text files."""
    params = {"q": q}
    if regex:
        params["regex"] = "1"
    if case:
        params["case"] = "1"
    return _request("GET", f"/manuscripts/{manuscript_id}/search/", params=params)


def replace_in_manuscript(
    manuscript_id: int,
    q: str,
    replacement: str,
    regex: bool = False,
    case: bool = False,
    files: list[str] | None = None,
):
    """#476: replace across the manuscript's text files, saved like an editor save."""
    payload = {"q": q, "replacement": replacement, "regex": regex, "case": case}
    if files:
        payload["files"] = files
    return _request("POST", f"/manuscripts/{manuscript_id}/replace/", json=payload)


def get_venue_turnaround(venue: str, exclude: int | None = None):
    """#474: your own median days from submission to decision at a venue."""
    params = {"venue": venue}
    if exclude is not None:
        params["exclude"] = exclude
    return _request("GET", "/manuscripts/venue-turnaround/", params=params)


def audit_figures(manuscript_id: int):
    """#473: every \\includegraphics with its format, pixels, printed width, dpi, size."""
    return _request("GET", f"/manuscripts/{manuscript_id}/figure-audit/")


def fix_lint(manuscript_id: int, only: list[dict] | None = None):
    """#472: apply the lint's mechanical fixes (all, or the `only` ones)."""
    return _request(
        "POST",
        f"/manuscripts/{manuscript_id}/lint/fix/",
        json={"only": only} if only is not None else {},
    )


def preflight_manuscript(manuscript_id: int, network: bool = False):
    """#466: the submission readiness checks, ok/warn/fail/skip each, `ready` overall."""
    return _request(
        "GET",
        f"/manuscripts/{manuscript_id}/preflight/",
        params={"network": "1"} if network else None,
    )


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


def get_daily_brief():
    """#491: the dashboard as a paste-ready markdown note."""
    return _request("GET", "/dashboard/brief/")


def get_day_activity(date: str | None = None):
    """#492: everything that happened on one day, across every project."""
    return _request("GET", "/dashboard/day/", params={"date": date} if date else None)


def list_inbox(snoozed: bool = False):
    """Untriaged captures with detected hints (paper / note / todo / …); snoozed=True lists
    the ones asleep instead (#495)."""
    return _request(
        "GET",
        "/quick-capture/",
        params={"processed": "false", "snoozed": "true" if snoozed else "false", "page_size": 100},
    )


def enrich_capture(capture_id: int, force: bool = False):
    """Fetch the page title behind a link capture (#499)."""
    return _request(
        "POST", f"/quick-capture/{capture_id}/enrich/", params={"force": "1"} if force else None
    )


def triage_captures(ids, action: str, project: str = "", until: str = ""):
    """Many captures, one action: file / dismiss / snooze / todo / wake (#497)."""
    payload = {"ids": list(ids), "action": action}
    if project:
        payload["project"] = project
    if until:
        payload["until"] = until
    return _request("POST", "/quick-capture/bulk/", json=payload)


def get_inbox_history(limit: int = 30):
    """What the captures that left the inbox became (#496)."""
    return _request("GET", "/quick-capture/history/", params={"limit": limit})


def snooze_capture(capture_id: int, until: str = "tomorrow"):
    """Park a capture until tomorrow / monday / next-week / weekend / YYYY-MM-DD; "" wakes it."""
    return _request("POST", f"/quick-capture/{capture_id}/snooze/", json={"until": until})


def local_tz() -> str:
    """The machine's UTC offset as "+HH:MM" — what a time written in a capture means here."""
    from datetime import datetime

    offset = datetime.now().astimezone().strftime("%z")
    return f"{offset[:3]}:{offset[3:]}" if len(offset) == 5 else ""


def convert_capture(
    capture_id: int,
    target: str,
    project: str = "",
    phase_id: int = 0,
    due: str = "",
    tz: str = "",
):
    """Turn a capture into a paper / note / todo / milestone / decision (#500: `tz` for a time
    written in the capture; the machine's offset when blank)."""
    payload = {"target": target, "tz": tz or local_tz()}
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


def get_backup_destination():
    """#536: the attached drive / sync folder snapshots are copied to, and the suggestions."""
    return _request("GET", "/backup-destination/")


def set_backup_destination(dir: str, enabled: bool = True):
    """#536: attach (or detach with dir="") the backup destination; copies the newest snapshot."""
    return _request("POST", "/backup-destination/", json={"dir": dir, "enabled": enabled})


def take_snapshot(list_only: bool = False):
    """#464: the automatic-snapshot status (and files), or write a new snapshot now."""
    if list_only:
        return _request("GET", "/snapshots/")
    return _request("POST", "/snapshots/")
