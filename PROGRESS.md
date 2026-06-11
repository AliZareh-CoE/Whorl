# PROGRESS

## Current Status

- **Phase:** Backlog (all 6 phases gated ✅); 30-minute self-improving loop is running
- **Slice in progress:** — (next: Owner idea #14 — world-class file handling [cycle 18])
- **Last completed slice (cycle 6 of the loop; cycle 10 = first audit cycle):** Owner idea #3 — Read aloud: local Piper TTS (en_US-amy-medium, `download_tts_voice` command), `POST /tts/` WAV endpoint, 🔊 buttons on notes and reference abstracts, verified live (188 KB of real speech). Previously: Owner idea #2 security: cache-based login throttle (5 fails/IP → 5-min 429 lockout, verified live), 50 MB upload cap + .pdf-only reference attachments (forms + API), DRF rate throttles, prod HSTS subdomains/preload + referrer policy, X-Frame-Options DENY, cache-leak test hygiene fixture.
- **Priority now (per Owner loop rules in DECISIONS.md):** broken builds → Owner ideas top-down → auto Backlog top-down; every cycle appends ≥1 new idea to the Backlog.
- **Next 3 slices:**
  1. Owner idea #14 — world-class file handling [cycle 18]
  2. Owner idea #15 — lightning search [cycle 19]
  3. AUDIT #2 [cycle 20]; then Owner-idea remainders (#1/#2/#5/#7/#9-#11 second slices) and auto Backlog
- **Broken:** nothing

## Gate reports

### Phase 6 — Claude integration / MCP (2026-06-10)

**Built:** `mcp_server/` — standalone FastMCP stdio server (official `mcp` SDK) whose `client.py` is a pure httpx client over `/api/v1/` configured by `ATLAS_API_URL` + `ATLAS_API_KEY` (an AST test enforces zero Django/SDK imports in the client); the full initial tool set: list_projects, get_project_overview, get_plan, complete_milestone, list_documents, search, add_reference_by_doi, get_reading_queue, set_reading_status, add_note, quick_capture, run_bib_check; supporting API endpoints added with schema descriptions: `/projects/{slug}/overview|plan|reading-queue|bib-report/`, `/api/v1/search/`, `/api/v1/notes/` (wiki-link sync on create/update); README documents `claude mcp add atlas ...` and a 5-step smoke-test conversation.

**Evidence per acceptance criterion** (clean run; real MCP stdio client driving the server against the live app):
- *List projects:* `list_projects` → `['attention-and-memory']`.
- *Check off a milestone:* `get_plan` → milestone id 4 "Pilot data collected (n=12)"; `complete_milestone(4)` → completed_at set; `get_project_overview` progress moved 3/9 (33%) → 4/9 (44%).
- *Add a reference by DOI:* `add_reference_by_doi("10.3758/s13423-017-1271-2", project)` → 201, key `white2017testing` from live Crossref; `get_reading_queue` contains it.
- Also exercised live: `add_note` (with a resolving wiki-link), `quick_capture`, `run_bib_check` (4 categories), `search` (mixed types). All 12 tools listed over the protocol.
- Suite: 152 passed; ruff check + format clean.

**Decisions:** `mcp` SDK added (spec-sanctioned, see DECISIONS.md); client kept SDK-free and Django-free so the API stays the single contract.

**Known gaps → Backlog:** none new. **All six phases are now gated; Backlog work begins top-down.**

### Phase 5 — Research thinking tools + dashboards (2026-06-10)

**Built:** `research` app — Hypothesis ledger (evidence balance per hypothesis, status auto-suggested from supports/contradicts/mixed but only ever set manually), Evidence linked to references/notes/documents, dated markdown ExperimentEntry log linked to hypotheses, Dataset registry (location/version/checksum); cross-project dashboard at `/` — active projects with current phase + progress bars, upcoming milestones and manuscript deadlines across everything (overdue flagged), GitHub-style 26-week activity heatmap from created_at/updated_at across 14 models, monthly stats (papers read, notes written, milestones completed, experiments logged), inbox triage count.

**Evidence per acceptance criterion** (clean run from fresh volume):
- *Dashboard answers "what should I work on today, everywhere?" in one screen:* live `/` shows the active project with its in-progress phase and progress bar, the overdue "Pilot data collected" milestone, the manuscript deadline countdown, monthly stats, and the activity heatmap — all above the fold. Test `test_dashboard_answers_today_everywhere` asserts project, phase, milestone, deadline, stats and heatmap in one response.
- Ledger: live page shows "2 supports · 1 contradicts" with "balance suggests" hint while the stored status (Testing) wins; `TestSuggestedStatus` covers supported/contradicted/inconclusive/manual-wins.
- Experiment log + dataset registry render seeded entries (verified live).
- Suite: 140 passed; ruff check + format clean.

**Decisions:** evidence-balance suggestion is advisory-only (never auto-writes status) — keeps the researcher's judgment authoritative.

**Known gaps → Backlog:** none new.

### Phase 4 — Writing studio (2026-06-10)

**Built:** `writing` app — Manuscript (10-state pipeline, venue, deadline with `days_to_deadline`), ManuscriptReference (with `cite_key_override`), SubmissionEvent; status-column board per project and a global `/writing/` board in the sidebar; per-manuscript bibliography picked from the library with `manuscript.bib` export honoring key overrides; cite checker (upload or paste `.tex` → parses `\cite/\citep/\citet/\parencite/\textcite/\autocite/...` incl. optional args and multi-key) reporting cited-but-missing, in-bib-but-uncited, matched; bib checkers v1 run scoped to the manuscript on its detail page; vertical submission timeline with inline event logging; deadline countdown on the project overview.

**Evidence per acceptance criterion** (clean run from fresh volume):
- *Idea → published with events logged:* `test_full_lifecycle_idea_to_published` walks all five submission events and the status change to published, then asserts the rendered timeline. Live: seeded manuscript detail shows "Submission timeline", "Reviews received", and the deadline countdown.
- *Cite checker flags a deliberately broken `.tex` fixture in tests:* `writing/tests/fixtures/broken.tex` + `test_broken_tex_fixture_flagged_correctly` asserts exact missing keys (anotherghost2021, ghostpaper1999, missingkey2020) and the uncited key; live curl upload of the fixture renders ghostpaper1999/missingkey2020 under "cited, missing from bib" and the "never cited" column.
- Bib export: live `export.bib` contains 6 entries; override keys tested.
- Suite: 129 passed; ruff check + format clean.

**Decisions:** none non-obvious (board is plain status columns — no drag-and-drop JS, status changes via the edit form, consistent with "no JS where a form works").

**Known gaps → Backlog:** none new.

### Phase 3 — Knowledge graph, notes, search (2026-06-10)

**Built:** huey 3 + Redis 7 (compose service, `run_huey` worker, MemoryHuey-immediate in tests); `literature/sync.py` — OpenAlex citation-edge sync (batched DOI→openalex_id resolution, referenced_works edges among project refs, citation_count refresh) with `CitationSyncState` (idle/syncing/done/failed + last-synced message) surfaced on the graph page with a sync button; notes — `Note`/`NoteLink`, markdown editor with live HTMX preview, `[[wiki-links]]` parsed to links on save (unresolved titles reported), backlinks panel, note→reference citations; knowledge graph — `core/graph.py` builder, session endpoint `/projects/{slug}/graph.json` + API `GET /api/v1/projects/{slug}/graph/`, page with 3d-force-graph + 2D toggle, node size from citation count, color from reading status/type, click side panel with link to object; global Postgres FTS (`core/search.py`) across projects, references, notes, documents, decisions, phases, milestones with a sidebar search box.

**Evidence per acceptance criterion** (clean run incl. `run_huey` worker):
- *20+ references → navigable 3D citation graph:* seeded project graph.json = 22 reference nodes, 3 note nodes, links {citation: 33, note-link: 4, note-citation: 5}; graph page loads 3d-force-graph.
- *Creating [[links]] updates graph and backlinks:* created "Gate Note" with `[[Load theory overview]]` via UI → backlinks panel on target shows it; graph.json note-links 4→5.
- *Search returns mixed-type results:* `/search/?q=attention` → 13 results grouped under projects, references, phases, decisions.
- *Background sync with visible state:* created "Sync Gate" project via API with DOIs 10.1038/nature14539 + 10.1162/neco.1997.9.8.1735 → POST graph/sync → huey consumer processed → "Last synced 2026-06-10 22:10 — 2/2 references matched on OpenAlex; 1 new edge(s)"; graph shows the real LeCun→LSTM citation edge.
- Tests: sync (mocked transport, 4 cases), graph builder, wiki-link service (5), notes views (4), search (4). Suite: 118 passed; ruff clean.

**Decisions:** Graph JSON has both a session-auth UI endpoint and the keyed API endpoint, both rendering from one builder. Tests run huey in immediate MemoryHuey mode.

**Known gaps → Backlog:** none new.

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
