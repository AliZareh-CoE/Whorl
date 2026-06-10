# ATLAS — Agent Build Prompt

> **How to use this file:** Save it as `CLAUDE.md` in the root of an empty git repository, open Claude Code there, and say: *"Read CLAUDE.md and begin Phase 0."* This build is **fully self-supervised** — the owner does not monitor it. You verify your own work, gate your own phases (§8), record state in `PROGRESS.md`, and keep going without asking for review. Whenever the owner runs the `/goal` slash command, you re-enter this loop. This document is the permanent source of truth: re-read the relevant sections at the start of every session, and never build ahead of the current phase.

---

## 1. Mission

You are building **Atlas** (working name — the owner may rename it): a self-hosted, single-user, research-oriented project management platform built with Django.

The owner is a researcher who dislikes existing tools (Jira, Monday, etc.) because they are task-soup: noisy, badly organized, and built for sprint teams rather than for research. Atlas is the opposite. The guiding metaphor:

> **Atlas is to project management what Django is to web frameworks** — batteries included, strong conventions, everything has exactly one obvious place.

### Product values — consult these when making any design decision

1. **A place for everything.** Every object lives inside exactly one Project. Every page answers "where is what, and how is it going?" at a glance.
2. **Research-first.** Phases, literature, hypotheses, decisions, and manuscripts are first-class citizens. Tasks are optional leaf nodes, never the center of the product.
3. **Plans over backlogs.** A project is driven by a written plan (phases → milestones → optional tasks). Progress rolls up visually from milestones to phases to the project.
4. **Calm, organized UI.** Dense but quiet. No gamification, no notification spam, no clutter.
5. **Machine-friendly.** Everything available in the UI is also available through the API, because Claude (via MCP) will be a daily collaborator in this system.
6. **Convention over configuration.** Pick one good way to do each thing. Do not build settings screens or theming systems.

### Non-goals — do not build these

- Multi-tenancy, teams, sharing, permissions beyond a single login, billing
- Real-time collaboration or websockets
- Native mobile apps (a responsive web UI is sufficient)
- A React/Vue SPA or any Node.js build pipeline

---

## 2. Tech stack (locked)

Do **not** add dependencies beyond this list without raising it at a phase gate.

| Concern | Choice |
|---|---|
| Language / framework | Python 3.12+, Django 5.x |
| Database | PostgreSQL 16 via docker-compose, psycopg 3 |
| API | Django REST Framework + drf-spectacular (OpenAPI schema + docs page) |
| Frontend | Django templates + HTMX 2 + Alpine.js 3 (CDN), Tailwind CSS via the standalone CLI (no Node project) |
| Background jobs | None until Phase 3; then huey + Redis |
| File storage | Local filesystem via `FileField` under `MEDIA_ROOT`, organized per project |
| Bib & metadata | bibtexparser, httpx; Crossref and OpenAlex public APIs |
| Graph view | 3d-force-graph + three.js via CDN |
| Markdown | `markdown` for rendering, `nh3` for sanitizing |
| Config | django-environ, `.env` file, 12-factor style settings |
| Testing | pytest, pytest-django, factory-boy |
| Lint / format | ruff (`ruff check` and `ruff format`) |

---

## 3. Repository layout & architecture

```
atlas/
├── CLAUDE.md                  # this file
├── README.md                  # always-current run instructions
├── DECISIONS.md               # running decision log for the build itself
├── docker-compose.yml         # postgres (+ redis from Phase 3)
├── pyproject.toml             # deps, ruff config, pytest config
├── manage.py
├── config/                    # Django project package
│   ├── settings/              # base.py, dev.py, prod.py
│   └── urls.py
├── templates/                 # global base templates
├── static/                    # css output, vendored js if needed
├── core/        # TimeStampedModel, dashboard, shared template tags, global search (later)
├── projects/    # Project, DecisionRecord
├── documents/   # Folder, Document, Tag
├── plans/       # Phase, Milestone, Task, ResearchQuestion
├── literature/  # Reference, ProjectReference, CitationEdge, metadata + bib services
├── writing/     # Manuscript, ManuscriptReference, SubmissionEvent, bib checkers
├── notes/       # Note, NoteLink, QuickCapture
├── research/    # Hypothesis, Evidence, ExperimentEntry, Dataset (Phase 5)
├── api/         # DRF serializers, viewsets, routers, API-key auth
└── mcp_server/  # standalone MCP server package (Phase 6)
```

