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
   edit with one-click create-and-attach.~~ ~~Summarization (2026-06-11, cycle 26):
   frequency-scored extractive summarizer in `core/summarize.py` (no models/APIs, opening-
   sentence bonus, original order preserved); ≡ tl;dr buttons on notes and abstracts via a
   shared HTMX include.~~ Remaining: search-side NLP done in #15; future: tl;dr for PDFs.
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
8. **Open-source readiness.** Goal: thousands of stars; brainstorm lives in `OPENSOURCE.md`.
   ~~First slice (2026-06-11, cycle 28): AGPL-3.0 LICENSE (decision logged), hero README
   (positioning line, screenshot grid from docs/screenshots/, feature list, comparison table
   vs Zotero/Notion/Overleaf, MCP front and center), CONTRIBUTING.md.~~ Remaining: app
   ~~containerization (2026-06-11, cycle 29): Dockerfile + compose app profile (web+worker),
   verified by building the image and serving /login/ from the container in-sandbox.~~
   Remaining: demo GIF, docs site, issue templates, launch posts.
9. **LaTeX editor ("better than Overleaf", owner knows it's ambitious).** ~~Slice 1
   (2026-06-11, cycle 13): `latex_source` on Manuscript; CodeMirror 5 (stex mode) editor page
   with cite-key autocomplete from the manuscript bibliography, Ctrl/Cmd-S save, integrated
   cite-check on every save.~~ Remaining: server-side compile (Tectonic — dependency decision
   first)~~ ~~Slice 2 (2026-06-11, cycle 24): Tectonic compile — `make tectonic` vendoring,
   background compile task, Compile PDF button (saves source first), status line, failure log
   panel in the editor, View PDF link; real end-to-end compile in the test suite.~~
   ~~Split-view preview (2026-06-11, cycle 27 UI/UX): toggleable PDF pane beside the
   source (preference remembered), compile-status polling endpoint, pane auto-opens on
   Compile, ✓/⏳/✕ status with failure log inline; verified with a real Tectonic compile.~~
   Remaining: snippets, section outline.
10. **Commenting / annotations.** ~~First slice (2026-06-11, cycle 14): generic `Comment`
    model (contenttypes) with markdown bodies; comment threads live on note, reference, and
    manuscript pages via one `_comments.html` include; kind allowlist guards the endpoint.~~
    ~~PDF-anchored comments (2026-06-11, cycle 25): `page` anchor on Comment; reader gains
    a sticky "Page comments" panel — IntersectionObserver tracks the page in view, comments
    pin to it, clicking one scrolls back to its page; page badges on detail threads; the
    `next` redirect is validated local-only (open-redirect guard + tests).~~
    Remaining: comments on documents/folders; selection-anchored PDF comments; LaTeX
    line-anchored comments in the editor.
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

### 2026-06-11 — Containerized deployment: gunicorn + whitenoise, ATLAS_BEHIND_TLS flag
- **Decision:** One-command install via `docker compose --profile app up -d --build`:
  single image (uv-built, Tailwind compiled and collectstatic'd at build time) running as
  `web` (migrate + gunicorn) and `worker` (run_huey); whitenoise serves static with the
  manifest storage in prod; `.dockerignore` keeps host artifacts out (host `.venv` clobbering
  the image's was a real bug caught during the live build). `ATLAS_BEHIND_TLS=false` relaxes
  SSL-redirect/HSTS/secure-cookies for localhost/LAN compose use; defaults stay strict.
- **Why:** Open-source adoption (Owner idea #8) lives or dies on install friction; gunicorn +
  whitenoise is the boring standard for single-box Django.
- **Alternatives rejected:** runserver in the container (not production-grade); nginx sidecar
  (a second container and config surface for marginal gain at this scale).

### 2026-06-11 — AGPL-3.0 license (open-source readiness, Owner idea #8)
- **Decision:** Atlas is licensed AGPL-3.0.
- **Why:** Free for every researcher to self-host and modify, while the network-use clause
  prevents closed SaaS clones from taking the work proprietary — the failure mode that most
  worries single-maintainer self-hosted projects.
- **Alternatives rejected:** MIT (invites closed forks of a hosted product), BSL/fair-source
  (not OSI-open, hurts adoption and the thousands-of-stars goal).

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
10. ~~OpenAlex "discover similar" (done 2026-06-11, cycle 31): `literature/discover.py` resolves the work, batch-fetches related_works, filters out DOIs already in the library; ⌕ Discover panel on reference detail with one-click + Add (reuses by-DOI import incl. background PDF fetch); verified live on a real paper.~~
11. Conditional GETs — ETag/Last-Modified on API list endpoints and far-future cache headers on media/static, so MCP polling and the PDF reader get cheap revalidation (idea added by cycle 4, from the performance pass)
12. ~~“Read aloud” for whole PDFs (done 2026-06-11, cycle 32): ▶ Listen in the reader — streams text-layer pages through /tts/ from the page in view, sentence-aware chunking for long pages, pause/stop mini player, auto-scroll to the page being read, graceful voice-missing message.~~
13. ~~Worker-deploy note (done 2026-06-11, cycle 33): `make worker` restart target + README warning; doctor detects stale workers via a CODE_STAMP round-trip task.~~
14. ~~Keyword cloud + queue filters (done 2026-06-11, cycle 35): weighted keyword cloud on the project literature page (10-min cached), clicking filters both the literature list and the reading queue by ?kw=.~~
15. ~~Responsive layout (done 2026-06-11, cycle 34, UI/UX): hamburger drawer below lg with backdrop + Escape close (Alpine), content reflows with responsive padding, wide tables scroll horizontally; verified at 420px in a real browser.~~
16. ~~`make doctor` (done 2026-06-11, cycle 33): manage.py doctor checks db/migrations/redis/worker-liveness+freshness/CSS/Tectonic/voice/media/API-key with ✓⚠✕ output and exit codes; verified live incl. catching a genuinely stale worker.~~
17. ~~Prompt variables (done 2026-06-11, cycle 36): `{{placeholder}}` parsing on Prompt (`variable_names` property), per-card fill-in inputs on the gallery, copy button substitutes filled values before writing to the clipboard.~~
18. ~~Bot run history charts (done 2026-06-11, cycle 37): pure-CSS bar sparkline of the last 20 runs per bot on the Automations page — bar height = headline number parsed from each result line (`BotRun.count`), failed runs in red, hover tooltip with date + result; history list capped at 5 with chart above; seeded demo runs. (Last-N retention shipped earlier in cycle 12.)~~
19. LaTeX compile service — vendor the Tectonic binary (like Tailwind/Piper pattern) behind a huey task with compile logs surfaced in the editor (idea added by cycle 13)
20. ~~Comment mentions (done 2026-06-11, cycle 38): `core/mentions.py` resolves `[[Note Title]]` (when exactly one note matches, any project) and `@cite-key` into markdown links before markdownify/nh3; applied via the `mentions` template filter in comment threads; unresolved/ambiguous mentions stay as typed; seeded demo comment exercises both.~~
21. ~~Queue gap-ordering (done 2026-06-11, cycle 41): "Fill matrix gaps" toggle on the reading queue — each queued paper scores by its least-read theme (READ/ANNOTATED counts), under-read themes float up with an amber "fills: <theme> (n read)" badge, unmarked papers sort last; default priority order unchanged.~~
22. ~~Pet hop (done 2026-06-11, cycle 42): milestone completion sends `HX-Trigger: atlas:milestone-completed`; a body listener restarts a calm two-bounce CSS animation on the sidebar pet (reduced-motion respected; un-checking stays quiet); verified in a real browser both ways.~~
23. ~~Tree grove (done 2026-06-11, cycle 43): "The grove" card on the dashboard — one tree per active project via the existing project_tree tag, size scales with milestone count (64px + 5/milestone, capped 112px), each tree links to its project; verified live with a screenshot.~~
24. ~~Upload progress bars (done 2026-06-11, cycle 44): bulk upload now sends one XHR per file with a slim live progress bar, done/failed state per row (filenames rendered via textContent), sequential to keep the server calm. Also repaired a template corruption found mid-slice: the upload script had been duplicated into the title and breadcrumbs blocks, redeclaring consts and silently breaking drag-and-drop — regression test added.~~
25. Search suggestion keyboard navigation (↑/↓/Enter) + recent-searches memory (idea added by cycle 19)
26. GIN trigram indexes on searched title fields once data grows (idea added by cycle 20 audit)
27. Last-Modified on media files + ETag support in the MCP client cache (idea added by cycle 21)
28. Loop-resilience note — chain notifications can drop and watchdog monitors expire at 30 min; watchdog is now re-armed every cycle (lesson from the cycle-21→22 stall)
29. Dev-process note — runserver/worker restarts must use pkill -f "[m]anage.py ..." (bracket trick) or they kill their own shell; documented after the cycle-23 debugging (idea added by cycle 23)
30. Editor split view — compiled PDF preview pane beside the source with sync scroll (idea added by cycle 24)
31. Comment markers rendered in the PDF margin at their anchor position (idea added by cycle 25)
32. tl;dr for whole PDFs — summarize the text layer per section in the reader (idea added by cycle 26)
33. SyncTeX-style jump — click in the PDF preview to jump to the matching source line (idea added by cycle 27)
34. Animated demo GIF for the README — scripted Playwright run through the killer 60-second flow (idea added by cycle 28)
35. Slim the Docker image — multi-stage build, piper/onnx as optional extra (~800 MB → ~300 MB) (idea added by cycle 29)
36. Containerized LaTeX compile — run Tectonic in a throwaway container/namespace to close the \input file-read residual risk if Atlas ever goes multi-user (idea added by cycle 30 audit)
37. Discover-similar in the reading queue — a "explore neighbors" action per queue item (idea added by cycle 31)
38. Listen prefetch — synthesize the next chunk while the current one plays to remove gaps (idea added by cycle 32)
39. Doctor on the Automations page — render the same checks in the UI with a stale-worker banner (idea added by cycle 33)
40. ~~Swipe + touch targets (done 2026-06-11, cycle 39, UI/UX): drawer closes on a >60px left swipe (Alpine touch handlers; short swipes ignored), milestone/task check-offs grew to 20/16px visuals with an invisible `after:-inset-2.5` pseudo-element giving ≈40×40px tap targets (+ shrink-0 so flex rows can't squeeze them); verified at 420px in a real touch browser.~~
41. Keyword cloud on the project overview card (idea added by cycle 35)
42. Audit log page — surface recent logins (incl. throttled attempts) and API activity on a simple "Activity & access" page, building on the new throttle counters (idea added by cycle 5, from the security pass)
43. Prompt variable defaults — `{{name|default}}` syntax pre-fills the fill-in inputs, and last-used values are remembered per prompt in localStorage (idea added by cycle 36)
44. Clickable chart bars — clicking a bot history bar filters the Inbox to captures created by that run (needs a run→capture link) (idea added by cycle 37)
45. Mentions everywhere — apply the same [[note]]/@cite-key resolution to decision records, experiment entries, and quick captures (one filter, three templates) (idea added by cycle 38)
46. Edge-swipe to open the drawer — touchstart within 24px of the left edge anywhere on the page slides the sidebar in (mirror of swipe-to-close) (idea added by cycle 39)
47. `make audit` target — pip-audit via uvx + the curl auth sweep as a one-command pre-audit script, so every 10th cycle starts from the same checklist (idea added by cycle 40, from AUDIT #4)
48. Matrix gap column hints — show each theme's read-count in the review matrix header so gaps are visible there too, linking back to the gap-ordered queue (idea added by cycle 41)
49. More pet reactions — a sparkle on phase completion and a brief "om nom" when a reference is marked read, all through the same HX-Trigger pattern (idea added by cycle 42)
50. Grove seasons — paused projects show bare autumn trees and archived ones fade out, so the grove reflects the whole portfolio at a glance (idea added by cycle 43)
51. Template lint pass — a tiny pytest that walks every template and asserts title/breadcrumbs blocks contain no `<script>` (the cycle-44 corruption class), plus django-template syntax check via the loader (idea added by cycle 44)
