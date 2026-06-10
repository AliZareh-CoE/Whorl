# PROGRESS

## Current Status

- **Phase:** 3 — Knowledge graph, notes, search
- **Slice in progress:** 3.1 huey + Redis + citation-edge sync task
- **Last completed slice:** Phase 2 gate
- **Next 3 slices:**
  1. 3.1 huey + Redis in docker-compose; background task fetching citation edges among a project's references from OpenAlex with last-synced/syncing state
  2. 3.2 Notes: Note/NoteLink models, markdown editor + preview, [[wiki-links]] parsing, backlinks panel, link notes to references
  3. 3.3 Graph API (`GET /api/v1/projects/{slug}/graph/`) + 3D graph page (3d-force-graph, 2D toggle, side panel)
- **Broken:** nothing

## Gate reports

### Phase 2 — API v1 + Literature core (2026-06-10)

**Built:** `api` app — DRF + drf-spectacular, sole auth via `X-API-Key` against `ATLAS_API_KEY` (session auth rejected on API; UI login untouched), all Phase 1 resources read/write incl. multipart document upload, pagination 50, schema + Swagger at `/api/docs/`; `literature` app — global Reference library, add by DOI (Crossref → OpenAlex fallback, httpx, 10s timeouts, `MetadataError` with human-readable reasons), add by arXiv ID (arXiv export API — see DECISIONS.md), manual entry with generated `lastnameYEARfirstword` keys, BibTeX paste-import with DOI dedup, PDF attach; ProjectReference linking with reading status + priority, per-project literature page with filters, reading queue (priority-sorted, HTMX inline status change), per-project `.bib` export with stable keys; bib checkers v1 in `literature/services.py` (duplicates DOI-exact + fuzzy-title, missing required fields per entry type, DOI resolution via doi.org, retraction flag via Crossref `updates:` filter) on a report page with offline mode; quick-capture inbox with triage + API; `POST /api/v1/references/by-doi`, `/api/v1/project-references/`, `/api/v1/quick-capture/`.

**Evidence per acceptance criterion** (clean run: fresh volume → compose → migrate → seed_demo → runserver):
- *curl with API key creates a project and adds a reference by DOI end-to-end:* `POST /api/v1/projects/ {"name": "Gate Two Project"}` → 201 slug `gate-two-project`; `POST /api/v1/references/by-doi/ {"doi": "10.1038/nature12373", "project": "gate-two-project"}` → 201, real Crossref metadata, key `kucsko2013nanometre`, linked to project. Also live arXiv: `{"doi": "1706.03762"}` → 201 `vaswani2017attention`.
- *Bib report renders with the four checker categories:* `/projects/attention-and-memory/literature/report/` shows Duplicates, Missing fields, DOI resolution, Retractions; seeded fake DOIs correctly flagged "does not resolve (HTTP 404)"; incomplete seeded entry flagged for missing fields. Tests: `literature/tests/test_services.py::TestCheckers` (8 tests).
- *Reading queue works:* `/literature/queue/` lists only to-read/skimmed, HighPaper before LowPaper (priority order, tested); HTMX status change → 200 and persists.
- Auth: missing/wrong key → 401; session cookie on API → 401; UI still login-only (tested).
- Suite: 98 passed; ruff check + format clean.

**Decisions:** arXiv via arXiv export API (OpenAlex 404s DataCite DOIs — verified live); `doi` is the unique nullable identity, `arxiv_id`/`openalex_id` plain strings.

**Known gaps → Backlog:** none new (OpenAlex enrichment of arXiv records arrives naturally with Phase 3 citation sync).

### Phase 1 — Projects, Documents, Plans (2026-06-10)

**Built:** Project CRUD with status/color/position, archive action, slug auto-generation; DecisionRecord log (list/create/edit/delete, markdown rendering via markdown+nh3); Project Overview (current phase, progress bar, next 5 milestones with overdue flags, recent documents, recent decisions, at-a-glance counts); plans app (Phase/Milestone/Task/ResearchQuestion, plan page with HTMX check-off for milestones and tasks, progress roll-up milestone→phase→project with OOB progress-bar update, overdue highlighting); documents app (nested folders with cycle-safe moves, per-parent unique names, upload into any folder, tags with per-project uniqueness, filter by folder/tag/all, forced-attachment download); `seed_demo` builds a realistic 4-phase psychology study exercising everything.

**Evidence per acceptance criterion** (clean run: fresh volume → `docker compose up -d --wait` → `migrate` → `seed_demo` → `runserver`; all via curl with a logged-in session, no admin):
- Create a project: `POST /projects/new/` → 302 to `/projects/gate-test-project/`.
- Build a 4-phase plan: 4× `POST .../plan/phases/new/` → 302 each; plan page renders all four.
- Upload documents into nested folders: created `Outer` → `Inner` (parent=Outer), uploaded into Inner → 302; doc listed under `?folder=Inner`; download → 200 with `Content-Disposition: attachment`.
- Check off milestones, progress propagates: `POST .../milestones/{pk}/toggle/` → response contains "1/2 milestones" in the phase card **and** OOB `#project-progress`; overview then shows "1/2 milestones".
- Record a decision: `POST .../decisions/new/` → 302; decision list shows it.
- Tests cover roll-up and nesting: `plans/tests/test_plans.py::TestProgressRollup` (4 tests), `documents/tests/test_documents.py::TestFolderNesting` (5 tests). Full suite: 44 passed; ruff check + format clean.
- Seeded project: overview shows "Current phase: Experimental design & pilot"; plan page highlights the overdue pilot milestone.

**Decisions:** Folder delete uses `on_delete=SET_NULL` for documents (files survive at project root) but cascades subfolders — logged in DECISIONS.md. HTMX toggle returns the phase card partial plus an out-of-band project progress bar, keeping one source of truth for markup.

**Known gaps → Backlog:** none new.

### Phase 0 — Scaffold (2026-06-10)

**Built:** settings split (base/dev/prod) on django-environ; docker-compose Postgres 16; Django 5.2 `LoginRequiredMiddleware` (all pages require login, exactly one superuser); base template with fixed left sidebar + breadcrumb block; Tailwind v4 standalone CLI via `make css`; pytest + ruff configured; `seed_demo` stub; README quick start.

**Evidence per acceptance criterion:**
- `docker compose up -d --wait` → healthy; `manage.py migrate` applied cleanly on a fresh volume.
- Styled login page: `curl http://127.0.0.1:8000/login/` → 200, contains tagline; `static/css/app.css` built by Tailwind CLI.
- Login required: `curl /` anonymous → 302 to `/login/?next=/`; POST credentials → 302 to `/` and dashboard renders ("Dashboard" present).
- Empty dashboard shell: `core:dashboard` at `/`, smoke-tested in `core/tests/test_smoke.py::test_dashboard_renders_when_logged_in`.
- Tests & lint: `pytest -q` → 5 passed; `ruff check .` and `ruff format --check .` clean.

**Decisions:** Python 3.12 via uv (see DECISIONS.md). Used Django 5.1+ built-in `LoginRequiredMiddleware` instead of a custom middleware/mixin — less code, contrib login view is auto-exempt.

**Known gaps → Backlog:** none.