### Code conventions

- Business logic lives in a `services.py` (and `selectors.py` if useful) per app. Views stay thin.
- Class-based views for standard CRUD; function-based views for custom pages. Every URL is namespaced (`projects:detail`).
- **Every model is registered in the Django admin** with sensible `list_display` — the admin is the free back office.
- HTMX is used only where it removes a full page reload (checking off a milestone, expanding a folder, inline status changes, quick capture). A normal Django form is the default. No JS where a form works.
- All pages require login. There is exactly one user: the superuser.
- Slugs for projects; integer PKs elsewhere are fine.

---

## 4. Data model

These are the canonical starting sketches. Refine field details while implementing, but keep names and relationships unless you log a decision in `DECISIONS.md`.

### core

```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
```

### projects (Phase 1)

```python
class Project(TimeStampedModel):
    name = CharField(max_length=200)
    slug = SlugField(unique=True)
    description = TextField(blank=True)              # markdown
    status = CharField(choices=PLANNING/ACTIVE/PAUSED/COMPLETE/ARCHIVED, default=ACTIVE)
    color = CharField(max_length=7, default="#4f46e5")  # accent color
    position = PositiveIntegerField(default=0)       # manual ordering

class DecisionRecord(TimeStampedModel):              # the research decision log
    project = FK(Project, related_name="decisions")
    title = CharField(max_length=300)
    context = TextField(blank=True)                  # markdown: the situation
    decision = TextField()                           # markdown: what was decided
    alternatives = TextField(blank=True)             # markdown: what was rejected and why
    decided_on = DateField(default=date.today)
```

### documents (Phase 1)

```python
class Folder(TimeStampedModel):
    project = FK(Project, related_name="folders")
    parent = FK("self", null=True, blank=True, related_name="children")
    name = CharField(max_length=200)
    # unique together: (project, parent, name)

class Tag(TimeStampedModel):
    project = FK(Project, related_name="tags")
    name = CharField(max_length=60)                  # unique per project
    color = CharField(max_length=7, blank=True)

class Document(TimeStampedModel):
    project = FK(Project, related_name="documents")
    folder = FK(Folder, null=True, blank=True, related_name="documents")  # null = project root
    file = FileField(upload_to=project_document_path)
    title = CharField(max_length=300)
    description = TextField(blank=True)
    tags = M2M(Tag, blank=True)
    file_size = PositiveBigIntegerField(editable=False)   # set on save
    content_type = CharField(max_length=100, editable=False)
```

### plans (Phase 1)

```python
class Phase(TimeStampedModel):
    project = FK(Project, related_name="phases")
    name = CharField(max_length=200)
    order = PositiveIntegerField()
    status = CharField(choices=NOT_STARTED/IN_PROGRESS/BLOCKED/DONE, default=NOT_STARTED)
    objective = TextField(blank=True)                # markdown
    target_start = DateField(null=True, blank=True)
    target_end = DateField(null=True, blank=True)
    # progress property: completed milestones / total milestones

class Milestone(TimeStampedModel):
    phase = FK(Phase, related_name="milestones")
    title = CharField(max_length=300)
    due_date = DateField(null=True, blank=True)
    completed_at = DateTimeField(null=True, blank=True)
    notes = TextField(blank=True)

class Task(TimeStampedModel):                        # optional leaf nodes only
    milestone = FK(Milestone, related_name="tasks")
    title = CharField(max_length=300)
    done = BooleanField(default=False)
    due_date = DateField(null=True, blank=True)
    order = PositiveIntegerField(default=0)

class ResearchQuestion(TimeStampedModel):
    project = FK(Project, related_name="questions")
    question = TextField()
    status = CharField(choices=OPEN/PARTIALLY_ANSWERED/ANSWERED/ABANDONED, default=OPEN)
    phases = M2M(Phase, blank=True)
```

