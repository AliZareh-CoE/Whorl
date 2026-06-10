# DECISIONS

Running decision log for the Atlas build. Newest entries at the top of each section.

## Owner ideas (todo — outranks the auto backlog; only broken builds come first)

The owner adds ideas here (or tells the agent, who appends them). Work top-down; split big
ones into cycle-sized slices; mark done with date. Never delete — strike through and date.

1. **Performance: lightning fast & efficient.** Recurring concern, not one slice — every cycle
   should leave the app faster or no slower. ~~First slice (2026-06-10, cycle 4): N+1 audit —
   /library/ 49→6 queries, overview 17→13, plan 11→7; aggregate-based progress roll-up;
   heatmap day-aggregated in DB + 10-min cache; query-budget regression tests.~~ Remaining:
   conditional GETs/ETags (Backlog #11), fragment caching if pages ever feel slow.
2. **Security hardening.** Recurring concern alongside performance. ~~First slice
   (2026-06-10, cycle 5): cache-based login throttle (5 fails → 5-min lockout, 429, verified
   live), 50 MB upload cap + .pdf-only reference attachments enforced in forms AND API
   serializers, DRF rate throttles (3000/h keyed, 30/h anon), prod HSTS subdomains+preload +
   referrer-policy, X-Frame-Options DENY, login template now renders lockout errors.~~
   Remaining: API-key rotation helper, CSP if ever public-facing.
3. **Free local text-to-speech ("read this to me").** A strong free TTS engine (e.g. Piper)
   the owner can run locally; "Read aloud" on notes, abstracts, and (eventually) PDFs.
4. **Auto-download article PDFs.** When a reference is added, resolve and fetch the
   open-access PDF automatically (Unpaywall API, arXiv PDFs) into `Reference.pdf`.
5. **NLP helpers.** Language tooling where it genuinely helps: keyword extraction for
   auto-tag suggestions, abstract/note summarization, smarter related-paper matching.
6. **Prompt gallery.** A library of saved prompts (title, body, tags, copy button) for reuse
   with Claude or any LLM — global like the reference library, searchable, exposed via
   API/MCP so Claude can fetch the owner's prompts too.
7. **Bots / automations.** Background helpers that handle routine work: e.g. a citation-sync
   bot (periodic OpenAlex refresh), a retraction-watch bot (weekly bib check with findings to
   the inbox), a deadline-reminder bot (inbox capture N days before due dates), an inbox-triage
   suggester. Built on huey periodic tasks with an "Automations" page to enable/disable each
   bot and see its last run — and, where text understanding is needed, callable through the
   MCP/Claude side.
8. **Open-source readiness.** Goal: a public GitHub repo worth thousands of stars. Keep a
   living brainstorm in `OPENSOURCE.md` (positioning, killer demo GIFs, one-command install,
   docs site, LICENSE/CONTRIBUTING, comparison table vs Zotero/Notion/Overleaf, launch plan
   for HN/r/selfhosted). Loop may add thoughts there any cycle; polish items become slices.
9. **LaTeX editor ("better than Overleaf", owner knows it's ambitious).** In-browser LaTeX
   editing on manuscripts: CodeMirror editor + server-side compile (Tectonic binary is the
   likely engine — dependency decision required first) + live PDF preview using the existing
   pdf.js reader; cite-key autocomplete from the manuscript bibliography is the natural
   first slice.
10. **Commenting / annotations.** Comments anchored to things: PDFs (building on the reader),
    LaTeX sources, notes, documents — one generic Comment model, surfaced contextually.
11. **Better papers & literature reviews.** Continuous improvement of the lit-review
    experience. IMPORTANT constraint from the owner: NO paid Claude/LLM API calls — smart
    features must run either as local NLP (see #5) or through the owner's own Claude
    subscription via MCP (Claude as interactive collaborator, which costs nothing extra).
12. **Virtual pet 🐾.** A small companion that lives in Atlas and reacts to research life —
    fed by completed milestones, papers read, streaks; gets creative. NOTE: CLAUDE.md §1 says
    "no gamification", but owner directives outrank the constitution — keep it calm, charming,
    optional (a sidebar critter, not notification spam).
13. **Project-as-growing-tree UI.** Visualize each project as a tree that grows with real
    progress (milestones/phases done) — sprout → sapling → full tree at completion. SVG-based,
    calm, fits the editorial aesthetic; could live on the overview and/or projects index.
14. **World-class file & folder handling.** Faster, cleaner, easier: drag-and-drop upload,
    multi-file upload, inline rename, move via drag or quick-pick, breadcrumbed folder
    navigation, file previews where cheap.
15. **Lightning-fast search with NLP.** Upgrade global search: Postgres trigram/websearch
    tuning, typo tolerance, prefix-as-you-type results, synonym/stemming improvements,
    ranking tuned for research artifacts — local NLP only (see constraint in #11).

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
13. Audit log page — surface recent logins (incl. throttled attempts) and API activity on a simple "Activity & access" page, building on the new throttle counters (idea added by cycle 5, from the security pass)
