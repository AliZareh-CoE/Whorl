# PROGRESS

## Current Status

- **Phase:** 2 — API v1 + Literature core
- **Slice in progress:** 2.1 DRF setup — X-API-Key auth, Phase 1 resources read/write, schema at /api/docs/
- **Last completed slice:** Phase 1 gate
- **Next 3 slices:**
  1. 2.1 api app: DRF + drf-spectacular, X-API-Key auth, serializers/viewsets for projects, phases, milestones, tasks, questions, decisions, folders, tags, documents (incl. upload), pagination 50
  2. 2.2 literature app: Reference model + add-by-DOI/arXiv (Crossref→OpenAlex via httpx) + manual entry + BibTeX paste-import + PDF attach
  3. 2.3 ProjectReference linking + per-project literature page + reading queue + .bib export
- **Broken:** nothing

## Gate reports

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