### literature (Phase 2–3)

```python
class Reference(TimeStampedModel):                   # GLOBAL library, shared across projects
    doi = CharField(unique=True, null=True, blank=True)
    arxiv_id = CharField(null=True, blank=True)
    openalex_id = CharField(null=True, blank=True)
    bibtex_key = CharField(unique=True)              # generated: lastnameYEARfirstword
    entry_type = CharField(default="article")        # article/inproceedings/book/misc...
    title = TextField()
    authors = JSONField(default=list)                # [{"family": "...", "given": "..."}]
    year = PositiveIntegerField(null=True)
    venue = CharField(blank=True)
    abstract = TextField(blank=True)
    url = URLField(blank=True)
    pdf = FileField(null=True, blank=True)
    raw_bibtex = TextField(blank=True)
    extra = JSONField(default=dict)                  # anything else from metadata APIs
    citation_count = PositiveIntegerField(null=True)

class ProjectReference(TimeStampedModel):            # per-project link + reading state
    project = FK(Project, related_name="project_references")
    reference = FK(Reference, related_name="project_links")
    reading_status = CharField(choices=TO_READ/SKIMMED/READ/ANNOTATED, default=TO_READ)
    priority = CharField(choices=LOW/NORMAL/HIGH, default=NORMAL)
    notes = TextField(blank=True)
    # unique together: (project, reference)

class CitationEdge(models.Model):                    # citing -> cited, fetched from OpenAlex
    citing = FK(Reference, related_name="outgoing_citations")
    cited = FK(Reference, related_name="incoming_citations")
    # unique together: (citing, cited)
```

### writing (Phase 4)

```python
class Manuscript(TimeStampedModel):
    project = FK(Project, related_name="manuscripts")
    title = CharField(max_length=400)
    status = CharField(choices=IDEA/OUTLINING/DRAFTING/INTERNAL_REVIEW/SUBMITTED/
                       UNDER_REVIEW/REVISION/ACCEPTED/PUBLISHED/SHELVED)
    target_venue = CharField(blank=True)
    deadline = DateField(null=True, blank=True)
    abstract = TextField(blank=True)
    repo_url = URLField(blank=True)
    references = M2M(Reference, through="ManuscriptReference", blank=True)

class ManuscriptReference(models.Model):
    manuscript = FK(Manuscript); reference = FK(Reference)
    cite_key_override = CharField(blank=True)

class SubmissionEvent(TimeStampedModel):
    manuscript = FK(Manuscript, related_name="events")
    kind = CharField(choices=SUBMITTED/DESK_REJECT/REVIEWS_RECEIVED/REVISION_SUBMITTED/
                     ACCEPTED/REJECTED/PUBLISHED/NOTE)
    date = DateField(); notes = TextField(blank=True)
```

### notes (Phase 3)

```python
class Note(TimeStampedModel):
    project = FK(Project, related_name="notes")
    title = CharField(max_length=300, unique_per_project)
    body = TextField(blank=True)                     # markdown; [[Title]] creates links
    references = M2M(Reference, blank=True)

class NoteLink(models.Model):                        # parsed from [[wiki-links]] on save
    source = FK(Note, related_name="outgoing_links")
    target = FK(Note, related_name="incoming_links")

class QuickCapture(TimeStampedModel):                # global inbox
    text = TextField()
    processed = BooleanField(default=False)
    project = FK(Project, null=True, blank=True)     # assigned during triage
```

### research (Phase 5)

