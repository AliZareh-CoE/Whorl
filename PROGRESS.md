# PROGRESS

## Current Status

- **Phase:** 1 — The core trio: Projects, Documents, Plans
- **Slice in progress:** 1.1 projects app — Project model, CRUD, list page
- **Last completed slice:** Phase 0 gate
- **Next 3 slices:**
  1. 1.1 projects: Project model + migration + admin + list/create/edit/archive + templates + tests
  2. 1.2 plans: Phase/Milestone/Task/ResearchQuestion models + plan page + HTMX check-off + progress roll-up
  3. 1.3 documents: Folder/Tag/Document models + folder tree + upload/download + tag filters
- **Broken:** nothing

## Gate reports

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
