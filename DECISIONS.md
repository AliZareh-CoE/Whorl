# DECISIONS

Running decision log for the Atlas build. Newest entries at the top of each section.

## Owner ideas (todo — outranks the auto backlog; only broken builds come first)

The owner adds ideas here (or tells the agent, who appends them). Work top-down; split big
ones into cycle-sized slices; mark done with date. Never delete — strike through and date.

1. **Performance: lightning fast & efficient.** Recurring concern, not one slice — every cycle
   should leave the app faster or no slower. ~~First slice (2026-06-10, cycle 4): N+1 audit —
   /library/ 49→6 queries, overview 17→13, plan 11→7; aggregate-based progress roll-up;
   heatmap day-aggregated in DB + 10-min cache; query-budget regression tests.~~ Remaining:
   ~~conditional GETs/ETags (2026-06-11, cycle 21): weak ETags on all API list/retrieve
   endpoints (count+max-updated aggregate — 304s skip serialization entirely, verified live
   0-byte revalidation), Cache-Control on document downloads.~~ Fragment caching only if
   pages ever feel slow.
2. **Security hardening.** Recurring concern alongside performance. ~~First slice
   (2026-06-10, cycle 5): cache-based login throttle (5 fails → 5-min lockout, 429, verified
   live), 50 MB upload cap + .pdf-only reference attachments enforced in forms AND API
   serializers, DRF rate throttles (3000/h keyed, 30/h anon), prod HSTS subdomains+preload +
   referrer-policy, X-Frame-Options DENY, login template now renders lockout errors.~~
   ~~API-key rotation helper (2026-06-11, cycle 22): `manage.py rotate_api_key` mints a
   token_urlsafe(32) key, rewrites .env preserving other lines, prints masked old key and
   restart/MCP reminders.~~ Remaining: CSP if ever public-facing.
3. **Free local text-to-speech ("read this to me").** A strong free TTS engine (e.g. Piper)
   the owner can run locally; "Read aloud" on notes, abstracts, and (eventually) PDFs.
4. **Auto-download article PDFs.** ~~Done (2026-06-10, cycle 7): arXiv direct + Unpaywall
   best-OA resolution in `literature/oa.py`; background huey fetch on every new reference
   (UI + API, `ATLAS_AUTO_FETCH_PDF` toggle), manual "Fetch open-access PDF" button on
   reference detail; %PDF magic + 50 MB cap; outcome stored on the reference; verified live
   (arXiv 1706.03762 → 2.1 MB PDF attached).~~