```python
class Hypothesis(TimeStampedModel):
    project = FK(Project, related_name="hypotheses")
    statement = TextField()
    status = CharField(choices=PROPOSED/TESTING/SUPPORTED/CONTRADICTED/INCONCLUSIVE/ABANDONED)

class Evidence(TimeStampedModel):
    hypothesis = FK(Hypothesis, related_name="evidence")
    direction = CharField(choices=SUPPORTS/CONTRADICTS/MIXED)
    summary = TextField()
    reference = FK(Reference, null=True, blank=True)
    note = FK(Note, null=True, blank=True)
    document = FK(Document, null=True, blank=True)

class ExperimentEntry(TimeStampedModel):             # lab-notebook style
    project = FK(Project, related_name="experiment_entries")
    date = DateField(default=date.today)
    title = CharField(max_length=300)
    body = TextField(blank=True)                     # markdown: setup, what happened, outcome
    hypotheses = M2M(Hypothesis, blank=True)

class Dataset(TimeStampedModel):
    project = FK(Project, related_name="datasets")
    name = CharField(max_length=200)
    location = CharField(max_length=500)             # path or URL
    version = CharField(blank=True)
    checksum = CharField(blank=True)
    description = TextField(blank=True)
```

---

## 5. Build phases

**Hard rules:**
- Never start phase N+1 before the phase N **self-gate** (§8.7) passes, with evidence recorded in `PROGRESS.md`.
- A broken main branch outranks everything: if tests, lint, migrations, or `seed_demo` fail at any point, fixing that is the only allowed work.
- Within a phase, work in vertical slices: model → migration → admin → view → template → tests → commit.
- Anything not in the current phase goes into the Backlog section of `DECISIONS.md`, not into the code.

### Phase 0 — Scaffold

- Repository layout from §3; settings split (base/dev/prod) reading `.env` via django-environ.
- `docker-compose.yml` with Postgres 16; `DATABASE_URL` wiring.
- Login flow (Django auth, login required by default via middleware or mixin); single superuser created via `createsuperuser`.
- Base template: fixed left sidebar + content area + breadcrumb block; Tailwind standalone CLI building `static/css/app.css` with a documented `make css` / script command.
- pytest + ruff configured in `pyproject.toml`; one trivial passing test; `manage.py seed_demo` stub command.
- README quick start that gets a fresh machine running in under 5 minutes.

**Acceptance:** `docker compose up -d` → `migrate` → `runserver` → styled login page → empty dashboard shell. Tests and lint pass.

### Phase 1 — The core trio: Projects, Documents, Plans

- Project CRUD with status, accent color, archive; project list as the Projects index.
- **Project Overview page** (the heart of Atlas): current phase with progress, next 5 milestones with due dates, recent documents, counts, recent decisions. One glance = full situational awareness.
- Folder tree per project (create, rename, move, delete) with nested display; document upload into any folder; tags; filter documents by tag/folder; download.
- Plan page: ordered phases, milestones with due dates, optional tasks; HTMX check-off for milestones/tasks; progress bars roll up milestone → phase → project; overdue highlighted.
- Research questions list linked to phases. Decision log (list + create/edit).
- `seed_demo` creates one realistic demo research project exercising every feature.

**Acceptance:** Owner can create a project, build a 4-phase plan, upload documents into nested folders, check off milestones and watch progress propagate, and record a decision — all without touching the admin. Tests cover progress roll-up logic and folder nesting.

### Phase 2 — API v1 + Literature core

- DRF setup: auth via `X-API-Key` header checked against `ATLAS_API_KEY` env var; all Phase 1 resources exposed read/write under `/api/v1/`; document upload supported; pagination (50); drf-spectacular schema + docs page at `/api/docs/`.
- Reference library: add by DOI or arXiv ID → synchronous metadata fetch (Crossref, OpenAlex fallback; httpx with timeouts and clear error states); manual entry form; raw BibTeX paste-import; attach PDF.
- Link references to projects (`ProjectReference`) with reading status + priority; per-project literature page with filters; a **reading queue** view sorted by priority.
- Export per-project `.bib` with stable generated keys.
- **Bib checkers v1** (pure functions in `literature/services.py`, surfaced as a report page): duplicate detection (DOI exact + fuzzy title), missing required fields per entry type, DOI resolution check, retraction flag via Crossref.
- Quick-capture inbox: one text box, list, triage to a project or dismiss; API endpoint included.

