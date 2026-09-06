# Atlas 🗺️ — the self-hosted research workbench

![CI](https://github.com/AliZareh-CoE/project-manager/actions/workflows/ci.yml/badge.svg)
![Desktop release](https://github.com/AliZareh-CoE/project-manager/actions/workflows/desktop-release.yml/badge.svg)

**Plans, papers, notes and manuscripts in one calm place — with Claude built in.**

Atlas is a single-user, self-hosted research platform for people who find Jira-style tools noisy
and task-obsessed. It treats what researchers actually care about as first-class: a **plan** you
write like a document, a **library** that reads your PDFs, **notes** that cite papers with `@key`,
a **writing studio** that checks your citations and compiles LaTeX, and an **MCP server** so
Claude Code can do all of it with you — 86 tools over the same API the UI uses.

> Built like Django itself: boring technology, strong conventions, everything has exactly one
> obvious place. No cloud, no telemetry. Runs as a web app or a one-click desktop app.

**Download:** [Atlas desktop preview](https://github.com/AliZareh-CoE/project-manager/releases/tag/desktop-preview)
(Windows `.exe`/`.msi`, Linux `.deb`/`.rpm`) · login `atlas` / `atlas` after `seed_demo`, or create your own user.

## Screens

| | |
|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Project overview](docs/screenshots/overview.png) |
| *Dashboard: what needs you, this week everywhere, projects with phase health, activity* | *Project overview: current phase with health, this week, what changed, open questions, manuscripts* |
| ![Plan as an outline](docs/screenshots/plan-outline.png) | ![Roadmap](docs/screenshots/plan-roadmap.png) |
| *Write the plan as a Markdown outline — the preview says what a save creates, renames, deletes* | *Roadmap: drag phases and milestones on a time axis; each phase rated behind / on track / ahead* |
| ![Library workbench](docs/screenshots/library.png) | ![Read and highlight in place](docs/screenshots/library-reader.png) |
| *Library: drop PDFs / BibTeX / RIS or pull Zotero, facet, bulk-file, recover metadata* | *Read in place: highlights save as structured rows and paint back onto the page* |
| ![Search inside your PDFs](docs/screenshots/library-find.png) | ![Discover from any paper](docs/screenshots/library-discover.png) |
| *Search inside every attached PDF — the hit names the page, the reader jumps to it* | *Discover: similar / cites / cited-by on OpenAlex, one-click add into a project* |
| ![Notes workbench](docs/screenshots/notes.png) | ![Knowledge graph](docs/screenshots/graph3d.png) |
| *Notes: `[[links]]` and `@citations` autocomplete, live preview, link panel* | *Knowledge graph: search-to-focus, neighbourhood mode, hubs; works offline* |
| ![Manuscript studio](docs/screenshots/writing-studio.png) | ![Reviewer response tracker](docs/screenshots/writing-reviews.png) |
| *Manuscript studio: pipeline, bibliography from your literature, cite check, compile, budget* | *Paste the reviews — get a point-by-point response note and a progress bar* |
| ![Inbox triage](docs/screenshots/inbox.png) | ![Review matrix](docs/screenshots/matrix.png) |
| *Inbox: a DOI becomes a paper, "todo:" a Today item, "decision:" a decision — one click* | *Review matrix: papers × themes, the finding typed into each cell, coverage per theme* |

## What's inside

**Plan** — phases → milestones → optional tasks, progress rolling up visually.
- Write the whole plan as a Markdown outline (`# phase [status] (start → end)`, `- [ ] milestone (due …)`, indented tasks) with a live dry-run of what a save creates, renames and deletes; Claude edits the same outline.
- Roadmap: phases as bars (windows inferred when undated), milestones as diamonds, drag or use the keyboard to reschedule; per-phase health (behind / on track / ahead / overdue) and a finish forecast from your pace.
- "This week" strip, milestone drawer (notes, due date, tasks), phase objectives and research questions in place.

**Library** — add by DOI / arXiv; drop a folder of PDFs (the DOI is read off page one), BibTeX, RIS, CSL-JSON, or pull Zotero; everything deduplicated.
- Facets, keyboard `j/k/x/o`, bulk file / mark / tag / export, saved smart views, duplicate merge that keeps every link.
- Read and highlight without leaving the page; per-project reading notes; Find PDF (arXiv → Unpaywall).
- Search inside your PDFs: every attached PDF is read into searchable text — hits name the page.
- Discover from any paper (similar / cites / cited-by), citations in APA · MLA · Chicago · Harvard · Vancouver · IEEE, retraction and duplicate checkers.
- Review matrix: an extraction table of papers × themes — click a cell, type the finding, add themes in place, copy as Markdown, draft a synthesis note; Claude fills cells from the PDFs through MCP.

**Notes & graph** — `[[wiki-links]]` and Pandoc-style `@key` citations with autocomplete, live preview, autosave, backlinks and unlinked mentions.
- Templates: a literature note built from any paper with its highlights, a daily note seeded with this week's focus, meeting, experiment. Export any note with a formatted bibliography.
- 3D/2D knowledge graph (vendored, works offline): search-to-focus, kind and link filters, neighbourhood focus, hubs.

**Writing** — one studio page per manuscript: status pipeline, deadline countdown, abstract, compile card with approximate word count, bibliography built from the project's literature, cite check with one-click fixes, submission timeline.
- Reviewer-response tracker: paste the reviews, get a point-by-point response note and "7/12 answered".
- Venue budget: words, abstract, figures, tables, references, pages — live bars against the venue's limits.
- A full-window LaTeX studio: files, outline, bibliography and history panels, CodeMirror with `\cite{}` completion from your library and a live cite-check, PDF preview, problems panel, autosave, Vim keymap, ⌘P quick open. Compiles with Tectonic (bundled in the desktop app), keeps revisions, exports an arXiv-ready `.zip`.

**Overview, dashboard, inbox, today**
- Project overview: current phase with health, this week, a digest of what changed, open questions, manuscripts at a glance.
- Dashboard: needs-attention lead, "this week, everywhere" (completable in place), phase health per project, monthly stats, 26-week heatmap.
- Inbox: capture from anywhere (⌘K, the page, Claude); smart triage turns a DOI into a paper, "todo:" into a Today item, "idea:" into a note, "milestone:" and "decision:" into the real thing.
- Today: a dead-simple personal list for the day. Research tools: a hypothesis ledger (evidence from papers, notes or documents; the balance suggests a status), experiment log, datasets, decision log, protocols. Automations: deadline reminders, retraction watch, citation sync. Local extras: Piper read-aloud, extractive tl;dr — offline.

**Claude / MCP** — 86 tools over the REST API plus four skills; your AI assistant operates the same contract you do. **Mochi** 🦉 — a living companion (it watches your cursor, hops when you finish things, grows from egg to sage) fed only by finished research; it never nags.

## Quick start (one command)

With just Docker installed:

```bash
git clone <repo-url> atlas && cd atlas
cp .env.example .env                       # set SECRET_KEY, ATLAS_API_KEY, DEBUG=false
docker compose --profile app up -d --build
docker compose exec web .venv/bin/python manage.py createsuperuser
```

Atlas is on http://127.0.0.1:8000 — the React app is the front door (the classic
server-rendered UI remains at /classic/ and trailing-slash URLs); web app, background
worker, Postgres, and Redis all running.

## Quick start (development)

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker with Compose, `make`, `curl`.

```bash
git clone <repo-url> atlas && cd atlas

cp .env.example .env          # edit SECRET_KEY / ATLAS_API_KEY if you like
uv venv --python 3.12 && uv sync

docker compose up -d          # Postgres 16 (5432) + Redis 7 (6379)
make css                      # downloads the Tailwind standalone CLI on first run
make tectonic                 # LaTeX engine for the studio's Recompile (desktop builds bundle it)

.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser   # you are the single user
.venv/bin/python manage.py seed_demo         # optional demo data
.venv/bin/python manage.py download_tts_voice  # optional: ~60 MB local voice for Read aloud
.venv/bin/python manage.py runserver
.venv/bin/python manage.py run_huey   # background worker (citation sync, bots), separate terminal
```

Open http://127.0.0.1:8000/ and log in. The Django admin lives at `/admin/`.

**React islands (optional, for island development only).** `make js` rebuilds the islands
in `frontend/` (Vite + TypeScript, Node 20+ required). Built artifacts are committed under
`static/js/islands/`, so running Atlas never needs Node.

## API

Everything in the UI is also available under `/api/v1/` (interactive docs at `/api/docs/`).
Authenticate with the `X-API-Key` header, checked against `ATLAS_API_KEY` in your `.env`:

```bash
curl -H "X-API-Key: $ATLAS_API_KEY" http://127.0.0.1:8000/api/v1/projects/

# rotate the key any time (updates .env; restart the server afterwards)
.venv/bin/python manage.py rotate_api_key

# add a reference by DOI and link it to a project
curl -H "X-API-Key: $ATLAS_API_KEY" -H "Content-Type: application/json" \
     -d '{"doi": "10.1038/nature12373", "project": "my-project"}' \
     http://127.0.0.1:8000/api/v1/references/by-doi/
```

## Claude integration (MCP)

`mcp_server/` exposes Atlas as MCP tools — a thin HTTP client over the API (no Django imports),
so anything Claude can do, you can also do with curl.

**The easy way:** open **Connect Claude Code** in the sidebar (`/connect`). It shows
the exact `claude mcp add` line for *your* install, with a Copy button — paste it in a terminal
once and you're done. Then `claude mcp list` shows `atlas` as connected.

**Skills.** The same page installs four Atlas playbooks into `~/.claude/skills/` so Claude Code
knows the workflows, not just the tools: `/atlas-daily` (dashboard → today's three things →
inbox triage), `/atlas-literature` (DOI in, reading queue, highlights, review matrix, synthesis
note), `/atlas-writing` (files, bibliography, cite check, compile, reviews → response note,
submission events) and `/atlas-plan` (outline round-trips with `dry_run`, roadmap health,
decisions). They live in `mcp_server/skills/` and a test pins every tool they mention to a real
MCP tool.

- **Desktop app:** the installer ships the MCP server as `atlas-mcp`, and the app mints its own
  API key on first launch. `atlas-mcp` finds the running app's URL and key by itself (from the
  data folder's `server.json` + `api_key`), so the line carries no secrets:
  `claude mcp add atlas -- "<install dir>/atlas-mcp/atlas-mcp"` (`.exe` on Windows).
- **Dev / server install:** the line passes the URL and key explicitly:

```bash
claude mcp add atlas \
  --env ATLAS_API_URL=http://127.0.0.1:8000 \
  --env ATLAS_API_KEY=<your key from .env> \
  -- /path/to/atlas/.venv/bin/python -m mcp_server.server
```

Tools — projects & plans: `get_dashboard`, `list_projects`, `get_project_overview`, `get_plan`,
`complete_milestone`, `get_timeline`, `create_project`, `list_project_templates`, `get_plan_outline`, `set_plan_outline`, `get_roadmap`, `set_phase_dates`, `get_week_focus`.
Documents & files: `list_documents`, `list_project_files`, `read_project_file`,
`write_project_file`. Literature: `add_reference_by_doi`, `get_reading_queue`,
`set_reading_status`, `run_bib_check`, `get_review_matrix`, `set_review_mark`, `add_review_theme`, `get_synthesis_scaffold`.
Library imports & discovery: `import_references` (BibTeX/CSL-JSON/RIS text), `import_from_zotero`,
`discover_related` (similar / cites / cited-by on OpenAlex), `export_bibtex`, `format_citations` (APA/MLA/Chicago/Harvard/Vancouver/IEEE).
Tags, views & hygiene: `list_library_tags`, `tag_references`, `find_duplicates`, `merge_references`.
Reading: `list_highlights`, `add_highlight`, `get_highlights_markdown`, `get_reading_notes`, `set_reading_notes`, `fetch_pdf`, `search_pdf_text`, `search_in_pdf`.
Today list: `list_todos`, `add_todo`, `complete_todo`.
Notes, search & review: `add_note`, `list_notes`, `get_note`, `update_note`, `get_note_links`, `create_note_from_template`, `export_note`, `quick_capture`, `list_inbox`, `convert_capture`, `search`, `get_weekly_review`,
`list_prompts`, `get_prompt`. Manuscripts (LaTeX): `list_manuscripts`, `get_manuscript`,
`list_manuscript_files`, `read_manuscript_file`, `write_manuscript_file`, `set_main_file`,
`compile_manuscript`, `get_compile_status`, `get_compile_diagnostics`, `compile_and_wait`,
`latex_word_count`. Protocols: `list_protocols`, `add_protocol`, `new_protocol_version`. Research: `add_hypothesis`, `set_hypothesis_status`, `add_evidence`, `log_experiment`. Bibliography & submissions: `get_manuscript_bibliography`, `add_manuscript_reference`, `remove_manuscript_reference`, `manuscript_cite_check`, `add_submission_event`, `log_reviews`, `get_response_progress`, `get_manuscript_budget`, `set_venue_limits`.

Smoke-test conversation script (after `seed_demo`):

1. *"List my projects"* → expect Attention and Working Memory.
2. *"What should I work on in attention-and-memory?"* → overview with current phase + overdue pilot milestone.
3. *"Check off the 'Pilot data collected' milestone"* → get_plan for the id, then complete_milestone; progress moves 3/9 → 4/9.
4. *"Add 10.1038/nature12373 to that project"* → add_reference_by_doi; appears in the reading queue.
5. *"Capture: email co-author about revisions"* → quick_capture; visible in the Inbox.

## File workspace, desktop app & terminal

Every project has a **Files** page (in the SPA subnav): one unified tree holding your
documents *and* your manuscript/LaTeX sources together, kept live. Click any file to open
it in-app — text/code/Markdown in a viewer, PDFs via the (locally vendored) pdf.js, CSVs
as a table, images inline. You can edit text in place, create folders, rename, delete,
drag-drop to upload, move files between folders, and jump to any file with **Ctrl/Cmd-P**.
It is machine-friendly too: `list_project_files`, `read_project_file`, `write_project_file`,
`create_project`, and `list_project_templates` are MCP tools.

**Project templates** scaffold an organized layout on creation — pick *Empirical study*,
*Theory / review paper*, *Software / dataset project*, or *Minimal* (literature/, data/,
analysis/, manuscript/, notes/ ...), or **save any project's structure as your own template**.

### Desktop app (Tauri)

Atlas also ships as a **self-contained desktop app**: one installer for Linux (`.deb`/`.rpm`)
or Windows (`.exe`/`.msi`) that bundles the Django server frozen with PyInstaller, running on a
per-user SQLite file — no Python, Postgres, Redis, or Docker on the machine. Installers are
built by the **Desktop release** GitHub Actions workflow and attached to the "Atlas desktop
preview" release (or a `v*` tag). On top of the web app the desktop build adds a **terminal
dock** — press ⌃` on any page for a real shell (tabs, resize, maximize), with a **Claude**
button that opens Claude Code already connected to Atlas — and **Open from disk** (a native
file picker). The web app stays the single source of truth.

To hack on the shell against a running dev server:

```bash
cd desktop
cargo install tauri-cli --version "^2"   # one-time
make desktop          # dev run (Atlas must be running on :8000)
make desktop-build    # packaged binary -> desktop/target/release/bundle/
```

See `desktop/README.md` for how the bundled build works, per-OS prerequisites, and the
one-time signing setup that activates the in-app updater. The terminal and disk access are
desktop-only and are never exposed through the web API or MCP.

## How Atlas compares

| | Atlas | Zotero | Notion | Overleaf |
|---|---|---|---|---|
| Research project plans | ✅ phases/milestones | — | manual | — |
| Reference manager + DOI import | ✅ | ✅ | — | — |
| Knowledge graph of citations & notes | ✅ 3D, offline | — | — | — |
| Notes that cite papers (`@key`) | ✅ | partial | — | — |
| Reviewer-response tracker, venue budget | ✅ | — | — | — |
| LaTeX editing + compile | ✅ Tectonic | — | — | ✅ |
| Cite checker against your bib | ✅ | — | — | partial |
| Self-hosted, your data | ✅ | ✅ | — | — |
| AI collaborator via MCP | ✅ | — | — | — |

## Development

```bash
make test     # pytest -q (900+ tests)
make lint     # ruff check + ruff format --check
make doctor   # health check: db, migrations, redis, worker freshness, optional components
make worker   # (re)start the background worker — it does NOT hot-reload after code changes
make css-watch
```

Something behaving oddly after an update? `make doctor` diagnoses the usual suspects,
including a worker still running stale code.

See **CONTRIBUTING.md** for conventions. Architecture and decision history live in
`CLAUDE.md`, `DECISIONS.md`, `PROGRESS.md`, and `AUDITS.md` — the project's entire build,
including its security audits, is documented in-repo.

## License

[AGPL-3.0](LICENSE) — free to self-host, modify, and share; improvements stay open.