5. **NLP helpers.** Language tooling where it genuinely helps. ~~First slice (2026-06-10,
   cycle 8): RAKE-style local keyword extraction in `core/keywords.py` (no deps, no models);
   keyword chips on reference + note pages linking into search; "Suggested tags" on document
   edit with one-click create-and-attach.~~ Remaining: summarization, search-side NLP (#15).
6. **Prompt gallery.** ~~Done (2026-06-11, cycle 11): `prompts` app — searchable, taggable
   gallery with one-click copy; sidebar entry; `/api/v1/prompts/` CRUD+search; MCP tools
   `list_prompts` / `get_prompt`; two seeded examples.~~
7. **Bots / automations.** ~~First slice (2026-06-11, cycle 12): `bots` app — registry +
   per-bot state rows, daily 06:00 huey periodic tick over enabled bots, Automations page
   (enable/disable, last run/result, Run now); deadline-reminder bot (milestones ≤3 days or
   overdue, manuscripts ≤7 days → deduped inbox captures, verified live) and retraction-watch
   bot (Crossref sweep → inbox flags). Bots report to the inbox; failures recorded, never
   crash the scheduler.~~ ~~Citation-sync bot + run history (2026-06-11, cycle 23): third
   bot refreshes OpenAlex edges for all active projects (verified live); BotRun model keeps
   the last 20 runs per bot with ✓/✕ shown in a Run history panel.~~ Remaining: inbox-triage
   suggester, MCP-side bots.
8. **Open-source readiness.** Goal: a public GitHub repo worth thousands of stars. Keep a
   living brainstorm in `OPENSOURCE.md` (positioning, killer demo GIFs, one-command install,
   docs site, LICENSE/CONTRIBUTING, comparison table vs Zotero/Notion/Overleaf, launch plan
   for HN/r/selfhosted). Loop may add thoughts there any cycle; polish items become slices.
9. **LaTeX editor ("better than Overleaf", owner knows it's ambitious).** ~~Slice 1
   (2026-06-11, cycle 13): `latex_source` on Manuscript; CodeMirror 5 (stex mode) editor page
   with cite-key autocomplete from the manuscript bibliography, Ctrl/Cmd-S save, integrated
   cite-check on every save.~~ Remaining: server-side compile (Tectonic — dependency decision
   first)~~ ~~Slice 2 (2026-06-11, cycle 24): Tectonic compile — `make tectonic` vendoring,
   background compile task, Compile PDF button (saves source first), status line, failure log
   panel in the editor, View PDF link; real end-to-end compile in the test suite.~~
   Remaining: PDF preview pane beside the editor, snippets, section outline.
10. **Commenting / annotations.** ~~First slice (2026-06-11, cycle 14): generic `Comment`
    model (contenttypes) with markdown bodies; comment threads live on note, reference, and
    manuscript pages via one `_comments.html` include; kind allowlist guards the endpoint.~~
    Remaining: comments on documents and folders; PDF-anchored comments (page/selection)
    building on the reader; LaTeX line-anchored comments in the editor.
11. **Better papers & literature reviews.** Continuous improvement; NO paid LLM APIs —
    local NLP or the owner's Claude subscription via MCP only. ~~First slice (2026-06-11,
    cycle 15): reading queue shows per-paper theme coverage badges (n/N themes); review
    matrix exports as a markdown table; `GET /api/v1/projects/{slug}/review-matrix/` +
    MCP tool `get_review_matrix` so Claude can discuss coverage gaps in chat.~~
    Remaining: coverage-gap suggestions in the queue ordering, synthesis-note scaffolds.
12. **Virtual pet 🐾.** ~~Done (2026-06-11, cycle 16): Mochi the research owl — sidebar
    widget + /pet/ page; mood from 7-day activity (sleeping/content/happy/thriving), lifetime
    stages (egg→hatchling→scholar→sage) derived live from milestones/papers/notes/experiments/
    comments; renameable; 5-min cached so pages stay fast (query-budget guards verified it);
    explicitly no nagging — it sleeps when you rest.~~ Possible later: tiny seasonal accessories.
13. **Project-as-growing-tree UI.** ~~First slice (2026-06-11, cycle 17): server-rendered
    SVG tree (`{% project_tree %}` tag) with five stages (sprout→sapling→young→mature→bloom
    with blossoms at 100%), deterministic per project, accent-colored foliage; lives on the
    project overview and as minis on the projects index.~~ Polish later: richer branch
    artwork at middle stages, gentle CSS sway on bloom.
14. **World-class file & folder handling.** ~~First slice (2026-06-11, cycle 18):
    drag-and-drop anywhere on the documents page (overlay + per-file size validation +
    titles from filenames) and multi-file Quick upload button; inline rename (HTMX) and
    quick-move folder dropdown on every row, project-scoped.~~ Remaining: breadcrumbed
    folder navigation, cheap previews (text/image), drag rows between folders.
15. **Lightning-fast search with NLP.** ~~First slice (2026-06-11, cycle 19): pg_trgm
    extension + trigram typo-tolerance fallback; websearch query parsing ("quoted phrases",
    OR, -negation); as-you-type suggestion dropdown on the sidebar box (HTMX, 250 ms
    debounce, top 8 mixed results). Bonus correctness fix the tests forced: FTS now filters
    on the boolean match instead of a rank threshold — ts_rank ignores ! and & so negated
    terms previously leaked.~~ Remaining: synonym dictionaries, per-type ranking boosts,
    keyboard navigation in the dropdown.

## Loop rules (amendments to CLAUDE.md §5, owner-directed)

- **The backlog must never be empty.** Every loop cycle MUST append at least one new,
  concrete, valuable idea to the Backlog below before it ends — the loop runs forever.
- **Priority order each cycle:** (a) anything broken → (b) Owner ideas top-down →
  (c) auto Backlog top-down. New owner messages with ideas are appended to Owner ideas
  immediately.
- **Efficiency and security are standing constraints** on every slice, not just items 1–2.
- **Every 10th cycle is an audit cycle:** full security review + responsiveness/performance
  check of the whole system and everything added since the last audit (re-run the query
  audit, check page weights, throttle behavior, upload paths, dependency CVEs). Track cycle
  numbers in PROGRESS.md.
- **At least 2 of every 10 cycles are UI/UX improvement cycles** to world-class standards —
  polish, consistency, accessibility, interaction quality; not new features.
- **No paid LLM API calls, ever** — language-smart features go local-NLP or through the
  owner's Claude subscription via MCP.

## Decisions

### 2026-06-11 — Tectonic vendored as the LaTeX engine (owner-sanctioned)
- **Decision:** LaTeX compilation uses the Tectonic 0.15 standalone binary, downloaded into
  `bin/` via `make tectonic` (same pattern as Tailwind and the Piper voice). Compiles run in a
  temp dir through a huey task with a 180 s timeout; PDF, status, log, and timestamp stored on
  the Manuscript. No new Python dependency.
- **Why:** Owner idea #9 needs real PDF output; Tectonic is the only modern self-contained
  LaTeX engine (auto-fetches packages, caches in ~/.cache/Tectonic, single binary).
- **Alternatives rejected:** TeX Live (gigabytes, apt-managed, breaks the 5-minute quick
  start); LaTeX-to-HTML approximations (not real output researchers can submit).

### 2026-06-10 — Piper TTS for "Read aloud" (owner-sanctioned dependency)
- **Decision:** Add `piper-tts` (free, local, no cloud) for Owner idea #3. Voice model
  (en_US-amy-medium, ~60 MB) is downloaded once via `manage.py download_tts_voice` into
  `tts_voices/` (gitignored). Server endpoint `POST /tts/` synthesizes WAV; "Read aloud"
  buttons on notes and reference abstracts stream it to an `<audio>` element.
- **Why:** The owner explicitly asked for a strong free TTS engine they can run locally;
  Piper is the best-in-class open option and runs fine on CPU.
- **Alternatives rejected:** browser SpeechSynthesis (quality is OS-roulette, often robotic);
  cloud TTS APIs (not free, not local, violates the no-paid-API rule).

### 2026-06-10 — Related-paper suggestions use TF-IDF cosine, not neural embeddings
- **Decision:** Backlog #3 ships as `literature/related.py`: TF-IDF vectors over title+abstract (venue excluded — same-journal is noise, a test caught it dominating small libraries) with cosine similarity, computed in-process (single-user library sizes make O(N) per page fine). Surfaced on the reference detail page and as `GET /api/v1/references/{id}/related/`.
- **Why:** "Embedding-based" via sentence-transformers means a multi-GB torch dependency outside the locked stack; an external embedding API adds a paid network dependency. Sparse TF-IDF vectors are embeddings enough to serve the product value (surface related papers), with zero dependencies and trivially reversible.
- **Alternatives rejected:** sentence-transformers (dependency weight, violates §2); OpenAlex `related_works` (only covers OpenAlex-matched refs and needs network per view — parked in Backlog as a future "discover similar on OpenAlex" enhancement).

### 2026-06-10 — PDF viewer via pdf.js CDN; highlights append to one note per reference/project
- **Decision:** Backlog #1 uses pdf.js (pdfjs-dist via CDN, like 3d-force-graph) rendering canvas + text layer at `/library/{pk}/read/`. Selecting text offers "Save highlight", which appends a blockquote (with page number) to a single auto-created note titled "Highlights — {bibtex_key}" in a chosen linked project, and links the note to the reference.
- **Why:** CDN JS is the established pattern for rich views in the locked stack (no Node build); one append-only highlights note per reference/project keeps "a place for everything" — highlights are findable via search, backlinks, and the graph immediately.
- **Alternatives rejected:** a dedicated Highlight model (more machinery than the workflow needs; a note already integrates with search/graph/evidence); browser-native iframe PDF rendering (no text-selection hook for highlight-to-note).

### 2026-06-10 — `mcp` SDK added as a dependency (Phase 6, spec-sanctioned)
- **Decision:** Add the official `mcp` Python SDK to `pyproject.toml` for `mcp_server/`. The server is stdio-only FastMCP; `mcp_server/client.py` stays a pure httpx client with zero Django and zero SDK imports (enforced by `test_no_django_imports`).
- **Why:** CLAUDE.md §5 Phase 6 names this SDK explicitly; the API remains the single contract.
- **Alternatives rejected:** hand-rolling the MCP protocol (pointless duplication of the official SDK).

### 2026-06-10 — arXiv metadata comes from arXiv's export API, not OpenAlex
- **Decision:** `fetch_metadata_by_arxiv` queries `export.arxiv.org/api/query` (Atom, parsed with stdlib ElementTree). DOI lookups remain Crossref → OpenAlex.
- **Why:** Verified live that OpenAlex returns 404 for arXiv DataCite DOIs (`doi:10.48550/arxiv.1706.03762`) and Crossref does not index them at all. arXiv's own public API is authoritative, free, and adds no dependency beyond httpx already in the stack.
- **Alternatives rejected:** OpenAlex DataCite-DOI lookup (verified broken); adding the `arxiv` PyPI package (unnecessary dependency for one Atom feed).

### 2026-06-10 — Folder deletion keeps documents, drops subfolders
- **Decision:** `Document.folder` uses `on_delete=SET_NULL` (document falls back to project root); `Folder.parent` cascades (subfolders are deleted with their parent). Folder moves exclude self and descendants to prevent cycles.
- **Why:** Files are the irreplaceable objects — a folder is just organization. Losing uploads because a folder was deleted would violate "a place for everything".
- **Alternatives rejected:** cascade documents (data loss); forbid deleting non-empty folders (friction, and the empty-state nudges re-filing anyway).

### 2026-06-10 — Milestone toggle returns phase card + OOB progress bar
- **Decision:** HTMX check-off endpoints return the full phase-card partial and an out-of-band `#project-progress` swap, both rendered from the same partials as the full page.
- **Why:** Progress must roll up visually without a page reload, and partials shared with the full page keep one source of truth for markup.
- **Alternatives rejected:** returning the whole plan page (wasteful); client-side recalculation in Alpine (duplicates server logic).

### 2026-06-10 — Python 3.12 via uv-managed virtualenv
- **Decision:** Use Python 3.12 (`/usr/bin/python3.12`) with a `.venv` managed by `uv`; dependencies declared in `pyproject.toml`, locked in `uv.lock`.
- **Why:** CLAUDE.md locks Python 3.12+; the system default is 3.11. `uv` is present, fast, and gives reproducible installs without adding anything to the runtime stack.
- **Alternatives rejected:** plain `pip` + `requirements.txt` (no lockfile, slower); Python 3.13 (newer than needed; 3.12 is the conservative floor the spec names).

## Backlog

(populated by phase gates; work top to bottom only after the Phase 6 gate passes)

1. In-browser PDF viewer with highlight-to-note
2. Literature review matrix (papers × themes)
3. Embedding-based related-paper suggestions
4. GitHub commit ↔ experiment linking
5. Cmd+K command palette
6. Auto-generated weekly review
7. Protocol library with versioning
8. Results/figure gallery
9. Email/calendar deadline reminders
10. OpenAlex "discover similar" — surface related_works for a reference with one-click add-by-DOI (idea added by cycle 3, from the related-papers work)
11. Conditional GETs — ETag/Last-Modified on API list endpoints and far-future cache headers on media/static, so MCP polling and the PDF reader get cheap revalidation (idea added by cycle 4, from the performance pass)
12. “Read aloud” for whole PDFs — stream the PDF text-layer through Piper chapter by chapter with a mini player (idea added by cycle 6, from the TTS work)
13. Worker-deploy note — document (README/Makefile) that `run_huey` must restart after code changes; consider a `make worker` target and a stale-worker warning on the Automations page when bots land (idea added by cycle 7, after hitting a stale TaskRegistry live)
14. Keyword chips → reading-queue filters and a project-level keyword cloud (idea added by cycle 8, from the NLP work)
15. Responsive layout — collapsible sidebar + mobile-friendly tables (next UI/UX cycle candidate; idea added by cycle 9)
16. `make doctor` — one command that checks services, migrations, voice model, worker freshness, and runs the query audit; useful for self-hosters (idea added by cycle 10, from the audit)
17. Prompt variables — `{{placeholders}}` in saved prompts with a small fill-in form before copying (idea added by cycle 11)
18. Bot run history — keep the last N results per bot and chart reminders-over-time on the Automations page (idea added by cycle 12)
19. LaTeX compile service — vendor the Tectonic binary (like Tailwind/Piper pattern) behind a huey task with compile logs surfaced in the editor (idea added by cycle 13)
20. Comment mentions of objects — [[wiki-links]] and @cite-keys resolving inside comment bodies (idea added by cycle 14)
21. Queue ordering option "least-covered themes first" — triage papers that fill matrix gaps (idea added by cycle 15)
22. Pet reactions to events — a brief happy hop via HTMX when a milestone is checked off on the plan page (idea added by cycle 16)
23. Tree grove view — all projects as one grove on the dashboard, trees sized by scope (idea added by cycle 17)
24. Upload progress bars per file for large uploads (idea added by cycle 18)
25. Search suggestion keyboard navigation (↑/↓/Enter) + recent-searches memory (idea added by cycle 19)
26. GIN trigram indexes on searched title fields once data grows (idea added by cycle 20 audit)
27. Last-Modified on media files + ETag support in the MCP client cache (idea added by cycle 21)
28. Loop-resilience note — chain notifications can drop and watchdog monitors expire at 30 min; watchdog is now re-armed every cycle (lesson from the cycle-21→22 stall)
29. Dev-process note — runserver/worker restarts must use pkill -f "[m]anage.py ..." (bracket trick) or they kill their own shell; documented after the cycle-23 debugging (idea added by cycle 23)
30. Editor split view — compiled PDF preview pane beside the source with sync scroll (idea added by cycle 24)
31. Audit log page — surface recent logins (incl. throttled attempts) and API activity on a simple "Activity & access" page, building on the new throttle counters (idea added by cycle 5, from the security pass)