**Acceptance:** `curl` with the API key can create a project and add a reference by DOI end-to-end. The bib report renders with at least the four checker categories. The reading queue works.

### Phase 3 — Knowledge graph, notes, search

- Add huey + Redis. Background task: fetch citation edges among a project's references from OpenAlex, with a visible "last synced / syncing" state.
- Graph API: `GET /api/v1/projects/{slug}/graph/` → `{"nodes": [{id, type, label, group, size}], "links": [{source, target, kind}]}`. Nodes are references and notes; links are citations, note-links, and note→reference citations.
- Graph page: 3D via 3d-force-graph with a 2D toggle; node size = citation count; color = reading status or type; click → side panel with details + link to the object.
- Notes: markdown editor + preview, `[[wiki-links]]` parsed into `NoteLink` on save, backlinks panel, link notes to references.
- Global full-text search (Postgres FTS) across references, notes, documents, decisions, plans — one search box in the sidebar.

**Acceptance:** A project with 20+ references shows a navigable 3D citation graph; creating `[[links]]` between notes updates the graph and backlinks; search returns mixed-type results.

### Phase 4 — Writing studio

- Manuscript CRUD with status pipeline (kanban-ish board or status column), venue, deadline countdown on the project overview.
- Per-manuscript bibliography: pick references from the library; export `manuscript.bib`.
- **Cite checker:** upload or paste a `.tex` file → parse `\cite{...}` keys → report cited-but-missing-from-bib and in-bib-but-uncited keys; run bib checkers v1 scoped to the manuscript.
- Submission timeline: `SubmissionEvent` log rendered as a vertical timeline per manuscript.

**Acceptance:** A manuscript can go idea → published with its events logged; the cite checker correctly flags a deliberately broken `.tex` fixture in tests.

### Phase 5 — Research thinking tools + dashboards

- Hypothesis ledger: hypotheses with linked evidence (supports/contradicts/mixed) drawn from references, notes, or documents; status auto-suggested from evidence balance but manually settable.
- Experiment log (dated entries, markdown) and dataset registry.
- Cross-project dashboard: active projects with phase + progress, upcoming milestones and deadlines across everything, GitHub-style activity heatmap (from `created_at`/`updated_at` across models), simple stats (papers read this month, notes written).

**Acceptance:** The dashboard answers "what should I work on today, everywhere?" in one screen.

### Phase 6 — Claude integration (MCP)

- `mcp_server/` as a small standalone package using the official `mcp` Python SDK (FastMCP). It is a **thin HTTP client over the DRF API** using `ATLAS_API_URL` + `ATLAS_API_KEY` env vars — no Django/ORM imports, so the API remains the single contract.
- Initial tool set: `list_projects`, `get_project_overview`, `get_plan`, `complete_milestone`, `list_documents`, `search`, `add_reference_by_doi`, `get_reading_queue`, `set_reading_status`, `add_note`, `quick_capture`, `run_bib_check`.
- README section documenting registration in Claude Code (`claude mcp add atlas -- ...`) and a smoke-test conversation script.

**Acceptance:** From Claude Code, the owner can list projects, check off a milestone, and add a reference by DOI, verified against the running app.

### Backlog (start only after the Phase 6 self-gate passes; then work top to bottom, one item at a time, same standards and self-gates)

In-browser PDF viewer with highlight-to-note, literature review matrix (papers × themes), embedding-based related-paper suggestions, GitHub commit ↔ experiment linking, Cmd+K command palette, auto-generated weekly review, protocol library with versioning, results/figure gallery, email/calendar deadline reminders.

---

## 6. API contract notes

- Base path `/api/v1/`; lowercase plural resource names; standard DRF error shapes; page size 50.
- Auth: `X-API-Key` header compared against env. Reject everything else. No session auth on the API.
- Special endpoints: `POST /api/v1/references/by-doi {"doi": "...", "project": "slug"}`; `GET /api/v1/projects/{slug}/graph/`; `POST /api/v1/quick-capture {"text": "..."}`.
- Everything must appear in the drf-spectacular schema with descriptions — the MCP server and future tooling depend on it.

---

## 7. UI guidelines

- **Layout:** fixed left sidebar (Dashboard, Projects, Library, Writing, Inbox, Search) plus a project-context subnav when inside a project (Overview, Plan, Documents, Literature, Notes, Writing, Research, Decisions). Breadcrumbs on every page.
- **Aesthetic:** calm and editorial. Near-white background, near-black text, generous whitespace, a clear type scale, and the project's accent color used sparingly (active nav, progress bars, links). System font stack. Minimal icons.
- **Every empty state** explains what the page is for and offers the primary action.
- Progress is shown as slim bars with a "3/7 milestones" label — never percentages alone.
- Prefer full pages over modals; prefer plain forms over JS; tables are fine and good.
- The product should feel like a well-organized lab notebook crossed with Django's admin — not like a SaaS marketing site.

---

## 8. Engineering standards & working agreement

1. **Vertical slices, frequent commits.** Conventional commits (`feat(plans): milestone check-off via htmx`). One slice per commit.
2. **Definition of done for any slice:** migrations created and applied, admin registered, tests written, `pytest -q` green, `ruff check .` and `ruff format --check .` clean.
3. **Tests:** every `services.py` function and computed property gets unit tests; every page gets at least a logged-in smoke test (200 + key content). Use factory-boy. Pragmatic coverage over 100%.
4. **Migrations** are always committed and never edited after being applied. No squashing without approval.
5. **`DECISIONS.md`** gets an entry (date, decision, why, alternatives considered) for every non-obvious choice. **`README.md`** run instructions are updated every phase. **`seed_demo`** always works and demonstrates the newest features.
6. **Autonomy protocol:** there is no human in the loop. When uncertain, choose the simplest reversible option that best serves §1's product values, log it in `DECISIONS.md` with the rejected alternatives, and continue. Questions that would block a supervised build get answered by you, in writing, the same way. Never silently expand scope; park ideas in the Backlog section of `DECISIONS.md`.
7. **Self-gate protocol (replaces human review).** A phase is complete only when you have verified, on a clean run, that: a fresh setup works end to end (`docker compose up -d` → `migrate` → `seed_demo` → `runserver`); `pytest -q`, `ruff check .`, and `ruff format --check .` all pass; and **every acceptance criterion for the phase is re-read and checked against concrete evidence** (a test name, a URL you exercised, a curl command and its output). Then append a gate report to `PROGRESS.md` — Phase · Built · Evidence per acceptance criterion · Decisions · Known gaps (moved to Backlog) — commit it, and proceed immediately to the next phase.
8. **State file: `PROGRESS.md`.** This is how the build survives interruptions. Its top is always a Current Status block: current phase, slice in progress, last completed slice, next 3 planned slices, anything broken. Update it at session end and after every gate. **Session start ritual:** read `CLAUDE.md` → read `PROGRESS.md` → `git log --oneline -15` → run tests → fix anything broken → resume the slice in progress.

---

## 9. Your first session — do this now

1. Verify the environment: `python --version` (3.12+), Docker available, port 5432 free.
2. Initialize the git repo, create the layout from §3, pin dependencies in `pyproject.toml`.
3. Create `PROGRESS.md` (Current Status block at top) and `DECISIONS.md` (with a Backlog section).
4. Execute Phase 0 completely, slice by slice, run the Phase 0 self-gate, and **continue straight into Phase 1**. From here on the loop is: resume → slice → verify → commit → update `PROGRESS.md` → repeat, phase after phase, through Phase 6 and then the Backlog. Do not stop to ask for review.

Build it the way Django itself is built: boring technology, strong conventions, obvious structure. Whenever you face a choice, pick the option that makes the answer to *"where is what?"* more obvious.
