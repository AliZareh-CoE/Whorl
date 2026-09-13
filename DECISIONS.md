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
    ~~SPA Listen (done 2026-06-11, cycle 74): /app/references/:id reader with a 🔊 Listen button on the abstract streaming real Piper TTS in-app; sets up the reading-flow [REV].~~
   the owner can run locally; "Read aloud" on notes, abstracts, and (eventually) PDFs. ~~Notes (done 2026-09-07, #412): a listen button on the note editor, markdown stripped, chunked playback.~~
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
   the last 20 runs per bot with ✓/✕ shown in a Run history panel.~~ ~~Inbox-triage suggester — `notes/capture.py::detect` suggests paper/todo/decision per capture and the Inbox pre-selects it (retired as done 2026-09-07).~~ ~~MCP-side bots (done 2026-09-07, #417: list_bots / run_bot / toggle_bot).~~
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
   ~~Snippets and the section outline — both live in the Studio (2026-09-06 rebuild: activity-bar Outline panel, snippet completions in the shared editor core).~~
10. **Commenting / annotations.** ~~First slice (2026-06-11, cycle 14): generic `Comment`
    model (contenttypes) with markdown bodies; comment threads live on note, reference, and
    manuscript pages via one `_comments.html` include; kind allowlist guards the endpoint.~~
    ~~PDF-anchored comments (2026-06-11, cycle 25): `page` anchor on Comment; reader gains
    a sticky "Page comments" panel — IntersectionObserver tracks the page in view, comments
    pin to it, clicking one scrolls back to its page; page badges on detail threads; the
    `next` redirect is validated local-only (open-redirect guard + tests).~~
    ~~Comments on documents (2026-06-11, cycle 96): modal thread + live counts on every
    documents-table row, SPA and classic island both.~~ ~~LaTeX line-anchored comments in the editor (done 2026-09-07, #414: Studio Comments panel, gutter marks, line-number click).~~ Remaining: comments on folders;
    selection-anchored PDF comments.
11. **Better papers & literature reviews.** Continuous improvement; NO paid LLM APIs —
    local NLP or the owner's Claude subscription via MCP only. ~~First slice (2026-06-11,
    cycle 15): reading queue shows per-paper theme coverage badges (n/N themes); review
    matrix exports as a markdown table; `GET /api/v1/projects/{slug}/review-matrix/` +
    MCP tool `get_review_matrix` so Claude can discuss coverage gaps in chat.~~
    ~~Synthesis-note scaffolds (done 2026-06-11, cycle 72): 'Draft synthesis note' on the review matrix creates a theme-organized markdown note (papers under each theme with cell notes, unthemed backlog, synthesis prompt) — local logic, a running start for the write-up.~~ Remaining: coverage-gap suggestions beyond the queue gap-ordering already shipped.
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
    quick-move folder dropdown on every row, project-scoped.~~ ~~Cheap previews (done
    2026-06-14, #227): a "Preview" link on previewable rows (React DocumentsTable + classic
    fallback) opens documents:preview, which serves raster images inline and any text as
    text/plain, with X-Content-Type-Options:nosniff — SVG/HTML/PDF/binaries deliberately fall
    back to download (SVG/HTML can carry script that would run in Atlas's origin). New
    Document.is_previewable property + PREVIEWABLE_IMAGE_TYPES whitelist; previewUrl in the
    island props (null when not previewable). 5 tests incl. the security cases; verified the
    built chunk + props live.~~ ~~Breadcrumbed folder
    navigation (done 2026-06-14, #222): the nested-folder header on the documents page is now
    a clickable breadcrumb (root "Documents" → each ancestor → current), backed by a new
    Folder.ancestors property (walks the parent chain like .path, same query cost). Jump
    straight to any ancestor instead of going back to the tree. Live-verified on real data
    (Data / Pilot); 2 tests.~~ ~~Drag rows between folders (done 2026-09-07, #410): file rows drag onto folders or the root through the existing move mutation.~~
15. **Lightning-fast search with NLP.** ~~First slice (2026-06-11, cycle 19): pg_trgm
    extension + trigram typo-tolerance fallback; websearch query parsing ("quoted phrases",
    OR, -negation); as-you-type suggestion dropdown on the sidebar box (HTMX, 250 ms
    debounce, top 8 mixed results). Bonus correctness fix the tests forced: FTS now filters
    on the boolean match instead of a rank threshold — ts_rank ignores ! and & so negated
    terms previously leaked.~~ Remaining: synonym dictionaries, per-type ranking boosts,
    keyboard navigation in the dropdown.
16. **Animated, talking pet (owner, 2026-06-11; UI idea).** Mochi should be animated (idle
    breathing/blinking, not just the milestone hop) and should *talk* — short, meaningful
    lines based on context, habits, and general state: what's overdue, reading streaks,
    "you wrote 3 notes today", time-of-day greetings. Local logic only, no LLM APIs; calm
    tone, never naggy (consistent with the pet's no-guilt design). ~~Slice 1 (2026-06-11,
    cycle 49): idle breathing loop (CSS, reduced-motion safe, hop takes over then idle
    resumes) + `pet_speech()` — context lines from overdue/done milestones, today's notes,
    weekly reading streak, active phase progress, time-of-day fallback; hour-stable pick;
    speech bubble on /pet/ and italic line in the sidebar widget; browser-verified with a
    real data-driven line.~~ ~~Blink (the Creature blinks and breathes since the pet overhaul); habit
    signals (done 2026-09-07, #419: streak days, "not your usual hour", words written today);
    speech on hop (the sidebar shows the reaction line with the hop since the Buddy-style pass).~~
17. **Professional tree illustration with more growth phases (owner, 2026-06-11; UI idea).**
    Redraw the project tree as a more polished, professional SVG illustration with more
    distinct phases than the current five — richer trunk/branch structure, layered foliage,
    smoother stage transitions; keep it server-rendered, deterministic, and accent-colored.
    ~~Slice 1 (2026-06-11, cycle 51): full redraw — 8 stages (seed→sprout→seedling→sapling→
    young→established→mature→bloom), filled tapered curved trunk with per-project lean,
    staggered tapered branches with foliage tufts at their tips, 3-depth-layer canopy
    (back/mid/front opacities) densifying with progress, soft ground mound + roots from 45%,
    white-and-gold blossoms at 100%; everything interpolates with percent; verified across
    all 8 stages in a rendered strip + on overview/grove.~~ ~~Sway/seasonal variants — retired 2026-09-07: the tree was a classic-UI illustration; the SPA's Observatory identity replaced it with the constellation (#385) and the orbit (#392).~~

18. **Bulk actions + modals everywhere (owner, 2026-06-11).** Two parts: (a) **bulk
    actions for everything** — multi-select with checkboxes and act-on-many (move/tag/
    delete documents, set reading status on many papers, triage many inbox items, …);
    (b) **modals instead of URL navigation** — create/edit/confirm flows open in modals
    on the same page rather than navigating to separate form pages. Owner directive
    explicitly supersedes CLAUDE.md §7's "prefer full pages over modals" — modals are
    now the convention for object forms; full pages remain the no-JS fallback (HTMX
    loads the same form views into a shared modal shell). ~~Slice 1 (2026-06-11, cycle
    52): core/modals.py ModalFormMixin (HX-Request → _modal_form.html partial, valid
    POST → 204 + HX-Redirect, invalid → re-render in slot) + shared modal shell
    (Alpine: Escape/backdrop/✕ close) + #modal-slot in base; converted the plan page
    (add/edit phase, milestone, task) and documents page (new folder, rename/move) —
    browser-verified: open without URL change, Escape closes, real create lands.~~
    ~~Slice 2 (2026-06-11, cycle 53): bulk actions — documents page grew per-row
    checkboxes + select-all with an action bar (Move to folder, Add tag, Delete with a
    confirm modal); literature list AND reading queue: bulk set reading status; inbox:
    bulk dismiss / file-to-project. All endpoints act on id lists scoped to the project
    (cross-project ids ignored, tested), open-redirect guard on next, per-row saves keep
    updated_at honest for ETags/pet. Browser-verified end to end. These endpoints are the
    contract for the cycle-54 React documents-table island.~~
    Next slices: modals for projects, decisions, questions, manuscripts, prompts, tags +
    delete confirmations.

19. **React islands — hybrid frontend (owner, 2026-06-11).** Owner considered a full React
    SPA ("basic HTML/CSS can't make a pleasing UI"); after discussing trade-offs chose the
    **hybrid islands** path: Django pages remain the skeleton, but genuinely rich views
    mount React components — candidates in order: documents table (bulk actions UX),
    Atlas Assistant panel ([REV] #59), graph page chrome, LaTeX editor shell. Amends the
    constitution's "no React/no Node build" rule to: **a contained, islands-only Vite
    workspace** (`frontend/`, TypeScript, builds to `static/js/islands/`, `make js`,
    committed build artifacts so self-hosters still need no Node). Convention:
    `<div data-island="name" data-props="…json_script…">` + one loader script. Pages must
    still render useful content without the island (progressive enhancement).
    ~~Slice 1 (2026-06-11, cycle 54): frontend/ Vite+TS workspace building self-contained
    ES modules to static/js/islands/ (committed; make js); vanilla islands-loader.js
    (data-island/data-props/json_script convention, server markup stays as fallback on
    failure); first island = DocumentsTable — client-side sort + instant filter,
    shift-click range selection, sticky bulk bar (move/tag/delete with confirm dialog)
    calling the cycle-53 endpoints with CSRF from the cookie, server reload after actions
    keeps Django as source of truth.~~ Next: per-view conversions (assistant panel, graph
    chrome, LaTeX shell), one per cycle.

20. **FULL REACT SPA — committed (owner, 2026-06-11, supersedes the islands compromise
    in #19).** Owner's words: "the whole app should now be React"; confirmed via explicit
    choice with costs stated (~10-20 cycles, little else ships meanwhile). Strangler
    migration so Atlas stays usable every day:
    - **Stack:** Vite + React + TypeScript in the existing frontend/ workspace; react-router;
      data layer on the existing DRF API (gaps filled per slice). Tailwind stays. New deps
      allowed: react-router-dom, @tanstack/react-query.
    - **Auth:** session cookie + CSRF for the same-origin SPA — add SessionAuthentication
      alongside X-API-Key on the API (API-key behavior for MCP unchanged); login page stays
      server-rendered.
    - **Serving:** SPA shell served by Django at /app/ during migration; sections cut over
      one by one (old URLs redirect as their SPA route lands); final cutover moves / to the
      SPA. Islands infra retires at the end (DocumentsTable + Assistant become SPA components).
    - **Slices (one per cycle, each browser-verified):** ~~56 shell+router+layout+
      session/CSRF wiring + dashboard read-only (done 2026-06-11: /app/* login-gated shell,
      React Router + TanStack Query, SessionAuthentication beside the API key with CSRF
      enforced on writes (tested), GET /api/v1/dashboard/, React dashboard + projects list,
      deep links verified, zero JS errors)~~ → ~~57 projects list/overview (done 2026-06-11: /app/projects/:slug overview in React —
      phase+progress bar, counts grid, next milestones with overdue, recent documents/decisions
      via extended overview endpoint; client-side nav from dashboard/list; deep links; classic
      pages linked for unmigrated sections)~~ → ~~58 plan page w/ check-offs (done 2026-06-11: /app/projects/:slug/plan — phase cards
      with status/progress, optimistic milestone+task toggles via PATCH with TanStack
      invalidation of plan/overview/dashboard; found+fixed: the SPA shell never set the CSRF
      cookie (no form), so the first write 403'd — ensure_csrf_cookie on the shell + test;
      phase objectives/editing stay classic for now)~~ →
      ~~59 documents (done 2026-06-11: DocumentsTable extracted to a shared component used
      by both the classic-page island and /app/projects/:slug/documents; new documents-table
      API action; SPA mode refetches via TanStack instead of reloading, bulk endpoint returns
      JSON consuming the flash queue; found+fixed: ml-56 missing from built CSS — the SPA
      layout's classes had never been through make css, so the sidebar overlapped the table;
      folder tree + upload still classic, noted)~~ → [~~60 AUDIT #6 (done — see AUDITS.md)~~] → ~~61 library+queue (done 2026-06-11:
      /app/library with add-by-DOI + filter, /app/projects/:slug/literature with optimistic
      per-row reading-status PATCH + X-SPA bulk status, /app/projects/:slug/queue filtered
      and priority-sorted sharing the same component; reference_summary nested on the
      project-references API; reference detail stays classic, noted)~~ →
      ~~62 notes+editor (done 2026-06-11: /app/projects/:slug/notes list with backlink counts,
      textarea markdown editor (decision: no CodeMirror for notes — calm wins) with Ctrl-S,
      create+edit via the notes API (wiki-links sync server-side), POST /api/v1/notes/preview/
      renders nh3-sanitized HTML with [[wiki-links]] resolved — dangerouslySetInnerHTML is
      justified ONLY by that server-side sanitization; backlinks on the serializer)~~ →
      ~~63 writing board+manuscript (done 2026-06-11: manuscripts API added (serializer w/
      nested events + project_name, viewset, route); /app/writing status-column board,
      /app/manuscripts/:id detail with optimistic status select + submission timeline;
      LaTeX editor + cite check stay classic links until their own slice — CodeMirror-in-
      React deferred to that slice)~~ → ~~64 inbox, prompts, search (done
      2026-06-11; automations+pet split to 66 — noted; PLUS dogfood setup per Owner idea
      #21: 'Atlas — self-build' project created via the live API with 13 milestones/2
      phases/3 decisions, now at 8/13 after this cycle's self-check-off; found+fixed:
      SearchAPIView's pinned authentication_classes silently dropped session auth —
      regression test added; 2 genuine friction items captured → backlog)~~ → ~~[65 REV] (done 2026-06-11:
      Cmd/Ctrl-K command bar as a core SPA component — fuzzy jump-to-anything over the
      assistant index with classic→SPA URL mapping, VERBS: 'capture: text' creates inbox
      items and 'done: fuzzy' checks milestones off, page-aware quick actions, Ask-Claude
      MCP prompt copy, recents; keyboard-only verified — and it performed its own dogfood
      duties: this cycle's friction note was captured THROUGH the bar and the REV milestone
      checked off with 'done: revolutionary')~~ →
      ~~66 research+decisions (done 2026-06-11: read-only hypotheses/experiments/datasets
      API + /app/projects/:slug/research ledger page; /app/.../decisions timeline with a
      create form — the cycle's own split decision was recorded through it; automations+pet
      split to 67 — decision in the app's own decision log)~~ → ~~67 graph+automations+pet (done
      2026-06-11: /app/.../graph with CDN-lazy 3d-force-graph, 2D toggle, node side panel,
      sync button; /app/automations on a new bots API (list w/ runs, toggle/run actions)
      with inline run charts; /api/v1/pet/ + Mochi in the SPA sidebar with speech)~~ →
      ~~68 CUTOVER (done 2026-06-11: the SPA owns / + slash-less routes via explicit URL
      patterns (APPEND_SLASH never fires); classic keeps trailing-slash URLs + dashboard at
      /classic/; /app/* bookmarks 302; login lands in the SPA; verified live across all five
      scenarios; collision decision recorded in the app's own decision log)~~. THE FULL
      REACT MIGRATION IS COMPLETE — 13 cycles, exactly as scoped (56-68). Audits and revolutionary cycles continue on schedule.
    - **Standing constraints unchanged:** lightning-fast (code-split routes, prefetch),
      security (CSRF, no token in JS-readable storage beyond the session cookie), tests
      (API contract tests guard every migrated view), no paid LLM APIs.

21. **Dogfood Atlas with Atlas (owner, 2026-06-11).** "Add this project itself to the app
    and see if it's helpful" — the build manages itself inside the running Atlas: a real
    project ("Atlas — self-build") with the SPA migration + backlog as phases/milestones,
    decisions mirrored as decision records, friction observations captured as notes/inbox
    items. THE POINT: every cycle the loop must actually USE the product (check off its own
    milestone via the API/SPA, log its decision, capture ideas through quick-capture) and
    record anything annoying as a backlog idea — features get built from felt needs, not
    guesses. Setup in cycle 64 via the live API (no seed scripts — real usage only).

22. **Owner live-usage feedback (2026-06-11, during cycle 69):** "pages changing and
    refreshing — React shouldn't be that way" + "Ctrl-K new project not doing it".
    ~~Both fixed same cycle: a global link interceptor routes classic-style hrefs
    client-side wherever an SPA page exists (verified: 6 sidebar navigations + command-bar
    flows = 0 full page loads); /projects/new is a real SPA page so ⌘K → New project
    creates and lands on the overview without a reload. Plus Backlog #76 shipped: route-
    level code splitting, spa.js 137→90KB (29KB gz), pages are 1-3KB lazy chunks.~~
    Standing instruction: hard-reload feel anywhere in the SPA is a bug.

23. **Pet like the Claude pet (owner, 2026-06-11, during cycle 96).** "I want the pet to be
    something like the claude PET" — evolve Mochi toward the Claude Code pet experience:
    a small always-present animated pixel-art companion that visibly reacts to what's
    happening (events, streaks, completions), with personality in the reactions. Research
    what makes the Claude Code pet loved before building; UI/UX cycle candidate (97/98).
    ~~First slice (2026-06-11, cycle 97, UI/UX): researched Claude Buddy (observes context,
    speech-bubble reactions ~10s, stats shaping personality) and shipped the core of it:
    real speech bubble with tail above sidebar-Mochi rotating contextual observation lines
    every 20s; live reactions — petReact() events from milestone completion (plan + ⌘K),
    papers marked read (literature + read-flow), and quick captures flip the bubble to a
    celebration line + hop animation for 4s; Buddy-style personality stats (WISDOM from
    reading, FOCUS from milestones, CURIOSITY from notes+comments, GRIT from experiments+
    submissions, 0–10 curve) with a dominant-trait bar panel on /pet/ and a trait line in
    the speech pool. No nagging kept; 5-min cache kept. Browser-verified: bubble rotation,
    milestone→"A milestone falls! *happy hop*", personality panel.~~ ~~Species / hatching / rarity (done 2026-09-07, #427: four plumages + a 1-in-64 golden, decided per install).~~

24. **LaTeX: Overleaf parity, then beyond (owner, 2026-06-11, during cycle 100).** "this
    latex feature that we have is too stupid! still overleaf is better! we need to first
    add everything that overleaf has and on top of that make it even better than overleaf!"
    — escalates idea #9 into a multi-cycle epic, top owner priority from cycle 101:
    PLANNED (parallel planning agent, cycle 100→101) — the epic plan of record:
    **Parity slices** (one per cycle): 1✅ compile diagnostics (parsed errors, inline
    markers, problems panel, API compile surface) · 2 autosave + in-place compile (no page
    reloads, compile_generation guard against stale results) · 3 pdf.js preview pane
    [UI/UX] · 4 autocomplete v2 + snippets (\begin auto-close, \ref from \label scan,
    placeholder hopping) · 5 find/replace + vim/emacs keymaps + settings + native
    spellcheck · 6 [REV cycle 105] multi-file manuscript workbench (ManuscriptFile model,
    file tree, figures upload, compile with --untrusted, path traversal tests, latex_source
    synced to main.tex for back-compat) · 7 SyncTeX both directions (--synctex verified in
    vendored tectonic 0.15; Python .synctex.gz parser; forward first) · 8 outline panel +
    word count (Python detex) · 9 versions/history (ManuscriptRevision snapshots on
    compile + labels + difflib diff + restore; beats Overleaf free) · 10 templates gallery
    + symbol palette + zip export [UI/UX]. **Beyond-Overleaf** (111+): B1 library-powered
    cite autocomplete (whole project library, auto-links ManuscriptReference) · B2 live
    cite-check squiggles with add-by-DOI · B3 research side panel · B4 MCP LaTeX tools
    (read/update files, compile, diagnostics — Claude gets the full fix loop) · B5 compiles
    on the research timeline · B6 line-anchored comments · B7 arXiv submission package
    export. **Risks logged:** CM5 EOL (CM6-island contingency), SyncTeX parsing is the real
    work not the flag, multi-file needs --untrusted + strict path validation (#36 urgency),
    compile queue pile-up needs generation counter, stop-on-first-error is moot (tectonic
    halts hard — verified live).
    ~~Slice 9 (2026-06-11, cycle 109): version history — ManuscriptRevision (JSON
    snapshot of all text files) taken automatically on every successful compile + on manual
    "★ label"; History panel lists labeled (★) and automatic (relative-time) snapshots;
    clicking one opens a color-coded unified-diff modal (Python difflib) vs the current
    files with a one-click Restore (which snapshots "Before restore" first, so restoring is
    itself undoable); trim keeps all labeled + the last 50 automatic. Beats Overleaf free's
    24h history. Browser-verified compile→snapshot, diff, restore-undoes-edit. 6 new tests.~~
    ~~Slice 8 (2026-06-11, cycle 108): outline panel + word count — the file sidebar gains
    an Outline (client-side parse of \(sub)*section/chapter/part with depth indent,
    click-to-jump, debounced refresh on edit + on file switch) and a Word count button →
    writing/wordcount.py (pure-Python detex: strips comments/math/commands, keeps brace
    contents; reports words/headers/captions/inline-math, labeled "approx" since it differs
    from texcount) via GET .../word-count/ over all tex files; the button saves the active
    buffer first so the count matches the screen. Browser-verified (3 headings, click-jump,
    17 words). 3 new tests.~~
    ~~Slice 5 (2026-06-11, cycle 106): find/replace + keymaps + settings + spellcheck —
    CM5 search/searchcursor/dialog/jump-to-line addons (Find button + Ctrl/Cmd-F), an
    "⚙ Editor" popover with keybindings (default/sublime/vim/emacs), font size, and a
    spell-check toggle, all persisted in localStorage. Spellcheck required constructing the
    editor with inputStyle:contenteditable (CM5 only honors it at construction; the runtime
    toggle silently no-ops — found and fixed during verification), then toggling the
    spellcheck option live. Browser-verified all five + a contenteditable regression check
    (autocomplete + compile still work).~~
    ~~Slice 10 (2026-06-11, cycle 115): templates gallery + symbol palette — writing/
    templates_gallery.py with 6 code-defined starters (article, two-column, IEEE, beamer,
    thesis chapter, cover letter); "Start from template" select on the new-manuscript form
    seeds main.tex via the alias (create-only). Editor "Ω Symbols" popover: a 52-symbol grid
    (Greek/operators/relations/arrows) inserting at the cursor, placing the caret inside the
    first {} — free where Overleaf charges. Browser-verified: 7 options, 52 symbols, \alpha
    inserted. 3 tests. ALL 10 PARITY SLICES COMPLETE.~~
    ~~[REV] Slice 6 (2026-06-11, cycle 105, THE REVOLUTIONARY CYCLE): multi-file
    manuscript workbench — ManuscriptFile model (strict path validator: ASCII-only,
    no dotfiles/.., depth-capped; tex/bib/asset kinds), latex_source two-way alias kept
    for back-compat (queryset .update() avoids recursion; API PATCH writes the main file,
    editor save writes back), migrations 0006+0007 (data migration seeds main.tex),
    compile.py rewrite (writes the whole tree, --untrusted sandbox, resolve()-guard against
    traversal, bib no-clobber, pdf from main_path.with_suffix, explicit update_fields so a
    long compile never clobbers mid-compile edits), 6 classic X-SPA endpoints + DRF
    manuscript-files viewset, editor file-tree sidebar with swapDoc buffers keyed by a docs
    Map (saves read the doc never the live editor), per-file dirty/diagnostics filtering,
    upload + create + rename + delete. 48 tests incl. a 15-case path-traversal battery.
    Browser-verified: created sections/intro.tex, \input from main, switched buffers,
    multi-file compile rendered. Also made the editor full-width (Owner idea #25 slice 1).~~
    ~~Slice 4 (2026-06-11, cycle 104): autocomplete v2 + snippets — one latexHint
    dispatcher (cite → ref → env → command): \ref/\autoref complete from a \label scan
    of the buffer; \begin{x} completion auto-inserts the matching \end{x} with the
    cursor placed inside; command completion from a ~130-command table UNION the commands
    already used in the document (Overleaf's data-driven trick); \fig/\tab/\eq/\enum/
    \itemz snippets expand with Tab-hoppable placeholder bookmarks (custom ~40-line
    walker; CM5 has no snippet engine). Browser-verified all four flows.~~
    ~~Slice 3 (2026-06-11, cycle 103, UI/UX): pdf.js preview pane replaces the iframe —
    real rendered pages (pdfjs-dist 4.10, same CDN/version as the literature reader),
    fit-width default with −/+/fit zoom (persisted), page indicator (p. 2/5) tracking
    scroll, scroll position preserved across recompiles, old PDF dimmed while compiling;
    researched Overleaf/TeXstudio/LaTeX-Workshop viewer UX first per the design rule;
    browser-verified on a 5-page compile: zoom re-render, indicator, scrollTop kept ±0,
    zero reloads.~~
    ~~Slice 2 (2026-06-11, cycle 102): the editor stopped reloading — debounced 2s
    autosave (X-SPA JSON mode on the editor view, "Saved HH:MM" + missing-cite count,
    beforeunload guard, retry on failure), fetch-based compile with the existing poller,
    auto-compile-on-save toggle (localStorage), compile_generation counter so stale huey
    results are dropped (guard at task start AND before result write, tested), editor JS
    extracted to static/js/latex-editor.js (vite emptyOutDir=false keeps it); browser-
    verified: type→Saved, broken compile→problems panel, fix→green PDF, all with zero
    page loads (window-flag assertion).~~
    ~~Slice 1 (2026-06-11, cycle 101): writing/log_parser.py parses tectonic output
    (located errors, LaTeX warnings, bare errors; noise filtered) into
    Manuscript.compile_diagnostics; CM5 lint addon renders gutter markers + squiggles;
    "Compile problems" panel with click→jump-to-line; API parity: latex_source +
    compile fields on the serializer, POST /manuscripts/{id}/compile/ +
    GET compile-status/; browser-verified on a real broken compile (marker on L4,
    jump works) and a clean API round-trip (202 → ok + PDF).~~

25. **Use space efficiently — less whitespace, like Overleaf (owner, 2026-06-11, during
    cycle 105).** "the interface itself has too much white space, use your space
    efficiently! for instance look at overleaf!" — standing UI rule from now on: stop
    centering everything in a narrow max-w-5xl column with big empty margins; tool/work
    surfaces (editor, tables, boards, graph, dashboards) should use the full width and
    tighter vertical rhythm. First slice (cycle 105): base.html main width became an
    overridable {% block main_class %}; the LaTeX editor opted into max-w-none (full-width
    3-pane workbench, taller editor+preview). Cycle 142: the project OVERVIEW page — the
    product's heart — widened to max-w-6xl and tightened (header mb-6→2, description mb-8→4,
    phase card py-4→3, cards p-5→4, gaps 4→3, list rhythm space-y-2→1, headers text-sm→xs);
    cards now reach ~1390px vs ~1300px and the fold shows more without scrolling.
    Cycle 143: the PLAN page — max-w-6xl, header/section margins 6→4, phase cards onto the
    shared token (p-4), milestone rows py-2→1.5, objective/bar margins 3→2; HTMX check-off
    re-verified on the dense layout. Density tokens born (#153): .card / .card-title in
    app.css @layer components — overview + plan are the first consumers.
    Remaining (queued UI/UX cycles): dashboard, documents/literature tables, library,
    writing board — audit each for the centered-narrow-column antipattern and density.

26. **Overleaf UI — study it properly, match and exceed (owner, 2026-06-11, during cycle 118).**
    "go do more research on UI of overleaf and see what they really do and make sure you make it
    to theirs and beyond." The functional parity is done; this is about the *interface* itself —
    Overleaf's redesigned editor (2024): simplified top bar with File/Edit/View/Help menus;
    a left vertical icon rail (file tree, settings, help at the bottom); History/Share/Layout
    buttons top-right; a review/track-changes mode toggled top-right; collapsible panels via the
    divider bars; the error-log pane beside Recompile. A parallel planning agent is producing a
    gap matrix vs Atlas's editor; close the visual/interaction gaps over upcoming UI/UX cycles
    (menu bar, collapsible panels with divider handles, a left icon rail, review mode), then go
    beyond. Sources: docs.overleaf.com/getting-started/.../redesigned-overleaf-editor.
27. **The pet must be a REAL pet, not an emoji (owner, 2026-06-11, emphatic, during cycle 118).**
    "for the pet you are using an emoji and calling it a day! thats wrong you need to make a real
    pet!" Replace the emoji glyph with a properly DESIGNED creature: inline pixel-art/vector SVG
    (no new deps, no external assets), per growth stage (egg → hatchling → owl-scholar → sage),
    with real CSS animation (idle breathing/bob, blink, ear/wing twitch, the hop on events),
    expressive eyes/mood. This is the next UI/UX cycle (119) and a standing quality bar: the pet
    should look hand-crafted, not a Unicode character.
    ~~Done (2026-06-11, cycle 119): templates/core/_pet_svg.html + frontend PetSvg.tsx — a
    hand-drawn inline-SVG owl, distinct per stage (egg with crack → yellow hatchling with
    eggshell-hat → scholar owl with ear tufts + eye-discs + beak → sage owl with a graduation
    cap + twinkling star), shared by the classic sidebar, /pet/ page, and the React layout.
    CSS in app.css: breathing body, off-beat blink, sage sparkle twinkle, hop on events,
    sleeping closes the eyes + dims; prefers-reduced-motion respected. Browser-verified all
    stages + live in-app.~~

28. **Lean on open source — don't reinvent (owner, 2026-06-11, during cycle 120).** "never
    underestimate the power of open source community! we can use many things that they have
    built! there are lots of technologies out there that we dont need to reinvent them!" —
    standing engineering rule: BEFORE hand-rolling something non-trivial, check whether a
    mature, well-licensed (MIT/BSD/Apache/AGPL-compatible) library already solves it, and
    prefer it — vendored like Tailwind/Tectonic/Piper, via CDN like CodeMirror/pdf.js/
    3d-force-graph, or as a pinned dependency within §2's spirit. This must be weighed at
    every slice and especially at phase gates; raising a new dependency at a gate is
    encouraged when it replaces hand-rolled code with a battle-tested one. Concrete near-term
    applications (Overleaf-UI epic, idea #26): (a) the collapsible/drag-resize panels — use a
    proven splitter (e.g. Split.js, MIT) instead of hand-rolling pointer math; (b) consider
    migrating the editor to CodeMirror 6 (the snippet engine + multi-buffer were hand-rolled
    against EOL CM5 — CM6 has @codemirror/autocomplete, snippets, search, vim natively);
    (c) the SyncTeX parser — look for an existing JS/Python synctex reader before writing one.
    Caveat: stay within §2's no-Node-build-beyond-Vite and single-binary-vendoring spirit;
    every added dep gets a DECISIONS entry with the alternative-considered. Re-audit current
    hand-rolled code (snippet walker, drag logic, detex word count, diff) for OSS replacements
    when touched. The owner's earlier rule still binds: NO paid LLM APIs — but free/open-source
    tools and the owner's own Claude subscription are exactly the point of this rule.

29. **Give the pet a voice (owner, 2026-06-11, during cycle 122).** "we can also let our pet
    to have a voice and speak :)" — Mochi already has contextual speech lines (speech_lines)
    and Atlas already has a LOCAL TTS engine (Owner idea #3: Piper, the /tts/ endpoint, the
    "Read aloud" buttons) — NO paid API needed. Wire a small 🔊 affordance on the pet (sidebar
    widget + /pet/ page) that speaks the current speech line via /tts/, and optionally speak a
    reaction line in the hop moment (milestone done / paper read / capture) — gated behind a
    remembered mute toggle so it's never noisy (the no-nagging pet principle). Pixel-pet charm,
    not a chatterbox. Next pet UI/UX cycle.
    ~~Done (2026-06-12, cycle 131): a small 🔊 beside the pet's speech — on the /pet/ page
    bubble (Alpine) and the SPA sidebar bubble (React) — synthesizes the CURRENT line via the
    existing local Piper POST /tts/ and plays the WAV. Strictly opt-in: speaks only on click,
    never on load; the button shows … while speaking. Verified live on both surfaces
    (200 audio/wav, no autoplay, no console errors).~~

30. **File management / IDE epic — projects open like a workspace (owner, 2026-06-12, during
    cycle 147).** "One thing it's really lacking is file management! it should be able to open
    any file and contain any file exactly like a file manager efficiently it should be able to
    act like an IDE as well! so when I open a project I expect to see all the files and folders
    that I have and the thing is that to make everything easy we need to have strong project
    templates that have organised folders and file prebuilt and expandable. This app should be
    a monster and honestly Im kinda thinking of turning it into an App similar to how Vs code
    is an app but I'm not sure yet."
    Reading: (a) a real per-project FILE WORKSPACE — the existing Folder/Document tree grown
    into a first-class explorer (tree pane, open/preview ANY file type in-app: text/code with
    the CM6 editor we already bundle, PDF with the reader we already have, images, CSV/data,
    markdown), upload/move/rename/delete inline, drag-drop, keyboard nav; (b) PROJECT
    TEMPLATES — instantiating a project scaffolds an organized, expandable folder/file
    structure (e.g. literature/, data/, analysis/, manuscript/, protocols/, notes/) the way
    the manuscript template gallery already works, template definitions versioned and
    user-extensible (#128 pairs); (c) the DESKTOP APP question — owner unsure; web-first
    stays, but architect so a Tauri shell (local app, file-system access, OS file associations)
    can wrap the same Django+SPA later; do NOT block the epic on it. Plan of record to
    docs/plans/ via a parallel planner, then execute in slices like the LaTeX epic (#24).
    OWNER DECISIONS (same day, via question + follow-ups): (1) UNIFY into one tree — Documents
    + manuscript sources become one per-project hierarchy; (2) FULL desktop commitment NOW —
    Tauri first-class target, not a note; (3) "because I would like to have terminal in it as
    well!" — integrated terminal IS in scope (xterm.js + portable-pty over Tauri IPC,
    desktop-only, never web-exposed — grep-guard enforced); (4) "try your best to use open
    source projects so we can seriously get this done with the least effort" — build-vs-adopt
    table is normative (react-arborist, papaparse, lucide, Tauri plugins, pdf.js vendored).
    Plan of record: docs/plans/2026-06-12-file-workspace-ide-epic.md (9 slices).

31. **Achievements — lots, some just for fun, some brutal, "souls game mode on research"
    (owner, 2026-09-07).** ~~First slice (2026-09-07, #374): 57 achievements in four tiers
    (fun / steady / hard / souls) derived from real data with progress bars, hidden ones,
    first-unlock timestamps, score + ranks (Undergrad → Ashen One), an Achievements page,
    a toast on fresh unlocks, `get_achievements` for Claude, and Souls mode: the companion
    speaks grimly, the ledger counts deaths / bonfires / bosses / souls, and the studio
    flashes YOU DIED on a failed compile.~~ ~~Seasonal secrets, souls-only trophies and the
    Platinum (done 2026-09-07, #415: nine more, 95 in the ledger).~~

## Loop rules (amendments to CLAUDE.md §5, owner-directed)

- **The backlog must never be empty.** Every loop cycle MUST append at least one new,
  concrete, valuable idea to the Backlog below before it ends — the loop runs forever.
- **Cadence (owner rule, 2026-09-12): one shipped slice per hour.** `/loop 1h /cycle` fires the
  loop prompt at the top of every hour; each firing ships exactly one slice (built, verified,
  gated, pushed, recorded) and then waits for the next hour. Long slices finish properly and
  ship on the hour they are ready; a firing that lands mid-slice continues that slice.
- **Priority order each cycle:** (a) anything broken → (b) Owner ideas top-down →
  (c) auto Backlog top-down. New owner messages with ideas are appended to Owner ideas
  immediately.
- **Efficiency and security are standing constraints** on every slice, not just items 1–2.
- **Dogfooding (owner rule, 2026-06-11; STRENGTHENED same day: "use it for everything"):**
  the loop maintains "Atlas — self-build" inside the running app and routes its OWN
  workflow through the product wherever possible: plan upcoming slices as milestones
  BEFORE building them, keep cycle working notes as Atlas notes, record decisions in the
  decision log (not only DECISIONS.md), capture every idea via quick-capture/command bar,
  use Atlas search to find its own context, check off milestones at ship. The point is to
  hit obstacles a real user hits. Friction items become backlog ideas, always.
  **Anti-decay clause (added cycle 144, owner-prompted assessment):** dogfooding ROTS if
  the ritual is only quick-capture. EVERY ship must ALSO log+complete a milestone on
  atlas-self-build (Quality loop, phase 30) — not just a capture — and the inbox must be
  triaged down (cycle-log captures → assign to atlas-self-build + processed) at least every
  audit cycle, kept in single digits. An untriaged-inbox pile or a milestone ledger lagging
  the cycle count is itself a failure to surface, exactly the task-soup §1 opposes. Cycle 144
  caught this: ledger had stalled at cycle 131 (13 cycles missing) and 54/66 captures were
  untriaged; both were corrected via the API and the ritual updated.
- **Every 10th cycle is an audit cycle:** full security review + responsiveness/performance
  check of the whole system and everything added since the last audit (re-run the query
  audit, check page weights, throttle behavior, upload paths, dependency CVEs). Track cycle
  numbers in PROGRESS.md.
- **One of every 10 cycles is a REVOLUTIONARY cycle (owner rule, 2026-06-11):** a big
  idea with a big implementation — a feature whose impact is significant, not an
  increment. Plan it deliberately (it may span the cycle's full budget), verify it live,
  and make it count. First one: cycle 55. Candidate ideas live in the Backlog tagged
  [REV]; the loop must always keep at least one [REV] candidate in the list.
- **At least 2 of every 10 cycles are UI/UX improvement cycles** to world-class standards —
  polish, consistency, accessibility, interaction quality; not new features.
- **No paid LLM API calls, ever** — language-smart features go local-NLP or through the
  owner's Claude subscription via MCP.
- **Parallel planning workflows (owner rule, 2026-06-11, cycle 100):** while build cycles
  run, background planning agents design future additions "so they would be really good" —
  each big epic gets a researched, file-specific plan BEFORE its build cycles start; plan
  outputs land in DECISIONS.md (gap matrices, slice sequences) and drive the next cycles.
  First use: the LaTeX Overleaf-parity epic plan (launched during cycle 100's gate).
- **Tech improvement + design research every cycle (owner rule, 2026-06-11, cycle 94):**
  each cycle must also make a technological improvement, and UI work must be informed by
  researching what people actually like — specifically Apple's HIG design principles
  (clarity: every element immediately understandable; deference: the interface recedes,
  content stays front and center; depth/hierarchy: layers communicate relationships) and
  current UI/UX best practice (e.g. NN/g on filtered empty states: name the filter, never
  imply fault, always offer the clear action). Not Apple's ecosystem — their design
  thinking. Cite what was consulted in the cycle notes.

## Decisions

### 2026-09-13 — Find in project, and replace across files, on the server (#476)

**Decision.** `writing/search.py` searches every `.tex` and `.bib` file of a manuscript (plain text or a regular expression, case-folded unless asked, one hit per match with the whole line, a 500-hit cap flagged as `truncated`) and replaces across all of them or a chosen subset, saving each file through `ManuscriptFile.save()` so the alias, the word samples and the history behave as if the change had been typed. Surfaces: `GET /manuscripts/{id}/search/?q=&regex=&case=`, `POST /manuscripts/{id}/replace/`, a *Search* sidebar tab in the Studio (⌘⇧F, hits grouped by file with the match highlighted, click → the line, *Replace all n* behind a confirm that saves the open buffers first and reloads the changed files), MCP `search_manuscript` + `replace_in_manuscript` (109 tools). The search action looks the manuscript up by id directly, because the list's `?q=` title filter would otherwise hide it.

**Why.** Overleaf's project search is the feature people miss first in any other LaTeX editor, and renaming a label, a macro or a term across a multi-file paper is exactly what an author does before a resubmission. Doing it on the server keeps one implementation for the panel, the API and Claude; the hit list is the exact preview of what replace will touch. Alternatives: a client-side search over the loaded buffers (rejected — files not yet opened would be missed, and MCP would have nothing); CodeMirror's built-in find (kept — it is per file and stays).

### 2026-09-13 — The clock becomes actionable: when a nudge is fair (#475)

**Decision.** While a paper is *submitted* or *under review*, `clock.nudge` says whether a polite note to the editor is fair yet: after 1.5× your own median round at the venue (never under 60 days), or 90 days when you have no history there. A logged nudge — a `note` event whose text mentions "nudge" — restarts the count from its date, so the hint never nags twice for the same wait. Surfaces: the manuscript-page chip turns amber with "96 d with no word, usually 82 — a polite note to the editor is fair" and a *Log a nudge* button that writes the note event; the board card says "· nudge?"; the dashboard's *Needs attention* gains *waiting* rows; the API carries it on every manuscript and the dashboard payload, so MCP sees it through `list_manuscripts` / `get_manuscript` and can log the note with `add_submission_event` (no new tool).

**Why.** A clock that only counts is trivia; the decision it informs is "do I write to them now?", and the answer depends on what this venue usually does for you. Making the threshold your own history keeps it honest, the 60-day floor keeps it polite, and the reset-on-nudge keeps it quiet. Alternatives: a fixed 90 days for everyone (kept only as the no-history fallback); an email draft (rejected — Atlas does not send mail, and the note itself is what the timeline needs).

### 2026-09-13 — The status clock reads the timeline, and the venue's turnaround is your own (#474)

**Decision.** Every manuscript now carries a `clock`: since when it has sat in its status, how many days, and which event started the count — *under review* from the last `submitted` / `revision_submitted`, *revision* from `reviews_received`, *submitted* from `submitted`, *accepted* / *published* from theirs; drafting-type statuses (and a waiting status with no matching event) count from the last change. The board cards say "41 d revising"; the manuscript page shows the chip next to the deadline and, while the paper waits on a venue, "your median here: 55 d to a decision" from `GET /manuscripts/venue-turnaround/?venue=…` — every submission event paired with the next decision across your manuscripts at that venue (case-insensitive) — the current paper's finished rounds count too, its open one never can; `exclude` is there for callers who want it. MCP `get_venue_turnaround` (107 tools).

**Why.** "How long has it been?" and "is that normal for them?" are the two questions an author asks every week a paper is out, and the data was already in the submission timeline. Public turnaround databases are noisy and outdated; your own record at a venue is the number you trust. Alternatives: a `status_changed_at` column (rejected — the events already say it, and a column would drift from them); crowd-sourced turnaround (rejected — network, freshness, and it is not yours).

### 2026-09-13 — Figure audit: resolution is measured, not guessed (#473)

**Decision.** `writing/figures.py` reads every `\includegraphics` in the tree and answers the question a desk editor asks first: will this print? The asset's pixel size comes straight from the PNG / JPEG / GIF header (no image library — Pillow is not a dependency and the desktop freeze stays as it is), the printed width from the options (`width=0.8\textwidth`, `\columnwidth`, `\linewidth`, or an absolute `cm`/`in`/`mm`/`pt` length) against a 6.5 in text width, and the effective dpi is the ratio. 300 dpi is the bar journals state; under 150 the figure visibly pixelates and the row fails; over 10 MB is a warning; PDF, EPS and SVG are vector and pass on sight; a path that matches no file fails. Surfaces: a *Figure quality* pre-flight row that points at the worst figure's line (skipped when there are no figures), `GET /manuscripts/{id}/figure-audit/`, a figures table under the Studio pre-flight checks (name, verdict, format · pixels · dpi · size, click → the `\includegraphics` line, unused image assets listed), MCP `audit_figures` (106 tools). The demo manuscript now carries a real 1600-px figure so the audit has something to measure.

**Why.** Low-resolution figures are the most common reason a submission bounces before review, and nothing in the toolchain says so: LaTeX scales anything, the PDF viewer smooths it, Overleaf shows a thumbnail. The detail line says how many pixels wide the export needs to be, which is the only number the author needs. Alternatives: Pillow for exact metadata (rejected — a new dependency for three header reads); reading the compiled PDF's image objects (rejected — needs a compile, and the source tree is what gets submitted).

### 2026-09-13 — Lint fixes are applied on the server, verified against the text that is there (#472)

**Decision.** A lint finding that carries a `fix` now also carries `original`, the exact text at its `col`, so the replacement is mechanical: `writing/lint.py::apply_fixes` rewrites each file bottom-up (later spans first, so earlier columns stay valid), checks that `original` still sits at the span before touching it (a stale finding is skipped, never mis-applied), saves through `ManuscriptFile.save()` like an editor save, and returns the fresh lint. Seven rules fix themselves: `Figure~\ref`, `5\,ms`, ``` ``quotes'' ```, `\ldots`, `50\%`, `e.g.,` and a one-line `$$…$$` → `\[…\]`; `\begin{center}` in a float lost its fix (the matching `\end{center}` would have to go too). Surfaces: `POST /manuscripts/{id}/lint/fix/` (all, or `only` a chosen subset), a *Fix* button per row and *Fix all n* in the Problems panel (the editor saves its buffers first, then reloads the changed files), a palette action, MCP `fix_lint` (105 tools).

**Why.** Applying edits in the browser would have left the API and MCP without the feature, and the server already holds the whole tree and the exact spans. Verifying the original text makes the operation safe against an editor buffer that moved on. Alternatives: CodeMirror `changes` from the client (rejected — two implementations of the same replacement); regenerating the file from the finding list without verification (rejected — one stale finding would corrupt a line).

### 2026-09-12 — One linter in the Studio (#471, backlog #308)

**Decision.** The `codemirror-lang-latex` package's own linter is switched off (`enableLinting: false`). Its two checks worth keeping — an environment opened and never closed (or closed without a begin) and unbalanced braces — are now `unmatched-env` and `unclosed-brace` error rules in `writing/lint.py`, so they reach the Problems panel, the pre-flight row, the API and MCP like every other finding. The checks it got wrong for a multi-file paper (a `\ref` defined in another file read as undefined, "missing \begin{document}" on every `\input` section, per-file duplicate labels) are gone with it; the server's cross-file rules cover them correctly.

**Why.** Two linters over the same text disagreed, and only one of them was listed: the package underlined `Table \ref{tab:dprime}` in `sections/method.tex` as undefined while the panel said the reference resolved. One source, one panel — the answer to "where is what?" for a red underline must be the Problems panel. The cost is that brace and environment errors now appear on save (a few seconds after typing) rather than as you type; the autosave makes that a small gap.

### 2026-09-12 — A style lint for the mistakes a compile never reports (#470)

**Decision.** `writing/lint.py` is a pure, dependency-free linter over the manuscript's `.tex` files with thirteen rules split into *errors* (text that prints wrong: an unescaped `%` after a number, `\label` before `\caption`, duplicate and undefined labels across the whole tree) and *warnings* (style: a plain space before `\ref` or between a number and its unit, straight quotes, `...`, `$$`, `\begin{center}` in a float, `\\` as a paragraph break, a captioned float without a label, `e.g.`/`i.e.` without a comma). Comments, `verbatim`-like environments, `\url{}` arguments and table/align bodies are skipped. It is served as `GET /manuscripts/{id}/lint/`, merged into the Studio's Problems panel next to the compile diagnostics (a `lint` chip toggles it, refreshed on every save, findings underline the line and jump on click), a *Style lint* pre-flight row that points at the first finding and never blocks, and MCP `lint_manuscript` (104 tools). The editor now keeps pushed diagnostics as line numbers and positions them per run, so a file switch cannot replay stale offsets. Not chktex: no external binary, no config file, and only rules whose fix is obvious.

**Why.** Overleaf has no linter; chktex is a separate install with a hundred noisy rules. A researcher hits the same dozen LaTeX traps for years, and the compile is silent about every one of them. Alternatives: bundling chktex (a binary per platform in the desktop build, noisy defaults); a client-only lint in CodeMirror (rejected — the API and MCP would not see it, and the cross-file label rules need the whole tree).

### 2026-09-12 — Submitting runs the pre-flight; a blocked submission can still be recorded (#469)

**Decision.** `POST /manuscripts/{id}/submit/` is the one way a paper becomes *submitted*: it runs the pre-flight, answers 409 with the report when a check fails (unless `force`), and otherwise sets the status and logs the `SubmissionEvent` with the readiness summary in its notes — every fail/warn row, and "Submitted anyway over N blocking issue(s)" when forced. From *Revision* the same call logs `revision_submitted` and moves to *Under review*. The manuscript page's pipeline routes only those two clicks through the endpoint (every other step stays a plain PATCH); a 409 opens an in-app confirm listing the blockers with *Submit anyway* / *Not yet*. The *Deadline* check never blocks: a paper submitted after its deadline is a fact to record, not a mistake to prevent. MCP: `submit_manuscript(manuscript_id, force, date, notes)` (103 tools).

**Why.** The pre-flight only pays off if it fires at the moment it matters — the click that says "it's gone". Recording what was open at submission turns the timeline into the paper's audit trail. Alternatives: a hard block with no override (rejected — the owner may have submitted from a different tree, or a venue may not need a compiled PDF); running the checks client-side before a PATCH (rejected — the API and MCP would bypass them).

### 2026-09-07 — Audit #25: dependency drift fixed, new surfaces reviewed (#468)

**Decision.** The ten-cycle audit cadence had lapsed since June; this audit (AUDITS.md › #25) covered #263–#467. Findings: six Python advisories (django → 5.2.17, djangorestframework → 3.18.0, mcp → 1.29.1, pydantic-settings → 2.15.0, sqlparse → 0.6.0, cryptography → 50.0.1) and five React Router advisories (→ 7.18.3), all fixed; `pip-audit` and `npm audit --omit=dev` are clean. `mcp` is pinned `<2` (2.x renames FastMCP and breaks the server at import; a guard test keeps the pin). The new surfaces — snapshots, restore-by-name, pre-flight, client errors, watched folder, Tauri open/reveal, the terminal dock, Zotero import — reviewed with no code findings; hot endpoints all under 100 ms.

**Why.** Every-10th-cycle audits are a loop rule; the drift showed exactly why — the app code was fine, the lock file was not.

**Alternatives rejected.** Porting the MCP server to mcp 2.x inside the audit (a real slice, not a fix — Backlog); leaving Django on 5.2.15 because the advisories are server-side (the desktop serves HTTP on localhost; patch anyway).

### 2026-09-07 — Readiness where the status is changed, and a backlog sweep (#467)

**Decision.** The manuscript page (where the status pipeline is) gets a *Ready to submit?* card: the pre-flight summary as a pill and only the rows that need a look, "Run again", and a link that opens the Studio on the Pre-flight tab (`/editor?panel=preflight` — the Studio now honours `?panel=<tab>` for any sidebar tab). The board cards stay as they are: computing thirteen checks per card on every board load is the wrong trade. Backlog sweep: fifteen lines struck as done or obsolete (#28, #29, #36, #63 shell, #65, #66, #76, #83, #86, #91, #123, #134, #135, #164, #211), each with the reason; 34 open lines remain.

**Why.** A check that lives only inside the editor is missed at the moment it matters — the click on *Submitted*. And the backlog had accreted notes and long-done items that cost a pre-check every cycle (#201).

### 2026-09-07 — Submission pre-flight: "is this paper ready?" from real data (#466)

**Decision.** `writing/preflight.py::preflight(manuscript, network=False)` runs thirteen checks and answers each `ok` / `warn` / `fail` / `skip` with a one-line detail and, where there is a place to fix it, a `fix` pointer (`compile`, `problems`, a sidebar `tab`, a `line` in a file, the manuscript `settings`/`budget` page): the compiled PDF exists and its stored source hash matches the current tree (stale ⇒ warn, missing/failed ⇒ fail); compile errors (fail, with the first location); undefined citation/reference warnings (fail) vs. other warnings (noted); `\cite` keys missing from the bibliography (fail) and entries never cited (warn); the offline bib checkers — missing required fields, duplicates (warn) — plus DOI resolution and retractions only when `network=1` (a retraction fails); the venue budget (over ⇒ fail, near ⇒ warn, no limits ⇒ skip); every `\includegraphics` path resolves to an asset in the tree, extension optional (fail with file:line); leftover `% TODO/FIXME`, `\todo{}`, `\textcolor{red}` and `??` (warn with file:line); a `.bbl` kept for arXiv (warn); venue, deadline (past ⇒ fail, ≤3 days ⇒ warn) and abstract. `ready` is true when nothing fails. `GET /api/v1/manuscripts/{id}/preflight/`; MCP `preflight_manuscript` (102 tools); the Studio gets a sixth sidebar tab, *Pre-flight*, that runs on open, colours each row, offers the fix as a button (or a link to the manuscript page) and a "Run again"; the actions palette lists "Pre-flight check".

**Why.** Every other surface in the writing studio reports one dimension (budget, cite check, problems, bib report). The moment before "submit" needs them read together, in order, with nothing invented — a checklist from data, not from memory. Overleaf has none of this; journal submission systems reject for exactly these reasons.

**Alternatives rejected.** A stored "readiness score" (recomputing from data is cheap and can never go stale); blocking the status change to *submitted* on a failing pre-flight (the author decides; Atlas informs); network checks by default (slow, and the offline set is what blocks a submission in practice).

### 2026-09-07 — Two small ones: abstracts get a trigram index, Mochi gets a calendar (#465)

**Decision.** (#53) `Reference.abstract` gets a `gin_trgm_ops` GIN index (`reference_abstract_trgm`, literature 0009 via `PostgresAddIndex`, so SQLite skips the DDL) — the `?kw=` filter on the project literature pages and the review-matrix word match both scan abstracts with `icontains`, which the trigram index serves once a library is in the thousands. (#56) `core/pet.py::calendar_lines` adds one weekday line and one month line to the speech candidates (seven and twelve, all observations: "Friday. Leave the next step written down; Monday-you will be grateful."), and the milestone reaction pool grows from three to six so the hop moment repeats less.

**Why.** Both were the last two "small and certain" backlog items; bundling keeps the cycle honest (one commit, one gate) without pretending either is a feature.

**Alternatives rejected.** A speech line per holiday (locale-bound; the month is enough ambience); a full-text index on abstracts instead of trigram (the filters are substring matches, not ranked search — global search already has FTS).

### 2026-09-07 — Claude backs up before it bulk-edits (#464)

**Decision.** MCP tool `take_snapshot(list_only=false)` (101 tools): the default writes a snapshot through `POST /snapshots/` and answers the file, the rotation and the folder status; `list_only=true` reads `GET /snapshots/`. The docstring and the atlas-daily skill both say when: before a request that deletes or rewrites many things. No new API — the tool is the thin client the MCP contract requires.

**Why.** Product value 5: everything in the UI is available to Claude. A collaborator that can rewrite a plan outline or change forty reading statuses in one call should be able to take the backup that makes that safe, in the same breath.

**Alternatives rejected.** Two tools (list / take — one with a flag reads better in a 101-tool list); snapshotting automatically inside every write tool (slow, noisy, and the daily snapshot plus the rotation already bound the loss).

### 2026-09-07 — The backup you never have to remember (#462)

**Decision.** `core/snapshots.py`: `take_snapshot` writes the one-file backup (`core/backup.py`) into `<data dir>/backups/atlas-snapshot-<stamp>.zip` — under a `.partial` name first, renamed when complete — records a `BackupRecord(kind="auto", path=…)` (core 0013 adds `kind` and `path`) and prunes to the newest `KEEP = 7`. `due()` is true when there is at least one project and the newest snapshot on disk is 24 h old or missing; `run_if_due()` swallows a failure into `last_error` for Diagnostics instead of raising. The desktop starts one daemon thread at boot (`start_scheduler`: first check 90 s after launch, then hourly); a server install runs `manage.py snapshot --if-due` from cron. `GET/POST /api/v1/snapshots/` reads the status and takes one; the diagnostics report carries a `snapshots` block (JSON and the paste-me text); the Diagnostics page gets an *Automatic snapshots* section with the folder, the newest file, kept/total, *Snapshot now* and (desktop) *Show in folder*. `ATLAS_SNAPSHOT_DIR` moves the folder; `backups/` is gitignored for source checkouts. A snapshot counts as a backup for the #424 "last backup" nudge — it is one, on disk.

**Why.** The one-file backup only existed when the owner thought of it; a research tool that keeps a thesis's data must keep it without being asked. Seven daily zips in the data folder survive a bad restore, a wrong delete and an update gone wrong, and cost megabytes.

**Follow-on (#463, same day).** The snapshots on disk are listed in the Diagnostics section, each with *Restore…*: `POST /api/v1/restore/ {"snapshot": "<name>"}` stages that file (matched by name against the folder listing — a path never reaches the filesystem) exactly like an upload, so the existing staged-restore flow (confirm, restart, previous data kept) applies. Buttons disable while a restore is staged.

**Alternatives rejected.** A huey periodic task (the desktop runs huey immediate — periodic tasks never fire there); snapshot at launch only (an app left open for a week would never snapshot); Time-Machine-style incremental copies (the zip is small and a whole-file copy is what a person can actually restore); a setting for the interval and count (convention: a day, seven — `--keep` on the command for servers).

### 2026-09-07 — The hatch is a moment (#461)

**Decision.** The creature remembers the stage it last drew (`localStorage` `atlas-pet-stage`). When the stage it is asked to draw is *later* than that one, it plays a transition once: the egg shakes and cracks for a second and a half, then the new creature pops in with a little overshoot; then it stores the new stage. Later stage crossings (hatchling → scholar → sage) play the pop without the egg. Same drawing, same CSS variables; two keyframes in `app.css`. Reduced-motion users get the swap without the shake.

**Why.** Backlog #132 (owner idea #23's last line): the first finished work hatches the egg, and a hatch that just swaps a drawing throws the moment away.

**Alternatives rejected.** A modal or toast for the hatch (the sidebar creature *is* the place); an animation on every mount (once per stage, per install, or it becomes noise).

### 2026-09-07 — The compile rhythm is a signal (#460)

**Decision.** `writing/progress.py::compile_rhythm` counts compiles per day over two weeks from the revision snapshots every successful compile leaves (labeled ones included). It rides in the manuscript's `progress` payload as `compiles`; Writing cards show a dot row under the word sparkline ("· 7 compiles this week"); the Studio status bar says "· 3 compiles today"; and Mochi has a line for a compiling week. No new table: the revisions already were the record.

**Why.** Backlog #129 — word deltas say how much was written; compiles say how often the paper was *checked*. Together they are the writing rhythm.

### 2026-09-07 — Completions know which environment they are in (#459)

**Decision.** `frontend/src/editor/context.ts` scans the text before the cursor for the innermost unclosed `\begin{…}` and hands out ranking bonuses: `\item` first inside itemize / enumerate / description; `\includegraphics`, `\caption`, `\centering`, `\label` inside figure / table; `\hline`, `\multicolumn`, the booktabs rules inside tabular; `\label`, `\nonumber`, `\frac` inside equation / align. A wrapper around the language package's completion source applies them as CodeMirror `boost`s; nothing is added or removed, only reordered. Pure functions, tested under node.

**Why.** Backlog #117 — Overleaf's usage data shows these commands dominate their environments; typing `\i` inside a list should offer `\item` before `\includegraphics`.

### 2026-09-07 — Chevrons on the Studio's split gutters (#458)

**Decision.** Each Split.js divider in the Studio carries a small chevron: the one between the sidebar and the editor collapses the sidebar, the one between the editor and the PDF collapses the preview — the same toggles as ⌘B / ⌘\ and the header buttons, reachable where the hand already is when resizing. The chevron shows on hover of the gutter and does not interfere with dragging (it is a button inside the gutter, with its own click).

**Why.** Backlog #138 — Overleaf's thin-panel arrows are the gesture people reach for; the header icons are three inches away from the divider.

**Alternatives rejected.** Split.js `collapse(i)` (leaves a zero-width pane the layout must special-case; hiding the pane is what the toggles already do).

### 2026-09-07 — Two small ones: theme candidates everywhere, section copy on Review (#457)

**Decision.** (a) Every theme header in the review matrix now carries a "candidates →" link (shown on hover) to the queue pre-filtered to unread papers that look relevant to it — the gap nudge kept that door for under-read themes only (backlog #105). (b) Each section of the weekly Review has its own ⧉ copy that puts just that section on the clipboard as Markdown, next to the whole-week copy (backlog #99).

### 2026-09-07 — The revision trim says what it keeps (#456)

**Decision.** Every successful compile snapshots the source; the trim kept "all labeled + the last 50 automatic" silently. The History panel now states it — "Kept: all 2 labeled + the last 50 automatic (37 now)" — and the number is a control: click, enter a new cap (1–500), saved per manuscript (`auto_revisions_keep`, writing 0017, on the manuscript API too). The workbench revisions endpoint carries a `retention` block.

**Why.** Backlog #122: a vanished automatic snapshot looked like data loss. A rule you can read and change is not a surprise.

### 2026-09-07 — Identical source is not compiled twice (#455)

**Decision.** `writing/compile.py::source_hash` digests everything a compile reads — every text file's path and content, every asset's path and size, and the bibliography Atlas would generate when the tree ships no `references.bib`. The compile action stores it on the manuscript (`compile_source_hash`, writing 0016) when it queues; a successful compile stamps it as `compiled_source_hash`. A request whose digest matches a *running* compile answers 202 `{deduped: true}` without a second build; one whose digest matches the last *successful* compile (with a PDF on file) answers 200 `{unchanged: true}` and the studio says "Up to date — nothing changed since the last compile." `force` (body or query, and `compile_manuscript(force=True)` over MCP) compiles anyway — after installing the engine, say.

**Why.** Backlog #115: compile-on-save racing a ⌘↵, or a Recompile on an unchanged tree, ran Tectonic again for the same PDF — on the desktop that is a whole CPU core and, in immediate mode, a busy thread while the window waits.

**Alternatives rejected.** Debouncing in the studio only (Claude and the API can fire the same duplicates); hashing only the main file (sections and the bibliography change the PDF).

### 2026-09-07 — No installer? Run it from source (#454)

**Decision.** `make standalone` (PowerShell: `$env:DJANGO_SETTINGS_MODULE = "config.settings.desktop"; uv run python manage.py run_desktop`) runs exactly what the desktop shell runs — the SQLite, Docker-less, Node-less server — from a checkout, and any browser at 127.0.0.1:8000 is the app; `ATLAS_DATA_DIR` can point at the desktop app's data folder so both see the same projects. Documented at the top of the README and in the desktop README, verified on a fresh data dir (login answers after five seconds), guarded by a docs test.

**Why.** With GitHub not assigning build runners, the owner has no way to get the fixes since 0.1.139 — except the source. This path existed in the code (the shell has always called `run_desktop`) and nowhere in the docs.

### 2026-09-07 — One rule for archive member names (#453)

**Decision.** `core/archives.py::safe_archive_name(name)` normalises backslashes and `./`, and refuses absolute paths, drive letters, `..` segments, control characters and empty names. The three archive writers — the submission zip, the Markdown vault and the backup — go through it; a guard test asserts they keep doing so, and the submission zip is tested against a row injected past validation.

**Why.** Backlog #133 (from audit #12): the traversal guard lived inside one view; the vault and the backup came later and re-derived their own safety by construction. One helper, one test, no drift.

### 2026-09-07 — The Studio's PDF preview has a text layer (#452)

**Decision.** Each preview page is now a positioned wrap holding the canvas and a pdf.js `TextLayer` (the same class and `.textLayer` CSS the literature reader uses), so the compiled PDF's text can be selected and copied straight from the studio; page tracking, "go to page" and SyncTeX's forward marker read the wrap instead of the canvas, and the double-click-to-source binding moved onto the wrap so the text layer cannot swallow it. A page without text still renders.

**Why.** Backlog #116 — proofreading means copying a sentence out of the PDF into a note, a message or a search, and the preview was a picture.

**Alternatives rejected.** Rendering via pdf.js's full viewer (its chrome and CSS fight the studio's); a copy-page-text button (selection is the universal gesture).

### 2026-09-07 — The reading flow runs over any Library view (#450)

**Decision.** `GET /api/v1/references/reading-flow/?<library filters>` returns the flow's paper shape for whatever the Library workbench is showing (same params as the list: q, tag, view, year, project, reading status…); each paper names the project link the status applies through — the `project` filter's link, else the first unread link, else the first — and `id` is null when the paper sits in no project yet. `/library/read?<params>` opens the same reading flow page in library mode: statuses go through that link, "j" captures the note into the paper's project, Esc returns to the Library, and a paper with no project says so instead of pretending. The Library list header gets "Read these →" next to ".bib of this view".

**Why.** Backlog #85: a smart view ("to-cite, 2024, no notes yet") is a reading list, and the flow was the only place where reading is actually pleasant — it lived behind one project's queue.

**Alternatives rejected.** Auto-filing unfiled papers into a project to give them a status (the flow should not create links behind your back); a separate library-flow page (one page, two data sources).

### 2026-09-07 — The blank window, third pass: "mounted" now means painted (#451)

**Owner report.** A dark, empty Atlas window again, on the newest installer they could download (the release feed carries 0.1.138/0.1.139, built at 05:06–05:17 UTC; nothing newer can be built — see CI below). No boot panel in the screenshot.

**Finding.** `main.tsx` set `window.__atlasMounted = true` the moment the script *started*, so the watchdog in `spa.html` (#382) stood down before React had drawn anything: any failure after that line — a chunk import that hangs, a render that inserts an empty container and stalls — produced exactly the silent dark window the owner sees. The panel also skipped whenever `#root` had *any* child node, painted or not.

**Decision.** The flag is set by a probe that waits for readable text inside `#root` (checked four times a second for up to a minute); the watchdog fires at eight seconds unless text is on screen, reports the in-flight requests (`performance` resource entries without a response) next to the errors, says plainly when "the app started but never drew anything", and withdraws by itself if the app paints later (a slow first launch). Both surfaces post the report to `/api/v1/client-errors/` as before, so the server log and Diagnostics carry it.

**CI.** Every desktop-release run since 140 fails in four seconds with `runner_id: 0`, no steps and an empty check output — GitHub is not assigning runners to this account (the usual cause is the Actions spending limit or a failed payment; the API cannot show more). Until that is cleared on GitHub's side nothing after 0.1.139 can be built or shipped, including every fix listed in PROGRESS since then.

**Alternatives rejected.** Building the Windows installer here (the frozen server needs a Windows build host); re-triggering runs (a 403 on rerun, and a fresh push is a run — all fail the same way).

### 2026-09-07 — One guard over every raw-HTML sink (#449)

**Decision.** `core/tests/test_html_sinks.py` reads the SPA sources and the templates: every `dangerouslySetInnerHTML` must take a field named `…html` (server-rendered, nh3-sanitised — `Prose`, the citation HTML, the note preview) and never a concatenated or templated string; a raw `innerHTML =` may only clear a node or write a static literal (the gutter marker's SVG); templates carry no `|safe` or `autoescape off`; `mark_safe` exists in exactly one file, behind nh3. Backlog #152.

**Why.** The escape rule was true by convention and checked by review; now a new sink fails the suite before it ships. Four sinks and one `mark_safe` today — the test names them if that changes.

### 2026-09-07 — Two small ones: abstract peek in the rail, overview prefetch on hover (#448)

**Decision.** (a) The studio's bibliography rows carry the paper's abstract; a ▸ on the row unfolds it under the title, so "which paper was that again?" is answered without leaving the editor (backlog #126). (b) Hovering a project card on the Projects page prefetches that project's overview query (30 s fresh), so the click lands on a painted page (backlog #64).

**Why.** Both were felt while writing and navigating; both are one hook each. Kept together because neither is a feature on its own.

### 2026-09-07 — A Studio actions palette on ⌘⇧P (#447)

**Decision.** ⌘P already quick-opens files and sections; ⌘⇧P now opens an *actions* palette: save, compile, locate the cursor in the PDF, toggle sidebar / preview / problems, new file, download the submission .zip, jump to the Files / Outline / Bibliography / History / Comments panel, editor settings, keymap default ↔ vim, compile-on-save and PDF-follows-cursor toggles — every row with its key binding, filtered as you type, ↑↓ and Enter. The settings footer and the `?` shortcuts sheet mention it. Same modal chrome as quick-open.

**Why.** Backlog #119 and the half of #139 that matters (bindings shown next to actions): the toolbar is icons, the bindings were only in tooltips, and power users skip the mouse.

**Alternatives rejected.** Merging into the global ⌘K (⌘K jumps anywhere in Atlas; editor actions are contextual and the studio is full-screen); showing bindings in the toolbar itself (the header is already tight at 1280 px).

### 2026-09-07 — Duplicate a manuscript (#446)

**Decision.** `writing/services.py::duplicate_manuscript` and `POST /api/v1/manuscripts/{id}/duplicate/ {title?, project?, bibliography?}`: a fresh manuscript in idea status with every source file (text and assets, each asset with its own copy of the bytes), the venue limits, the venue and abstract, and — unless asked otherwise — the bibliography links with their cite-key overrides. Compile state, revisions, comments and submission events stay with the original; the tree mirror runs for the copy like for any new manuscript. The Writing board's card menu gets "Duplicate…" (a title prompt, then straight to the copy); Claude gets `duplicate_manuscript` (100 tools).

**Why.** Backlog #128: researchers reuse their own LaTeX skeleton — the class, the macros, the section layout, half the bibliography — far more than any gallery template. "Duplicate" is the user-defined template with no template model to maintain.

**Alternatives rejected.** A `ManuscriptTemplate` model with a save-as flow (a second thing to name, list and delete; a copy of the last paper is what people actually want); copying revisions and events (history belongs to the paper it happened to).

### 2026-09-07 — The cite completion adds the paper you don't have yet (#445)

**Decision.** The editor's `\cite{}` completion now filters the library itself (key, title, authors) and, when nothing matches — or the fragment *is* a DOI or arXiv id — ends the list with "Add a paper by DOI or arXiv id…" / "Add 10.…/… to the library". Accepting it asks for the id (skipped when the fragment already is one), adds the paper through `/references/by-doi/` into the project, links it to the manuscript's bibliography through the workbench `cite-library/` endpoint, replaces the fragment with the new key and reloads the completion pool. The amber cite-check diagnostic keeps pointing at the same door.

**Why.** Backlog #124: writing breaks the moment you have to leave the editor to hunt a paper; the library-wide completion (B1) covered everything already in Atlas, and this covers the rest.

**Alternatives rejected.** Searching Crossref by title from the fragment (a fuzzy guess inserted into a bibliography is how wrong citations happen; the DOI is exact); a separate "add paper" button in the studio rail (the moment of need is inside `\cite{}`).

### 2026-09-07 — The overview does not pay for the timeline's bodies (#444)

**Decision.** `project_timeline(project, bodies=False)` skips the markdown rendering #443 introduced; the overview's week digest — which already builds the event stream to say "this week in the project" — uses it. The Timeline page and its API keep the bodies. Backlog #108 (a mini-timeline strip on the overview) is struck: the week digest *is* that strip.

**Why.** Owner idea #1, performance, is never one slice: #443 quietly made every overview render every decision, note and entry body in the project. Caught the same day by reading the callers.

### 2026-09-07 — Timeline events open in place (#443)

**Decision.** Every timeline event that has a body now carries it as rendered HTML (`body_html`, through `core.rendering.render_body` — markdown, `[[links]]` and `@keys` resolved like everywhere else): a decision's context, decision and alternatives; an experiment entry's body; a note's text (first 1,500 characters); a milestone's notes; a manuscript event's notes. On the Timeline page a chevron on such rows expands the body under the event without leaving the page; the label still links to the object.

**Why.** Backlog #78 and #107: the timeline told you *that* a decision was made on a date and made you leave the page to read *what*; a project's history should read like a methods section, in one scroll.

**Alternatives rejected.** Truncated plain-text snippets on every row (noise on the rows that do not need it); a side panel (the timeline is the reading surface, not a list).

**Dead-idea sweep.** #69 (notes autosave), #70 (submission events from the SPA), #110 (pet species, #427), #114 (vendored editor), #121 (live word count, #413), #125 (cite-check across files) and #136 (pet voice) verified in the code and struck.

### 2026-09-07 — The submission package carries the .bbl (#442)

**Decision.** The compile runs Tectonic with `--keep-intermediates` and, on success, stores the generated bibliography (`main.bbl`) on the manuscript (`compiled_bbl`, writing 0015). `submission.zip` now writes it next to the sources, named after the main file (`paper.bbl` for `paper.tex`), unless the source tree already carries a `.bbl`. No compile yet → no `.bbl`, as before.

**Why.** Backlog #131: arXiv runs no BibTeX — a package with `.tex` + `.bib` and no `.bbl` builds with empty citations there. This is the single most common reason a first arXiv upload fails, and Atlas already had the file in the work directory; it only threw it away.

**Alternatives rejected.** Running BibTeX at export time (a second engine path, a second bundle download; the compile already produced the file); storing the `.bbl` as a `ManuscriptFile` (it would show in the studio's tree and invite edits that the next compile overwrites).

### 2026-09-07 — Claude can attach figures (#441)

**Decision.** `attach_manuscript_figure(manuscript_id, path, file_path)` (99 tools): the MCP client reads a local file, guesses its type and sends it multipart to `/manuscript-files/` as an `asset` at `path` (PATCH when an asset already sits there); the tool answers with the file row and a ready `\begin{figure}…\includegraphics…\label{fig:…}` snippet. `write_manuscript_file` stays the text path.

**Why.** Backlog #127: with `write_manuscript_file`, `draft_related_work` and the cite checker, a figure was the one thing Claude could not put into a paper end to end.

**Alternatives rejected.** Base64 in a JSON tool argument (megabytes through the model's context for nothing — the file is on the same machine as the MCP server); a separate figures API (the manuscript-files endpoint already stores assets and the studio already lists them).

### 2026-09-07 — Undo for inline triage (#440)

**Decision.** One global undo toast (`components/UndoToast.tsx`: `showUndo(message, undo)` + `UndoHost` mounted once in `main.tsx`, bottom-centre, six seconds, Esc dismisses, the newest replaces the last). Filing or dismissing a capture — from the Inbox (button or the `x`/`f` keys) or the dashboard's needs-attention row — shows "Filed under X — “…”" or "Dismissed — “…”" with **Undo**, which PATCHes the capture back to unprocessed with its previous project. Convert-to-object actions are not undoable this way (they created a paper, a note, a milestone — those have their own delete).

**Why.** Backlog #158: an inline action that vanishes a row must be worry-free, or people hesitate — and hesitation is exactly what the inbox is meant to remove.

**Alternatives rejected.** Confirm dialogs (the opposite of quick triage); a "recently dismissed" section (undo within seconds covers the real case; the Inbox already shows filed items per run and search finds captures).

### 2026-09-07 — Comments are searchable and can be resolved (#439)

**Decision.** `Comment.resolved_at` (core 0012). `PATCH /api/v1/comments/{id}/ {resolved}` resolves or reopens; the list endpoints carry `resolved_at`. In the Studio a resolved line comment greys out, drops its gutter mark and offers "reopen"; the Reference page's comments get the same toggle. Global search gains the `comment` kind on both paths — the snippet is the remark, the row says what it sits on (note title, paper, manuscript file and line) and whether it is open or resolved, and opens the note, the paper, or the manuscript editor. `Comment.target_route()` is the one place that knows where a comment lives.

**Why.** Backlog #109 ("where did I write that remark?" — comments were the last first-class text search could not see) and #130 (addressed feedback should clear, like a review tool, without deleting the record of what was said).

**Alternatives rejected.** Deleting instead of resolving (loses the trail; a resolved comment still answers "what did I decide about that paragraph?"); a separate comments page (search already is that page); a `resolved` boolean (the timestamp says when, for free).

### 2026-09-07 — Templates that plan (#438)

**Decision.** A built-in project template now carries three research-first parts beside its folders: a `plan` (a `plans.outline` Markdown outline — phases with objectives, milestones, a task or two), starter `questions` and review-matrix `themes`. `instantiate_template` lays each down only when the project has none of that kind, so re-applying a template, or applying it to a project that already has a plan, never duplicates. Empirical study: four phases / ten milestones / two questions / four themes (Theory, Method, Key finding, Limitation); Theory-review: scope → screening → synthesis → write-up with Claim / Evidence type / Population / Open problem; Software: design → build → evaluate → release; Minimal: one phase, one milestone. The New project cards state the counts; `/projects/templates/` carries them; `create_project(template=…)` over MCP gets the same.

**Why.** "Plans over backlogs" — an empty project with nice folders is still an empty project. The first plan is the hardest to write and the most formulaic; the template's job is to hand the researcher a plan to edit, not a blank page.

**Alternatives rejected.** Templates as DB rows the owner edits in the admin (they version with the code, like the writing gallery; a saved *snapshot* template already exists for the owner's own structures); applying the plan even when phases exist (would merge two plans — the outline endpoint is the deliberate way to rewrite one).

**Dead-idea sweep.** #57 (search budget): measured today at 14 queries / 27 ms on the demo library for three queries, well under the 50 ms bar — struck. #58 (grove tooltips): the grove exists only in the classic dashboard template, which the SPA replaced — struck.

### 2026-09-07 — The matrix writes the Related-work section (#437)

**Decision.** `POST /api/v1/manuscripts/{id}/related-work/` turns the project's review matrix into LaTeX (`literature/selectors.py::related_work_latex`): `\section{Related work}`, one `\subsection` per theme, every cell finding a sentence ending in `~\citep{key}`, papers marked without a finding gathered into one `\citep{a, b}`, empty themes and unthemed papers left as `%` comments (gaps to fill or drop), specials escaped. The section is saved as `sections/related-work.tex` in the manuscript's source tree (409 unless `overwrite`), every cited paper is added to the manuscript's bibliography so the cite checker passes, and the response carries the `\input{sections/related-work}` line. The Matrix page gets "Related work → .tex" (picks the manuscript when the project has several, confirms before replacing, shows a strip with a link into the studio); Claude gets `draft_related_work` (98 tools).

**Why.** Backlog #62's revolutionary half, minus the part that already existed (the synthesis *note*): the review matrix is where findings are extracted; the paper is where they must end up. Retyping thirty cells into `\citep` sentences was the tax. Now the matrix is the first draft of the related-work section and the bibliography stays consistent by construction.

**Alternatives rejected.** Inserting into `main.tex` directly (destructive; a separate file plus one `\input` line is reversible and matches how the demo manuscript is organised); a Markdown export instead of LaTeX (the studio is LaTeX and the cite checker is the point); letting the caller pick themes (one section per theme is the honest shape — delete a subsection in the editor).

### 2026-09-07 — Related papers reach the Reference page and Claude (#436)

**Decision.** The local TF-IDF neighbours (`literature/related.py`, title + abstract, cosine, no network) already fed the Library rail and `GET /references/{id}/related/`; now the Reference page shows them too ("Related in your library", with the similarity as a percentage) and Claude gets `get_related_in_library` (97 tools) — the local complement to `discover_related`, which asks OpenAlex for papers the library does not have. Backlog sweep with it: #1 (in-browser PDF viewer with highlight-to-note — the reader has done this since the Library v2 slices), #3 (embedding-based related papers — TF-IDF is the offline version and the whole point of Atlas is that it works on a train) and #11 (conditional GETs — API lists since #384, files since #434) are struck.

**Why.** "Where is what" — a paper's page is where you decide what to read next; making the reader open the Library rail for that was a detour. The MCP side is product value 5.

**Alternatives rejected.** Embeddings via a local model (a 100 MB+ dependency for a marginal gain on a few hundred abstracts; TF-IDF cosine is transparent and instant); computing related papers across projects only (the library is global by design, so is the neighbourhood).

### 2026-09-07 — Search remembers: recent searches and pins (#435)

**Decision.** The Search page keeps the last eight searches that returned results and lets you pin any query with the ☆ at the right of the box. With the box empty, pinned searches come first (amber, with an ✕ to unpin), then the recents (with a clear). Both live in this browser's `localStorage` (`atlas-search-recents`, `atlas-search-pins`) behind try/catch, like the library's list/cards choice — a convenience, not data: the search itself is the URL and `/api/v1/search/`.

**Why.** Backlog #55 (from the classic UI's recents dropdown, which the SPA never got). Researchers run the same three searches for weeks ("pupil", "dual-task", the reviewer's pet phrase); a chip beats retyping.

**Alternatives rejected.** A server-side SavedSearch model with API + MCP (nothing downstream needs a pinned search; if a smart view ever wants a saved *global* search, that is the moment to promote it); recording every keystroke's debounced query as a recent (only searches that returned something are worth remembering).

### 2026-09-07 — Served files revalidate for free: one conditional-GET helper (#434)

**Decision.** `core/files.py::file_response(request, field_file, …)` is now the only way Atlas hands out an uploaded file — document download, inline preview and the workspace raw view all go through it. It stamps `ETag` (`"<mtime>-<size>"`, from the storage so it works on any backend), `Last-Modified`, `Cache-Control: private, max-age=86400` and `nosniff`, and answers `If-None-Match` / `If-Modified-Since` with an empty 304. The magic-byte checks still run first (a 304 can never bypass #250). `/media/` (reference PDFs, compiled manuscripts, figures) already had this from `django.views.static.serve`.

**Why.** Backlog #54 and the second half of #11: the PDF reader and the studio re-open the same files all day; after the day of caching they re-downloaded them wholesale. Performance is owner idea #1 and never one slice. Backlog #251 asked for the inline-safety contract to live in one place — it now does, alongside the caching.

**Alternatives rejected.** A content hash as the ETag (reads the whole file per request; uploads are immutable, so mtime+size is exact); `ConditionalGetMiddleware` (it hashes the body for ETags and streams poorly with FileResponse); dropping the max-age in favour of revalidate-always (an extra round trip per PDF page load for nothing).

### 2026-09-07 — Library selection ergonomics: ranges and select-all (#433)

**Decision.** The last row you toggled (by checkbox or `x`) is the anchor; **shift-click** a checkbox or press **shift-x** on the row under the cursor to select everything between the anchor and it; **⌘A / Ctrl+A** (outside a text field) selects the whole view; Esc still clears. The hint line in the list header says so.

**Why.** Backlog #60's last open pieces. Bulk actions (link, tag, status, fetch PDFs, cite, export) were already there; selecting forty papers one checkbox at a time was the tax on using them.

**Alternatives rejected.** Drag-to-select (a marquee over a virtual list fights scrolling); "select all matching the filter, beyond the page" (the bulk endpoints take ids, and acting on rows you have not seen is how libraries get mangled).

### 2026-09-07 — ⌘K learns to make things: paper:, a bare DOI, and four creation verbs (#432)

**Decision.** The demo GIF's own last frame showed the gap: "add paper" typed into the palette matched nothing. Now `paper: <DOI or arXiv id>` (also `doi:`, `p:`) adds the paper to the library — and to the project you are in — through `POST /references/by-doi/`, and a bare DOI, `doi.org` URL or arXiv id typed on its own does the same without a prefix. Four static verbs join the list: "Add a paper by DOI or arXiv id" (Library with the add box focused via `?add=1`), "New note in this project" (`/notes/new`), "New manuscript" (Writing with the title box focused via `?new=1`), "New project". When nothing matches, the palette says so and lists the prefixes instead of showing a blank panel.

**Why.** "Ask Atlas anything" promised more than jumping; every first-class object should be creatable from the keyboard without knowing which page owns it. Product value 5 (machine-friendly) has a human cousin: the fastest path from thought to object.

**Alternatives rejected.** Fuzzy-matching page *contents* for creation intents ("note about X" → a note titled X): too clever for a palette; the verbs are explicit and the Inbox already does smart triage. A DOI verb that fetches metadata before showing the row: the fetch is the action, not the preview.

### 2026-09-07 — Today items can carry a time; the sidebar nudges (#431)

**Decision.** `TodoItem.due_at` (optional, UTC). The time is *parsed in the browser* (`frontend/src/app/dueTime.ts`): "call Sam at 3pm", "by 9:30", "@ 4pm", "at noon", "tomorrow at 9am" — am/pm or a colon is required, so "read at 3 papers" stays text; a time already an hour gone means tomorrow. The phrase is stripped from the text and `due_at` sent as ISO with the owner's offset. The Today page shows a time chip per row (quiet, amber within two hours, red once passed), the ⌘K `todo:` verb understands the same syntax, the dashboard's "On your list" rows show the time, and a **sidebar nudge** (`TodoNudge`, shares the `["todos"]` query, re-read every minute) surfaces the one item due within two hours or overdue by less than twelve. The Today header also counts what was carried over ("2 carried over from earlier days"). MCP `add_todo` takes `due_at` (ISO with offset). No reminders beyond the nudge: Atlas has no notification channel and does not want one (product value 4).

**Why.** Backlog #300's last two lines. A time on a scratch-list item is the difference between "call Sam" and actually calling Sam at three; a calm sidebar line is the whole reminder system a single user needs.

**Alternatives rejected.** Parsing on the server (the server keeps UTC; "3pm" is the owner's 3 pm, and the browser knows the zone — MCP callers pass an explicit ISO offset instead); a separate `next-due` endpoint (the list is ≤200 rows and already cached client-side); a datetime picker per row (the sentence is the picker; the API is there for anything else); system notifications (a channel Atlas deliberately lacks).

### 2026-09-07 — The README gets a moving picture: a scripted demo GIF (#430)

**Decision.** `scripts/demo_gif.py` drives the seeded demo through eleven screens — dashboard, project overview, plan, library, reading flow, a note, the 3D graph, the LaTeX studio (compiled first through the API so the preview shows a PDF), the review matrix, Connect Claude Code and the ⌘K palette with "add paper" typed — stamps a caption on each, and Pillow assembles the keyframes into `docs/demo.gif` (960 px, 128 colours, 2.2 s holds with one 50 % blend frame per cut; 22 frames, 3.0 MB). The README embeds it under the download line; `make demo-gif` re-shoots it; `core/tests/test_demo_gif.py` keeps it present, a real GIF, referenced and under 4 MB. Pillow is pulled in ad hoc with `uv run --with pillow` — a maintainer-only tool, not a dependency.

**Why.** Owner idea #8's remaining line ("demo GIF") and OPENSOURCE.md's own brief: the sales pitch is the whole loop in one unbroken picture. Screenshots show rooms; the GIF walks the house.

**Alternatives rejected.** A true 60-second screen recording (Playwright records WebM but the repo has no ffmpeg, GitHub READMEs cannot embed video, and a 60 s GIF is tens of MB); 3-step cross-fades (4× the bytes for a nicer cut — measured 6.5 MB); a hand-recorded GIF (rots the moment a screen changes; the script re-shoots in a minute).

### 2026-09-07 — The plan moves under the mouse: drag phases, drag milestones between phases (#429)

**Decision.** The phase number on each card is a drag handle: drop it on another card and the phase takes that card's place (`POST /api/v1/projects/{slug}/phases/reorder/ {ids}` writes `order` 1..n and `updated_at`, mirroring the to-do and smart-view reorders; unlisted phases keep their relative order after). Milestone rows are draggable too: dropping one on a different phase card moves it there (`PATCH /milestones/{id}/ {phase}`). Both are optimistic in the SPA and settle from the server. Cards ring indigo for a phase drop, emerald for a milestone drop; the two payloads use private MIME types so a card knows which it is being offered.

**Why.** A plan is written, then rearranged — "the pilot belongs in phase two after all" was a delete-and-retype. Plans over backlogs means rearranging must be as cheap as thinking it.

**Alternatives rejected.** Reordering milestones within a phase (they order by due date, which is the honest order); a dnd library (the native API already runs the other three drag surfaces); dragging tasks between milestones (rare; the task is one line to retype).

### 2026-09-07 — Global search reaches protocols, datasets and captures (#428)

**Decision.** Three object kinds were searchable nowhere: protocols (title + body), datasets (name, location, description — the FTS path had skipped them) and inbox captures (text; project may be null). Both search paths — Postgres FTS and the SQLite `icontains` fallback the desktop uses — now cover them, `describe()` gives each a snippet and a route (research page; the Inbox with the capture id), and the SPA groups them under Protocols, Datasets and Captures.

**Why.** "One search box in the sidebar" (Phase 3) means every first-class object. A protocol you wrote in June and a thought you jotted last week are exactly what search is for.

**Alternatives rejected.** Indexing to-do items and comments (short, context-bound text that mostly duplicates its parent — noise in a mixed result list); a separate "search captures" box on the Inbox (one box is the rule).

### 2026-09-07 — Mochi has a species (#427)

**Decision.** `core/pet.py::pet_species` hashes the Pet row's identity (pk + created_at) once: four plumages — tawny, snowy, barn, dusk — and one in sixty-four hatches golden (shiny, with a soft glow). The species rides in the pet state (`species: {key, name, blurb, shiny}`), the hatchling blurb names it ("Hatched — a barn owl!"), the pet page says "a snowy owl · the scholar · thriving" (eggs keep the secret), and the Creature takes a `species` prop that maps to a CSS class overriding the five `--mochi-*` palette variables — no new artwork, the same layered SVG in a different coat.

**Why.** Backlog #110 / owner idea #23's last line: a Buddy-style hatch moment with species and rarity. Deterministic from the install means it is *your* owl on every device that restores your backup; a colour-variable palette makes it a twelve-line change with no drift from the animations.

**Alternatives rejected.** Random at first sight with the result stored (a new field for something a hash gives for free); distinct body shapes per species (artwork and animation debt for a delight feature); a re-roll button (rarity means nothing if you can re-roll).

### 2026-09-07 — Performance pass: the references list stops asking for tags one row at a time (#426)

**Decision.** A query probe over the twenty hottest API endpoints on the demo data (cache cleared) found one N+1: the references list ran one `LibraryTag` query per row (36 queries for 50 rows; the `tags` field on the serializer reads the M2M). `prefetch_related("tags")` on both reference querysets takes it to 7, flat in the row count; a budget test pins it (40 rows, ≤ 12 queries). Everything else was flat: the dashboard is 23 queries warm (the heatmap and pet are cached), the project overview 51 queries at ~60 ms — each a cheap aggregate from a different selector, not a per-row pattern — the achievements ledger 77 single counts behind the pet's 5-minute cache.

**Why.** Owner idea #1: every cycle leaves the app faster or no slower. Today's slices added serializer fields (`progress`, `*_html`, `captures`) — the probe is how the loop checks they did not smuggle in per-row queries (they did not; the tags one predates them).

**Alternatives rejected.** Squeezing the overview's 51 into fewer by threading prefetched phases through six selectors (a refactor for ~20 ms on a page that already answers in 60); caching list responses (ETags already make the repeat case free).

### 2026-09-07 — A keyboard cheat sheet on `?` (#425)

**Decision.** `app/shortcuts.tsx` holds the one list of shortcuts the app answers to — everywhere (⌘K, ?, the inspector on the desktop), Inbox (j/k, ↵, 1–5, x), Notes (⌘S, `[[`, `@`), Studio (⌘S, ⌘↩, ⌘⇧J, ⌘B, ⌘\, ⌘J, ⌘P), Reader — rendered as a two-column card through the in-app notice dialog. `?` opens it anywhere except inside inputs, textareas, selects, contenteditable and the CodeMirror editor; "Keyboard shortcuts" is a ⌘K verb. The modifier label follows the platform (⌘ / Ctrl).

**Why.** The shortcuts existed in five places and were documented in none of them; a cheat sheet is how every keyboard-first tool makes them discoverable, and `?` is the convention.

**Alternatives rejected.** Deriving the list from the code (the bindings live in CodeMirror keymaps, React handlers and a palette — a hand-kept list with a guard test is honest and cheap); a dedicated page (a card that closes with Esc is what you want mid-task).

### 2026-09-07 — The app knows when it was last backed up (#424)

**Decision.** Every download of `/api/v1/backup.zip` writes a `core.BackupRecord` (size, media count, database kind; migration 0010). `core/backups.py::backup_status()` says when the last one was and whether that is *stale* — no backup within 14 days, or never — but only once there is data worth keeping (at least one project). It appears in three places: the Diagnostics header ("last backup 3 d ago", amber when stale, in the copyable report too), the dashboard's Needs-attention block as a calm amber row with the download link (the all-clear card yields to it), and `get_diagnostics` for Claude.

**Why.** A single-user desktop app is one disk failure away from losing a year of notes, and the backup button only helps if you remember it. A dated nudge is the smallest thing that makes people remember, and it never pops up, mails, or blocks.

**Alternatives rejected.** Automatic scheduled backups to a folder (a settings screen and a place to put them — later, if the owner asks); counting restores or Vault exports as backups (a vault is an export of one project, not the database).

### 2026-09-07 — A bar on the run chart opens the Inbox filtered to that run (#423)

**Decision.** `QuickCapture.bot_run` (nullable FK to `bots.BotRun`) records which automation run filed a capture: `run_bot` now creates the `BotRun` row *before* running the bot and holds it in a context variable that `_capture_once` reads, then fills in the outcome afterwards. The bots API returns each run's `id`, `GET /quick-capture/?run=<id>` filters to that run's captures, the Inbox honours `?run=` with a banner ("Showing what one automation run filed — n captures, m still open · Show the whole inbox") and the Automations run-history bars link to it when the run filed anything. Hand-written captures stay `bot_run = null`.

**Why.** Backlog #44: the chart said "3" and the Inbox could not say which three. The link needed the row to exist while the bot ran, hence the create-then-update.

**Alternatives rejected.** Tagging captures by text prefix (emoji-sniffing is not a foreign key); a `BotRun.capture_ids` JSON list (the FK gives the reverse relation and cascades correctly when a run is pruned).

### 2026-09-07 — Template lint: every template parses, chrome blocks stay clean (#422)

**Decision.** `core/tests/test_template_lint.py` walks every `.html` under `templates/` and each app's `templates/`, compiles it through the Django engine (a broken tag fails the build with the file name) and asserts that `{% block title %}` and `{% block breadcrumbs %}` contain no `<script>` or `<style>`. One parametrised test per template, so the failure names the file.

**Why.** Backlog #51: the cycle-44 corruption (a script pasted into a title block) took every page down at once and was only caught by eye. The classic templates are fewer now that the SPA is the front door, but the login page, the spa shell and the admin-side pages still go through them.

**Alternatives rejected.** A full render of each template (needs a context per template; parsing catches the syntax class, the smoke tests cover rendering); djlint as a dependency (a linter for a shrinking template tree).

### 2026-09-07 — The sparse documents table says what it is for (#421)

**Decision.** With three files or fewer (and no filter), the Documents table gets a dashed footer: how many files there are, what the page is for (the project's file cabinet), a link to upload or drop files in Files, and the one rule people trip over (papers' PDFs live in the Library). The empty state gains the same "Upload in Files →" action. The table itself is unchanged; nothing collapses or scrolls.

**Why.** Backlog #178: the wide layout made a three-row table look abandoned. Every empty state explains the page and offers the primary action (UI guideline); a *nearly* empty one deserves the same.

**Alternatives rejected.** A max-height (hides rows that fit fine); onboarding cards with icons (clutter for a page whose value is the table).

### 2026-09-07 — Narrow-width audit: three sideways scrolls fixed (#420)

**Decision.** A 900 px pass of `scripts/ui_audit.py` (light and dark) after today's slices found three pages scrolling sideways, none of them new code: the Documents table's `sr-only` header labels are absolutely positioned and escaped the `overflow-x-auto` scroller (the wrapper is now `relative`); the manuscript detail's two grid columns had `min-width: auto`, so a long cite key widened them past the track (`min-w-0`); the Literature header's link row was `shrink-0` and would not wrap (`flex-wrap`); and the manuscript title, an `<input>` that could only clip, is now a content-sized `<textarea>` (`field-sizing: content`, Enter blurs, newlines stripped) that wraps onto two lines instead of hiding the end of the title behind the studio button. The audit is clean at 900, 1280 light and 1280 dark desktop.

**Why.** UI guideline: wide content scrolls inside its own container, the page never scrolls horizontally. The desktop window is often narrower than a browser tab.

**Alternatives rejected.** Hiding the sr-only labels at narrow widths (they are the accessible names of the action columns); a horizontal-scroll wrapper around the manuscript columns (the content wraps fine once the column is allowed to be narrow).

### 2026-09-07 — Mochi notices habits: the streak, the hour, the writing (#419)

**Decision.** Three more observation lines in `_speech_candidates`, all from data already kept: the activity streak ("4 days running…", "12 days in a row — a habit now, not luck" from seven), the hour ("Not your usual hour. Curious what brought you here." when at least three usual working hours are known and this is not one of them, from the same hours set the achievements read), and today's writing ("+240 words today. The pen is moving.", "+1,200 words … A real session." from five hundred, from the #413 samples). The tone stays observational — no nagging, no "you should".

**Why.** Owner idea #16's remaining line: more habit signals. The pet is the one voice in the app allowed to comment on *how* you work; these three are the facts a good lab-mate would notice.

**Alternatives rejected.** A line for a broken streak ("you missed yesterday") — that is nagging, and the product value says never; time-of-day *suggestions* ("you work best in the morning") — an inference the data cannot support.

### 2026-09-07 — "Words written this month" on the dashboard (#418)

**Decision.** `monthly_stats()` gains `words_written`: the sum of positive day-to-day deltas of the daily word samples (#413) across every manuscript since the first of the month; a cut counts as zero, a manuscript's first-ever sample counts as nothing. The dashboard's stat row becomes six cells (three per row on small screens) with "words written this month" linking to Writing; `get_dashboard` carries it too.

**Why.** The stats row answered reading and note-taking but not writing, which is the output that actually leaves the lab. The samples were already there; the stat is one pass over them.

**Alternatives rejected.** Total words across manuscripts (a size, not a month's work); counting deletions as negative (a month of editing down a draft would show as negative writing, which reads as punishment).

### 2026-09-07 — Bots from the MCP side (#417)

**Decision.** Three thin tools over the existing bots API: `list_bots` (state, last result, recent runs), `run_bot(slug)` (run now, returns the result line) and `toggle_bot(slug)` (flip enabled). 96 tools. Nothing new server-side: the Automations page already spoke this contract.

**Why.** Owner idea #7's last line ("MCP-side bots"): Claude could read the Inbox the bots fill but could not ask a bot to run — "check the deadlines before we plan the week" needed a browser. Now the bots are one tool call away, which is also how a Claude-driven routine would schedule them.

**Alternatives rejected.** Bots implemented *inside* the MCP server (they would need the ORM the server deliberately has none of, and would stop running when Claude is not around); a `create_bot` tool (bots are code in `bots/registry.py`, not data).

### 2026-09-07 — A project as a Markdown vault (#416)

**Decision.** `GET /api/v1/projects/{slug}/vault/` streams a zip that is the whole project as text: `README.md` (description + front matter), `plan.md` (the same outline the Plan page round-trips), `questions.md`, `notes/<title>.md` (bodies as written — `[[wiki-links]]` and `@keys` intact — with the linked references as front matter), `decisions/<date> <title>.md`, `references.bib` + `literature.md` (a reading-status table and per-paper notes), `research/hypotheses.md` (with evidence and its citations), `research/experiments/`, `research/datasets.md`, `protocols/<title> v<n>.md`, `manuscripts/<title>/` (README with status + timeline, then the source tree) and `documents/<folders>/` (the uploaded files; `?documents=0` leaves them out). Titles become file names without punctuation; collisions get `(2)`. A manifest (`atlas-vault.json`) sits at the root. The overview kebab and the ⌘K palette ("Export this project as a Markdown vault") download it.

**Why.** No lock-in is a product value the backup only half-honours: a SQLite file is *yours* but not *readable*. A folder of Markdown opens in Obsidian, in a text editor, in git — and because the notes keep their links and cite keys, the vault is a working knowledge base, not a print-out.

**Alternatives rejected.** Obsidian-specific extras (`.obsidian/` config, callouts) — the plain files open there already and the dialect would leak into every other reader; an import path back (the vault is an export; the API and the backup remain the way in); one giant Markdown file (loses the folder-as-place structure the app is built on).

### 2026-09-07 — Achievements batch three: the calendar, the dark, and the platinum (#415)

**Decision.** Nine more trophies, all still read from real work. Five *seasonal secrets* (hidden until earned) read the activity calendar: New year, new hypothesis (Jan 1), Trick or treat (Oct 31), Solstice (Jun 21 or Dec 21), Leap of faith (Feb 29, steady tier), Friday the 13th. Three belong to Souls mode: Embrace the dark (switch it on), and two that only count while it is on — No bonfire (seven active days) and The Dark Soul (thirty, hidden) — backed by a new `Pet.souls_since` (core migration 0009) that `set_souls_mode` stamps when the mode goes on and clears when it goes off, so leaving and returning starts the count again. And the *Platinum*: every other achievement in the ledger, computed by `evaluate()` from the rest before its own row, listed last so `max_score` and the souls tier include it.

**Why.** Owner idea #31's remaining line: seasonal/secret achievements, a platinum for the whole ledger, souls-mode achievements that only count while it is on. The calendar ones are the kind you find by accident, which is the point of hidden ones; the souls-only ones make the mode a commitment rather than a skin.

**Alternatives rejected.** Counting souls days from the toggle's *first* use ever (a mode you switched off should not keep paying out); a platinum that excludes hidden trophies (then it is not the whole ledger); time-boxed seasonal events with a calendar of their own (a settings-shaped feature; a date check is enough).

### 2026-09-07 — Comments inside the Studio: line-anchored, in the gutter, in a panel (#414)

**Decision.** The Studio gets a *Comments* panel in its activity bar: every comment across the manuscript's source files (`GET /manuscripts/{id}/comments/`, newest first, with file path and line), a click jumps to the file and line, hover shows *delete* (`DELETE /comments/{id}/`), and "+ line N" comments on the line under the cursor. While the panel is open, a click on a line number comments on that line — closed, line numbers behave as line numbers. Commented lines carry the chat-bubble mark in the editor's comment gutter (the `setCommentLines` hook the shared editor core has had since Slice B; the marks follow the active file). The prompt is the in-app multiline dialog.

**Why.** Owner idea #10's last line ("LaTeX line-anchored comments in the editor"): the API, the model anchor and the gutter existed; the Studio rebuild never wired them, so the only way to leave a note on a line was `% TODO`. Overleaf's comments are the feature people miss most when they leave it.

**Alternatives rejected.** Comments on selections with text anchors (the anchor drifts as the text changes; a line is honest and the body can quote); always-on gutter click (line numbers are for selecting lines — the panel-open condition keeps that); a per-file fetch (one manuscript-wide request keeps the panel complete when the open file is not the commented one).

### 2026-09-07 — Writing progress: words per day, today's delta, the streak (#413)

**Decision.** `writing.WordCountSample` keeps one word count per manuscript per day (migration 0014), written whenever a `.tex` file is saved (the last save of the day wins) and whenever the word count is asked for (opening the Studio logs a baseline). `writing/progress.py` turns the samples into deltas — days without a sample carry the previous count forward with a zero delta — plus today's delta, this week's added words, the streak of consecutive writing days ending today or yesterday, and the best day. Surfaces: the word-count endpoint now also answers `today_delta`/`streak`/`week_delta` and the Studio status bar shows "+212 today · 3d streak"; every manuscript carries a 14-day `progress` in its API row and the Writing board draws it as a tiny bar sparkline with the delta beside it; `GET /manuscripts/{id}/progress/?days=` and the MCP tool `get_writing_progress` (93 tools) give the whole series. The demo manuscript is seeded with a fortnight of writing.

**Why.** The Studio counted words but the count had no memory: "how is the paper going?" needs yesterday's number too. A daily sample is the smallest thing that answers it, and it feeds the same places a writer looks (the status bar while writing, the board when choosing what to write).

**Alternatives rejected.** Deriving progress from manuscript revisions (`ManuscriptRevision` keeps content, but not every save makes a revision and counting each one on read is O(revisions)); per-save samples (a row per autosave — the daily grain is what the questions are asked at); a target-words goal with a ring (venue limits already exist as `venue_limits`; goals are a settings screen in disguise).

### 2026-09-07 — Read this note to me (#412)

**Decision.** The note editor's toolbar has a *listen* button: the title and body go through `speakable()` (a markdown stripper in `app/listen.ts` — `[[Note]]` and `@key` become their words, links their text, code blocks and images are skipped, headings/list markers/quotes/table rules go, each line ends as a sentence) and then through the same chunked, prefetched `listenTo` the abstract reader uses (#404), with an *i/n* progress in the button; switching notes or clicking again stops the voice; a missing voice model surfaces as the toast the export button already uses. No new endpoint: `/tts/` and the local Piper voice as before.

**Why.** Owner idea #3 asked for read-aloud on notes, abstracts and PDFs; abstracts had it, PDFs have the section tl;dr, notes had nothing — and a note is the thing you most want read back while walking. Stripping markdown matters: a voice reading "open bracket open bracket" is worse than none.

**Alternatives rejected.** Reading the rendered preview's `innerText` (the preview is a separate query and may lag the editor; the stripper works on what is being typed); a server-side `speakable` (the client has the text, and the chunker already lives there).

### 2026-09-07 — Where a paper appears: backlinks for references (#411)

**Decision.** `literature/usage.py::usage_of(reference)` collects every place a paper is used — notes that link it (the M2M) or cite it as `@key`, decisions / experiment entries / protocols / captures that mention `@key` (a whole-key match through the same `CITE_RE` the mention renderer uses, so `@lavie2010attentionb` is not `@lavie2010attention`), manuscripts whose bibliography carries it (with the cite key actually used), and evidence rows that point at it (with their direction). Served as `GET /api/v1/references/{id}/usage/` (grouped counts + rows with the SPA route to each), as the MCP tool `get_reference_usage` (92 tools), and on the Reference page as a "Where it appears" section between Highlights and Comments, manuscripts first because they are the costliest place to break. The empty state says how to make the paper appear somewhere.

**Why.** Notes have had backlinks since Phase 3; papers had none, although they are the thing a researcher most often asks "where did I use this?" about — before deleting one, before merging duplicates, when writing the related-work section. #407 made mentions live everywhere; this is the reverse index.

**Alternatives rejected.** Parsing `\cite{}` in manuscript `.tex` sources (a file read per manuscript per view; the bibliography membership is the contract the cite checker already enforces); a denormalised mention table maintained on save (more machinery for a per-page query that is a handful of `icontains` filters).

### 2026-09-07 — Files: drag a file onto a folder to move it (#410)

**Decision.** File rows in the Files explorer are `draggable`; the drag carries the document id under a private MIME type (`application/x-atlas-doc`), so folder rows and the tree's empty area — which already accept OS files for upload — tell the two apart: an Atlas row moves through the existing `PATCH /documents/{id}/ {folder}` mutation, an OS file uploads as before. Dropping on the folder the file is already in is a no-op; manuscript folders refuse drops as they did; manuscript source files are not draggable (the Studio owns them). The dragged row dims, the target folder rings, and the tree's border lights when the drop would go to the root.

**Why.** Owner idea #14's last remaining line ("drag rows between folders"): the Files page had the drop zones and the move mutation, only the row → folder gesture was missing, and the Move-to dropdown in the detail pane is three clicks for something every file manager does in one.

**Alternatives rejected.** A drag library (dnd-kit): the native API already drove the OS-file drops and the Today/smart-view reorders; multi-select drag: the explorer has no multi-select yet — when it does, the payload is a list.

### 2026-09-07 — One gate for page data: `queryGate` / `QueryBoundary` (#409)

**Decision.** `components/QueryBoundary.tsx` exports `queryGate(query, {skeleton, message})` — the node to render instead of the page while its query loads (the page's own skeleton, or `SkeletonPage`) or after it fails (`ErrorState` with the message, the error text and a retry) — and `QueryBoundary`, the same as a render-prop component. Nine pages that had a loading rung but no error rung (Reference, ReadingFlow, Automations, Graph, Prompts, Pet, Connect; inline rows on Report and Diagnostics) now go through it. `core/tests/test_query_boundary.py` fails the build when a page under `pages/` calls `useQuery` without `queryGate`, `QueryBoundary` or `ErrorState`; pages whose queries only decorate a static page (NewProject's templates, the Studio's per-panel queries, the plan widgets, the constellation, the PDF reader) are allowlisted by name.

**Why.** Backlog #282, and the owner's blank-window saga: a page that fetches and forgets the error branch shows a skeleton pulsing forever or nothing at all when the request fails — exactly the symptom a user cannot tell apart from a crash. The gate makes the error branch the default, and the guard makes forgetting it a red test.

**Alternatives rejected.** A hook (`useQueryView`) — it is not a hook, it calls none, and naming it like one invites the rules-of-hooks lint to complain about the early return; suspense + error boundaries per route (a larger migration of every query to `useSuspenseQuery`, and the page-level ErrorBoundary already exists for crashes — this is the *expected* failure path).

### 2026-09-07 — The matrix header says how much of each theme is actually read (#408)

**Decision.** Every theme row of the review-matrix table carries `read` (marked papers whose reading status is READ or ANNOTATED, via the same `theme_read_counts` the gap-ordered queue uses) next to `covered`/`total`. The column header shows "n read": green when every marked paper is read, a neutral chip linking to `/queue?theme=<name>` when some are unread, and an amber chip when nothing under the theme has been read yet. The queue's existing `?theme=` filter (unread candidates for a theme) is the landing page.

**Why.** Backlog #48: coverage ("how many papers mention this theme") and reading ("how many of those I have read") are different questions, and the matrix only answered the first. The gap-ordered queue knew the second but the number was invisible where the themes live.

**Alternatives rejected.** A separate "gaps" panel above the table (one more block to scan; the header is where the eye already is); sorting columns by gap (reorders the table under the reader — the number is enough).

### 2026-09-07 — Mentions everywhere: one renderer for every markdown body (#407)

**Decision.** `core/rendering.py` is the single markdown renderer: `resolve_mentions(body, project)` rewrites `[[Note Title]]` (resolved inside the project; globally only when the title is unique) and `@cite-key` into links, leaves unresolved mentions *visibly* in italics, and `render_body()` sanitises the result with nh3. The notes preview endpoint now calls it, and four serializers grew read-only companions: `context_html` / `decision_html` / `alternatives_html` on decisions, `body_html` on experiment entries and protocols, `text_html` on quick captures (with soft line breaks, because captures are jotted). The SPA shows them through one `<Prose>` component; the Decisions page clamps long records behind "Read the whole decision", the experiment log expands an entry on click, protocols render their steps, the Inbox renders captures. Internal links go through the existing SPA link interceptor, so a mention navigates without a reload. `core.mentions` is a project-less alias over the shared resolver.

**Why.** Backlog #45: decisions and lab entries are written in markdown and cite notes and papers, but the SPA showed them as truncated plain text — `[[Load theory overview]]` was dead ink outside Notes. One resolver means a mention behaves the same on every surface, and one HTML field per body keeps the client dumb (no markdown library in the bundle).

**Alternatives rejected.** Rendering markdown in the browser (a second sanitiser and a second mention resolver to keep in sync with the server's); a generic `/render/` endpoint the SPA calls per card (N requests per page for data the list already carries); leaving unresolved mentions as typed (the comments' old contract — the visible gap is the point, it says "this note does not exist yet").

### 2026-09-07 — A watched folder: drop a PDF on disk, it lands in the library (#406)

**Decision.** `literature/watch.py` watches one folder: a daemon thread scans it every 15 s while enabled, imports each new PDF once (a ledger of path, size and mtime; a file still being written waits for the next scan) through the same pipeline as a drag-drop import, optionally filing it into a project; the config lives in `<data dir>/watch.json` and the desktop launcher resumes watching on boot. `GET/POST /api/v1/watch-folder/` and `POST …/scan/` drive it; the Library rail shows the folder, its state and the last scan, with *scan now*, *stop*, and — on the desktop — the OS folder picker (`pick_folder`).

**Why.** Researchers save PDFs to a Downloads folder all day; a library that only fills through its own drop zone is a library that lags. Pointing Atlas at that folder makes "save the PDF" the whole import step, on the desktop where the folder lives.

**Alternatives rejected.** OS file-system events (inotify/ReadDirectoryChanges — platform code in the frozen build for a folder that changes a few times a day; polling is fine); moving or renaming the files (the folder is the owner's; the ledger remembers instead); recursive watching (a Downloads tree is full of things that are not papers).

### 2026-09-07 — AppImage, second attempt (#405)

**Decision.** `appimage` is back in the Linux bundle targets. The first attempt (#210f) failed because linuxdeploy could not relink the bundled Postgres shared objects; Postgres is gone since #286 and the only native libraries left are PyInstaller's own, which linuxdeploy handles. If the Linux job goes red on this, the target comes out again and this entry records why.

**Verdict (run 126, same day).** Red: the .deb and .rpm bundled, then `Bundling Atlas_0.1.126_amd64.AppImage` ended in `failed to bundle project: failed to run linuxdeploy` — the same relinking step, now presumably tripping over PyInstaller's bundled libraries rather than Postgres's. `appimage` is out of the targets again; .deb/.rpm stay. Backlog #288 is closed as *tried twice, not viable with a PyInstaller payload* — the way in, if ever, is a hand-built AppDir without linuxdeploy's library harvesting, which is its own project.

**Why.** Backlog #288: an AppImage runs on any distribution without a package manager, which is what a researcher on a locked-down lab machine needs. One CI run answers whether it works now.

**Alternatives rejected.** Flatpak (a different packaging world and a runtime the app does not need); shipping only .deb/.rpm (excludes every other distribution).

### 2026-09-07 — Read-aloud: chunked and prefetched (#404)

**Decision.** `app/listen.ts` splits the text into sentence-aware chunks of about 420 characters, synthesises the first, starts playing it, and fetches the next chunk while the current one plays; `stop()` aborts the fetch and the audio. The reading flow and the reference page use it; the pet's one-liners keep the plain call.

**Why.** Backlog #38: a 3 000-character abstract meant waiting for the whole synthesis before the first word, and anything past the 5 000-character cap was silently cut. Chunking starts playback within a sentence and reads everything; prefetching removes the gap between chunks that a naive loop would leave.

**Alternatives rejected.** Streaming WAV from the server (Piper synthesises sentence by sentence anyway, and a streaming response complicates the frozen server for the same result); a Web Audio scheduler (gapless to the millisecond, but far more code for spoken prose where a sentence boundary is a natural pause).

### 2026-09-07 — Reading queue: explore neighbours (#403)

**Decision.** A queue (and literature) row's menu carries *Similar in your library*: a panel above the list shows the paper's nearest neighbours from `GET /references/{id}/related/` (the existing local similarity), each with its year, a similarity percentage, a link to the paper and a `+ add here` that files it into this project; *explore beyond* opens the Library detail with the OpenAlex lenses.

**Why.** Backlog #37: while queueing what to read next, the question "what else do I have like this?" was two pages away. The similarity endpoint already existed; the panel just puts it where the reading decision happens.

**Alternatives rejected.** Inline expansion under each row (the list is a table of statuses; a single panel keeps it scannable); fetching OpenAlex neighbours here (network calls belong behind the explicit lens on the Library page).

### 2026-09-07 — Small polish: active nav icon tint, typeahead miss feedback; two ideas retired (#402)

**Decision.** The sidebar's active item tints its icon with the accent (backlog #172). In the Files tree, when typeahead finds no row starting with what was typed, the hint pill turns red, shakes once and says "no match" (backlog #185). Two older ideas are retired as moot: the "reset layout" confirmation (#163 — the SPA dashboard has no reset-layout control) and the pet reading its mood blurb (#162 — the click already reads the rotating bubble line, which is the mood).

**Why.** Both are the kind of feedback that stops a half-second of doubt: "am I on this page?" and "did my keystroke land?". Retiring the two dead ideas keeps the backlog honest.

**Alternatives rejected.** A sound on a typeahead miss (never); tinting every icon (the accent means "here", and only here).

### 2026-09-07 — A read-only token for the calendar URL (#401)

**Decision.** `core.FeedToken` is a single rotatable secret; the Dashboard's *subscribe (.ics)* now copies `…/calendar.ics?key=<feed token>` (from `GET /api/v1/feed-token/`), *rotate* (`POST`) mints a new one and every URL copied before stops working. The `?key=` authenticator accepts the feed token for the calendar feed only — it opens nothing else — and still accepts the API key so older subscriptions keep updating.

**Why.** Backlog #253: calendar services store subscription URLs on their servers; a URL that carries the API key hands out the whole API. A token that can only read deadlines, and that one click retires, is the right shape for something that leaves the machine.

**Alternatives rejected.** A token in the path (`/calendar/<token>.ics`) — the `?key=` contract already exists and the Dashboard is the only place that hands it out; per-project tokens (one secret to rotate is the point of a single-user tool).

### 2026-09-07 — Smart views: drag to reorder (#400)

**Decision.** `POST /api/v1/library-views/reorder/ {"ids": [...]}` sets the rail order (the given ids take positions 1..n, the rest follow; `updated_at` moves), the facets list views by position, and the rail rows are draggable with an insertion line.

**Why.** The last item of the Library-v2 list (#302/#306): the rail is the reading desk's shortcuts and the order should be the owner's, not creation order. Same contract shape as the Today list, same drag pattern.

**Alternatives rejected.** Up/down buttons (two clicks per move, and clutter on hover); alphabetical order (loses the "most used first" the owner arranges by hand).

### 2026-09-07 — The access log: who touched the door (#399)

**Decision.** `core.AccessEvent` records logins, failed logins, login lockouts and rejected API keys (address, user agent, a detail such as the username or the path), kept to the last 500 rows; Django's `user_logged_in` / `user_login_failed` signals, the lockout branch of the login form and the API-key authenticators feed it, and every write is best-effort so a failing log can never block the door. `GET /api/v1/access-events/` lists the events with a seven-day summary; Diagnostics gets an *Access* section and the paste-able report gets one line. The access log is excluded from the data-version bump so a probe cannot churn ETags.

**Why.** Backlog #42 (from the security pass): a self-hosted single-user app exposes one login and one API key, and until now nothing said whether anyone else had tried them. Successful API calls are deliberately not logged per request — Claude polls constantly — the rejected ones are the signal.

**Alternatives rejected.** Django's admin LogEntry (it records model edits, not access); logging every API request (a write per poll and a table that only grows); a separate "Activity & access" page (Diagnostics is already the "why did it do that" page).

### 2026-09-07 — Overview themes (#398)

**Decision.** The overview API carries `themes`: the salient phrases across the project's papers (titles and abstracts), notes, decisions and questions, extracted locally with `core.keywords` and weighted by how many of those sources mention each phrase. The overview shows them as a chip row under the counts, sized by weight; each chip searches the project for the phrase.

**Why.** Backlog #41: "what is this project about, in its own words" was nowhere on the page a visitor lands on. Ten phrases the material itself keeps using are a better answer than a description someone wrote in week one — and they change as the reading changes.

**Alternatives rejected.** A word cloud proper (random sizes and angles say less than a sorted row); topic modelling (a dependency and a fit step for a single-user tool; the RAKE-style extractor already existed for the matrix).

### 2026-09-07 — Library cards view; the unlock toast moves to the top-right (#397)

**Decision.** The Library list gains a *Cards* view (toggle in the list header, remembered per browser): cover-style cards with a colour band (the first project's accent, solid when a PDF is attached), the title, authors, year, venue, the reading status, the PDF/metadata pills and coloured tags; the same cursor, selection, keyboard and right-click behaviour as the rows, so nothing is lost by switching. The achievement toast now appears top-right, since every page's flash lives bottom-right and the two overlapped.

**Why.** The third page the Observatory pass named. Rows scan by title; cards scan by shape — a shelf you recognise papers on. The band doubles as the "which project, do I have the PDF" signal that the rows spell out in pills.

**Alternatives rejected.** Thumbnails of page one (rendering every PDF for a list view, and nothing for the 90% without a PDF); making cards the default (the list is denser and the keyboard flow was built on it).

### 2026-09-07 — Reader: comment markers in the margin, comment on this page (#396)

**Decision.** Each rendered page in the Library reader carries a gutter on its right: one speech-bubble marker per comment anchored to that page (the comment text on hover), and a `+` that appears on hover to comment on that page — a prompt dialog that lists the page's existing comments and posts the new one with `line = page` to the existing comments endpoint. The Library loads a paper's comments only while its reader is open.

**Why.** Backlog idea #31: comments already had a page anchor but only the reference page listed them, away from the page they were about. Marginalia belong in the margin; the reader is where the thought occurs.

**Alternatives rejected.** Anchoring comments to a rectangle like highlights (a highlight with a comment already does that — this is for the page-level thought); an inline comment editor in the gutter (the dialog keeps the page uncluttered and reuses the one dialog system).

### 2026-09-07 — tl;dr of a paper, section by section (#395)

**Decision.** `literature/tldr.py` finds the section headings in a paper's extracted text (known names such as Abstract/Methods/Results, or numbered short Title-Case lines; stops at the references), summarises each section with the local extractive summariser (two sentences), and records the page each section starts on. `GET /references/{id}/tldr/` serves it (falling back to the abstract, or saying why there is nothing), `get_reference_tldr` is the MCP tool (91), and the Library's detail pane has a *tl;dr* block that summarises on request with `p.N` buttons that open the PDF at the section.

**Why.** Backlog idea #32: the question before reading a paper is "is it worth my hour?", and the extracted text was already there for search. Section-wise sentences answer it in twenty seconds without a model or a network call, and the page buttons make the summary a table of contents into the PDF.

**Alternatives rejected.** An LLM summary (a network dependency and a cost for every paper; the extractive one is honest about being the paper's own sentences); summarising at import time (most papers are never opened — do it when asked, cache it in the browser for ten minutes).

### 2026-09-07 — Studio: the PDF follows the cursor (#394)

**Decision.** An editor setting, *PDF follows the cursor*, turns SyncTeX forward sync (#378) continuous: whenever the cursor line changes, a debounced effect resolves the line to its PDF spot and scrolls the preview there with the usual marker; nothing happens for lines without a position, when the preview is closed, or before a compile. Off by default; ⌘⇧J keeps working either way.

**Why.** Backlog idea #30 asked for the split view with sync scroll. The map and the marker existed; the only missing piece was letting the cursor drive them without a keystroke, which is how every LaTeX IDE's "auto sync" feels. Off by default because a scrolling preview is a distraction while drafting; on while polishing, it is exactly what you want.

**Alternatives rejected.** Following the editor's scroll position instead of the cursor (the cursor is what the writer is thinking about); scrolling the editor when the PDF scrolls (the double-click already does that on demand — continuous inverse sync fights the writer).

### 2026-09-07 — Prompts: `{{name|default}}` and remembered fill-ins (#393)

**Decision.** A placeholder may carry a default after a pipe — `{{venue|NeurIPS}}` — which fills in unless the user types something; the first occurrence that carries a default speaks for every occurrence of that name. `Prompt.variables` (name + default) is on the API, `render_prompt()` applies value → default → the bare placeholder left visible, and the gallery shows the default as the input's placeholder. The values typed for a prompt are remembered per prompt in the browser (`atlas-prompt-values:<id>`) and come back next time.

**Why.** Backlog #43: most fill-ins have a usual answer (the venue, the advisor's name, the model), and retyping them every copy is friction that the prompt itself can carry. Remembering the last values is the same idea for the ones that vary slowly.

**Alternatives rejected.** Storing last-used values server-side (a browser convenience, not data); Jinja-style templating in prompts (a whole language for what is one pipe).

### 2026-09-07 — Observatory second pass: the plan as an orbit (#392)

**Decision.** Under the Plan header (cards mode), one SVG strip draws the phases as arcs of an orbit, each sized by its milestone count: a done phase is a solid line in the accent, the phase in progress glows and fills to its progress, a blocked one is amber, a not-started one dashed and dim. Every milestone is a moon on its arc — filled when done, ringed red when overdue — with the title on hover, and each phase shows its `done/total` under the arc. Clicking an arc scrolls to that phase's card. No request: it renders the plan the page already holds.

**Why.** The plan page opened on a stack of cards with no picture of the whole; the roadmap tab has the dates but takes a click. One glance at the orbit says where the project is, what is late, and how much lies ahead — the "plans over backlogs" value made visible, and the second of the pages the Observatory pass named.

**Alternatives rejected.** A time-scaled axis (phases without dates would collapse; the roadmap tab already does time); a circular orbit (reads as decoration and wastes the width); moving the roadmap into the header (too dense for a glance).

### 2026-09-07 — ⌘K: the safe verbs (#391)

**Decision.** The palette's static verbs grow from two to eight: copy this project's `.bib` / the whole library as `.bib` (fetches the export and puts it on the clipboard, reporting the entry count), go to this week's review, new quick capture (the inbox), warm up the LaTeX engine, download a backup, and — desktop only — open the web inspector. Each returns the one-line result the palette flashes.

**Why.** Backlog #279 asked for the actions the owner repeats, side-effect-light so a mistaken Enter never destroys anything: every verb here copies, navigates, downloads or warms a cache. The bibliography copy is the one that saves a trip through the Library every time a citation is needed in another tool.

**Alternatives rejected.** Verbs that delete or move things (the whole point is that Enter is safe); a nested "Commands…" submenu (the fuzzy match over keywords already finds them).

### 2026-09-07 — CI boots the app in a browser against every platform's frozen server (#390)

**Decision.** The release workflow's frozen-server smoke test now also runs `scripts/boot_check.py`: a Playwright Chromium logs in, pretends to be the Tauri web view, loads the dashboard, projects, library and diagnostics pages, and fails the build on an empty root, a missing sidebar, a page or console error, an HTTP error, or either failure panel. Screenshots are uploaded as the `boot-check-<platform>` artifact (kept 14 days), so the Windows rendering can be looked at without a Windows machine.

**Why.** Every failure this week was Windows-only, and the only Windows machine in the loop is the owner's. The frozen server already answered curl in CI; drawing the app is the thing that broke, and a browser on the runner is the closest stand-in for the web view that a Linux container cannot provide.

**Alternatives rejected.** Running the Tauri app itself on the runner (no display, and the shell has no test hook); trusting the Linux boot check to stand for Windows (it passed while the owner's window was blank).

### 2026-09-07 — The desktop ships the web inspector, opened on demand (#389)

**Decision.** `tauri` is built with the `devtools` feature; an `open_devtools` command opens the web view's inspector for the main window; the SPA binds F12 and Ctrl/⌘+Shift+I to it, Diagnostics gets a *Web inspector* button, and the boot-failure panel offers "Open the inspector" whenever the Tauri bridge exists.

**Why.** The blank-window report had no console behind it; #382 captures what the page throws, but a console the owner can open is the general tool — network tab, element tree, the live error — for every future "it doesn't show". Opening it is a deliberate act (a key or a button), so ordinary use never sees it.

**Alternatives rejected.** A debug build for the owner (a second artefact to maintain and download); auto-opening the inspector on an error (frightening, and the panel already carries the text).

### 2026-09-07 — Achievements, batch two (#388)

**Decision.** Twenty-nine more achievements (86 in all): twelve fun (colour-coded tags, a working lunch, midnight oil, 25 PDFs, 50 DOIs, ten comments, a hundred documents, a four-file manuscript, three smart views, a second project, five to-dos in a day, a hidden anniversary), seven steady (a fortnight streak, forty active days, fifty commented highlights, a balanced evidence ledger, five projects, 250 papers, ten phases), five hard (a 90-day streak, two hundred active days, five hundred highlights, ten manuscripts, three complete projects) and five souls (a hundred deaths, fifty bonfires, five rejections, a hidden Dragonslayer for three acceptances, a hidden Estus for twenty failed and twenty good compiles). Sixteen new facts feed them, all counts on data that already exists.

**Why.** The owner asked for "a lot" and for hard ones; the first batch covered the obvious milestones, this one covers habits (streaks, active days, the hour of the day), the library's hygiene (colours, DOIs, PDFs), and the writing grind — the places a researcher actually spends the year. Souls-tier entries stay grim and honest: deaths are rejections, contradictions and failed compiles.

**Alternatives rejected.** Achievements for opening pages or clicking buttons (cheap, unearned, and they would need tracking that does not exist); weekly "seasonal" resets (a ledger should never take anything away).

### 2026-09-07 — Observatory second pass: the project's constellation under the overview header (#387)

**Decision.** `Constellation.tsx` draws the project's papers and notes as a 132 px sky under the overview header: nodes and links from `GET /projects/{slug}/graph/` (capped at 320 nodes by degree), a small in-file layout (sideways-only 1/d repulsion, a home height per star, loose link springs, soft walls — a full n² force layout piles a short band onto its edges), stars tinted with the project accent (unread ones fainter, notes teal), a slow drift and twinkle that stop under `prefers-reduced-motion` or a hidden tab, hover for the title, click to open the paper or note, and a caption with counts and a link to the graph page. Nothing renders when the project has fewer than two nodes.

**Why.** The overview is the page a visitor lingers on and the one that should look like the Observatory rather than a form. The data was already there (the graph endpoint) and a canvas needs no library, so the header gains a living picture of the project's literature for a few kilobytes — and it is honest: every dot is a real paper you can click.

**Alternatives rejected.** Reusing 3d-force-graph in the header (1.3 MB and WebGL for a decoration); a static SVG sparkline of counts (says nothing a number does not); running the layout on the server (the browser has the width, and the layout takes a few milliseconds).

### 2026-09-07 — Library: Find PDF from the row menu, with a result pill (#386)

**Decision.** The row's right-click menu carries **Find PDF** (disabled with a "needs a DOI" hint when the paper has neither DOI nor arXiv id, "PDF attached" when it already has one). While the lookup runs the row shows a "looking…" pill; afterwards a paper that still has no PDF shows a quiet "no PDF found" pill whose tooltip carries the server's outcome (`extra.oa_pdf`, written by `fetch_and_attach_pdf`) and the hint to retry.

**Why.** The lookup existed only in the detail pane and left no trace on a miss, so the same paper got tried again and again. A pill per row answers "did I already look?" at a glance without a new field — the outcome was already stored.

**Alternatives rejected.** A "last checked" facet in the rail (a filter for a state you mostly want to see inline); auto-retrying misses on a schedule (network calls the owner did not ask for).

### 2026-09-07 — The last CDN loads are vendored: htmx and Alpine (#385)

**Decision.** `templates/base.html` loads htmx 2.0.4 and Alpine 3.14.9 from `static/vendor/` instead of unpkg; `core/tests/test_no_cdn.py` fails on any unpkg/jsdelivr/cdnjs/esm.sh URL in the templates or the SPA sources, and checks the two files are present.

**Why.** The desktop app must work with no internet. The graph libraries and pdf.js were vendored earlier for the same reason; these two were the last runtime loads from the network, and every classic page (login included) pulled them. 95 KB of static beats a page that half-works offline.

**Alternatives rejected.** Keeping the CDN with a local fallback (`onerror` swap — two code paths for one file); an npm build for the classic shell (the SPA already has one, the classic pages do not need it).

### 2026-09-07 — ETag honesty: a data version in every ETag, M2M writes touch updated_at, and a guard on bare update() (#384)

**Decision.** Three layers. (1) `core/versioning.py` keeps a process-wide data version in the cache; `core/signals.py` bumps it on every save, delete and M2M change of an Atlas model, and every list/detail ETag in `AtlasViewSet` folds it in. (2) The same M2M receiver stamps `updated_at` on the instance and on the related rows, since Django's `add/remove/set/clear` never touch it. (3) `core/tests/test_etag_honesty.py` walks the app code with `ast` and fails on any queryset `.update(...)` that neither passes `updated_at` nor carries an `# etag: ok` reason; the sites it found (a highlight marking papers skimmed, moving documents, inbox bulk triage, merge bookkeeping, the main-file switch) now stamp `updated_at`, and two lines that run right before a delete or a save are marked.

**Why.** The stale-304 bug shipped twice in one day (#381 tags, #383 reorder) and the survey found five more places waiting to do it. `updated_at` stays the primary signal (it is exact across processes), the version closes the gaps in-process (which is the whole desktop), and the guard stops the next one at test time rather than in the owner's hands.

**Alternatives rejected.** Dropping ETags from the API (MCP polling and the SPA's cache would pay every time); computing ETags from the serialised body (a full render per request just to say 304); a Django middleware that clears the browser cache on writes (cannot see M2M or `update()` either).

### 2026-09-07 — Today list: drag to reorder through one endpoint (#383)

**Decision.** `POST /api/v1/todos/reorder/ {"ids": [...]}` sets the whole order — the given ids take positions 1..n, everything else follows in its current order — and bumps `updated_at` so the list ETag moves. The Today page drags rows by a grip that appears on hover (HTML5 drag & drop, an insertion line above/below the target, optimistic update), and the existing ⌥↑/↓ keyboard reorder now goes through the same call instead of two swapped PATCHes. `reorder_todos` is the MCP tool (90 tools).

**Why.** The list is meant to be reordered by feel, and a swap-only API cannot express "drop it third". One endpoint carrying the full order is the smallest contract that both the mouse and Claude can use, and the optimistic update keeps the row under the cursor. The first Playwright run showed the API reordered but the page did not: `update()` had left `updated_at` alone, the list ETag stayed put, and the browser handed back the old order (the tag bug of #381 again) — the endpoint now stamps `updated_at`, and the test asserts the ETag changes.

**Alternatives rejected.** A drag library (dnd-kit adds a dependency for one list); fractional positions (no re-numbering, but every reorder still writes and the numbers drift); PATCHing each item's position from the client (n requests for one drop).

### 2026-09-07 — A blank window can never be silent: boot watchdog, error boundaries, client-error log; static re-collected clean per version (#382)

**Decision.** The owner reported that 0.1.106 — the build carrying the #379 hotfix — still shows only the background. Two things ship. (1) **Every front-end failure now says so on screen and in the log.** `spa.html` carries an inline boot watchdog: if `#root` is still empty eight seconds in, it draws a plain panel ("Atlas couldn't draw the app") with the errors captured by `window.onerror`/`unhandledrejection`/the script tag's `onerror`, Reload / Copy report / classic-pages buttons and the server-log path, and posts the report to `POST /api/v1/client-errors/`. A React `ErrorBoundary` wraps the whole tree (scope `app`) and the page outlet (scope `page`, reset on navigation) with the same report; every report is logged by `core.client_errors` (→ `atlas-server.log` on the desktop) and kept for the Diagnostics report ("Front-end errors", also in the paste-able text). (2) **The desktop re-collects static assets with `--clear` on a version change and serves them with `WHITENOISE_MAX_AGE = 0`.** Without `--clear`, `collectstatic` keeps any collected file whose mtime is not older than the source's; an installer that preserves build timestamps can therefore leave the previous build's `spa.js`/chunks in the data dir, and a half-updated module graph fails to evaluate — which is exactly a blank window with the background drawn. Chunk names carry no content hash, so the web view's own cache must revalidate too.

**Why.** The SPA boots cleanly here under the desktop settings (SQLite, DEBUG off, WhiteNoise, empty and seeded) and under a fresh PyInstaller freeze, with a Tauri stub — so what is left is the owner's machine: WebView2, the real IPC, their data, and the update path. Reasoning cannot close that gap; evidence can. The watchdog turns the next report into the actual error text, and the clean re-collect removes the one failure mode that only ever happens on an upgraded install (never in CI, never in a fresh Playwright run).

**Alternatives rejected.** Waiting for a console (the release web view has none); a desktop-side dev-tools toggle (helps me, not the owner, and ships a debugging surface); content-hashed chunk names (a bigger change to the Vite/collectstatic contract than `--clear` + revalidation, and it would not have surfaced the error either).

### 2026-09-07 — Library tag colours, rename and delete from the rail; tag changes move the list ETag (#381)

**Decision.** A tag's colour (the model had the field since slice 5) is now chosen from the rail: right-click a tag → eight swatches, "No colour", **Rename…** and **Delete tag…** (in-app dialogs). Chips on the rows, in the detail pane and on the duplicate cards carry a tint plus a dot in that colour, so a tag reads the same everywhere. `PATCH /library-tags/{id}/` validates `#rrggbb` (or blank) and keeps case-insensitive uniqueness on rename; the facets carry each tag's `id`.

**Why.** The rail already painted the tag icon with the colour nobody could set. Colour on a tag is the cheapest way to make a long list scannable ("everything rose is methods"), and rename/delete were the last tag operations without a place in the UI. While verifying, the rows kept showing a stale tag set: tagging is an M2M change that never moves `updated_at`, and the list ETag (#11-adjacent conditional GETs) is built from it, so the SPA got 304s after every tag/untag and after a rename or delete. `literature.library.touch_references` now bumps the affected rows in `bulk` and in the tag viewset's update/destroy — the same "keep updated_at honest" rule the hypothesis/evidence and manuscript viewsets already follow. Regression test in `test_tags_views`.

**Alternatives rejected.** A free colour picker (eight calm swatches fit the palette and a menu; a wheel needs a dialog and produces greens nobody can read on); folding the tag table's max `updated_at` into the reference list ETag (works for rename/delete but not for tag/untag, and splits the ETag rule); dropping the ETag on the reference list (MCP polling would lose its cheap 304s).

### 2026-09-07 — The dashboard hero carries the top of your list and your rank (#380)

**Decision.** `GET /api/v1/dashboard/` now includes `todos` (the first four open Today items in list order); the hero renders them with a tick box that completes in place and a "n more on today's list" link. A small chip next to the counts shows the achievement rank and score (red in souls mode) and opens the ledger.

**Why.** The dashboard answers "what should I work on today?"; the Today list *is* that answer for the small stuff, and it lived one click away. The rank chip is the only place the achievements surface outside their own pages — one glance, never a nag.

**Alternatives rejected.** A whole Today panel on the dashboard (duplicates the page); pushing the rank into the sidebar pet widget (already the busiest 60 px in the app).

### 2026-09-07 — Hotfix: a hook below an early return blanked the app; a static rules-of-hooks guard (#379)

**Decision.** The dashboard's warm-up hooks (#372) were added below the loading/error returns; once data arrived the hook count changed, React threw #310 and every page mounted under the dashboard route went blank — the owner's "the new update isn't even showing anything" (builds 0.1.99–0.1.104). Both offenders (Dashboard, and a latent one on Today) are fixed, and `core/tests/test_hook_order.py` now walks every component and fails on any hook call after a top-level early return, since the repo has no eslint.

**Why.** The UI audit passed the night before because the bug landed after it ran, and the desktop stub was the first thing to load `/` afterwards. A static guard costs nothing and catches the whole class; it is the cheapest possible replacement for `eslint-plugin-react-hooks` without adding Node tooling to CI.

**Alternatives rejected.** Adding eslint to the build (a Node toolchain in CI for one rule); an error boundary that hides the blank page (it would show a message, but the page would still be broken).

### 2026-09-07 — SyncTeX in the studio (#378)

**Decision.** Tectonic runs with `--synctex`; `writing/synctex.py` folds the `.synctex.gz` records into one rectangle per (page, file, line) in PDF points, stored as `Manuscript.synctex` on a good compile (cleared on failure) and served by `GET /manuscripts/{id}/synctex/`. In the studio, **Locate** (⌘⇧J) scrolls the PDF to the cursor's line and flashes a bar there; **double-click** anywhere in the PDF opens the matching file and line. The inverse lookup prefers the smallest box containing the point (page and paragraph boxes contain everything).

**Why.** Backlog idea #33 and the "better than Overleaf" bar: jumping between the rendered page and the source is what makes a two-pane editor feel like one document. The compact map (one rectangle per line) keeps the payload small enough to fetch once per compile.

**Alternatives rejected.** Server-side lookups per click (a round-trip for every jump); storing the raw synctex file (megabytes, and the parsing would move to every client).

### 2026-09-07 — Studio to-do panel (#377)

**Decision.** The studio's Outline tab lists every `% TODO …`, `% FIXME …`, `% XXX`, `% HACK` and `\todo{…}` marker across all source files (each loaded once into the editor's state map), with click-to-line across files and a count in the tab label. The demo manuscript ships two markers.

**Why.** Owner idea #9 ("better than Overleaf") — a writer's own reminders live in the source; every editor that people love surfaces them. Comments are the Overleaf feature for teams; for one researcher the marker list is the honest equivalent.

**Alternatives rejected.** A separate Tasks tab (one more tab for a list that belongs beside the outline); parsing only the open file (the whole point is "what is left, anywhere").

### 2026-09-07 — Restore from a backup is staged, then applied at launch (#376)

**Decision.** A backup zip uploaded on Diagnostics (`POST /api/v1/restore/`) is validated (manifest, a database inside, no path traversal) and saved as `restore-pending.zip` in the data folder; the desktop launcher applies it at the next start, *before* `migrate` opens the database: the SQLite file (with its WAL/journal) and the media folder move to `restore-backup-<timestamp>/`, the backup's copies come in, and `restore-result.json` records the outcome, which Diagnostics shows. The page offers "Restart Atlas and restore now" on the desktop and "Cancel". `manage.py restore_backup <zip>` stages + applies for servers (JSON backups extract `restore-database.json` for `loaddata`).

**Why.** A backup nobody can restore is a screenshot. Swapping a live SQLite file under an open Django connection is not safe, and the desktop has exactly one moment when nothing is open — launch. Keeping the previous data beside the restored one makes the operation reversible by hand.

**Alternatives rejected.** Restoring in-process by closing connections (waitress threads may hold others; a half-restore is worse than none); `loaddata` into the live database (merges by primary key — surprising duplicates and dangling files).

### 2026-09-07 — Achievements: a derived ledger with a souls tier (#374)

**Decision.** `core/achievements.py` holds a catalogue of 57 achievements as predicates over one `facts` dict gathered from the database (papers, notes, milestones, submissions, hypotheses, streaks, activity hours…), each with a progress (current/target) and a tier: fun (5 pts, several hidden), steady (10), hard (25), souls (50 — "You died", "Git gud", "Boss slain: Reviewer 2", "No-hit run", "Bonfire lit", "Hollowed, returned", "Praise the sun", "New game+", "The abyss"). Only the first-unlock moment is stored (`AchievementUnlock`); everything else is recomputed and cached with the pet state. Score → rank (Undergrad … Ashen One). `/achievements` page with tier filters and the five closest; toast on a fresh unlock; `GET /api/v1/achievements/`; MCP `get_achievements` (89 tools). **Souls mode** is a stored flag on the pet: same facts, grim lines ("{deaths} deaths. Each one taught you something. Rise."), counters, and a YOU DIED / BONFIRE LIT flash in the studio.

**Why.** The owner asked for "a lot of achievements, some just for fun, some really hard, souls game mode on research". Deriving them from real work keeps the no-guilt design of the pet: nothing to grind, nothing nags — the ledger only names what already happened, and the souls tier turns the worst days of research (rejections, contradictions, failed builds) into something you can wear.

**Alternatives rejected.** Event-sourced achievements (a new table written from every view; brittle and it would miss data created through the API/MCP); per-project achievements (the ledger is about the researcher, not one project); a separate difficulty setting (souls mode is tone — the data is the data).

### 2026-09-07 — The app icon is rendered, not drawn (#373)

**Decision.** `scripts/make_icon.py` renders the Observatory mark — a navy rounded square with an aurora glow, a tilted orbit ring and a bright star — as a 1024² PNG from signed-distance fields in pure Python (no Pillow, no ImageMagick, no design file to lose); `tauri icon` turns it into every platform size, committed under `desktop/icons/`. The desktop server runs eight waitress threads and no longer logs queue-depth notices.

**Why.** The installed app showed the Tauri placeholder — a flat indigo square — which the owner rightly called "not a proper icon". A script keeps the mark reproducible and editable without a designer's tool, and the same identity carries into the product name work later (the mark is abstract on purpose: it survives a rename).

**Alternatives rejected.** A hand-made PNG in the repo (unreproducible); an SVG through a rasteriser (none available in the build environment; the CI runners would need one too).

### 2026-09-07 — LaTeX warm-up: know the bundle cache is cold, fill it on purpose (#372)

**Decision.** `writing/warmup.py` finds Tectonic's cache directory per platform, reports warm/cold + size, and can compile a small document that pulls the common packages (amsmath, graphicx, hyperref, natbib, booktabs, xcolor, geometry) on a daemon thread, with the state in the Django cache. Diagnostics shows a *TeX bundle* row with **Warm up now** and polls while it runs; the report text and `get_diagnostics` carry it.

**Why.** The owner's "latex didn't compile" was, in part, a first compile silently downloading the bundle for minutes. A cold cache is now a visible fact with a button, not a surprise behind "Compiling…".

**Alternatives rejected.** Shipping the bundle in the installer (hundreds of MB for packages most papers never use); warming automatically on first launch (an unasked-for download on a metered connection).

### 2026-09-06 — ⌘K: `todo:` verb and recent jumps (#371)

**Decision.** The palette understands `todo: <text>` (also `t:`) and adds it to the Today list, tagged with the project you are in; navigations made through the palette are remembered per browser (`atlas-recent-jumps`, six entries) and shown as "Recent jumps" above the server's "Recently edited" list when the query is empty.

**Why.** The two things a researcher does most from the keyboard are "note this for later" and "back to where I was". Both were one hop too far: capture went to the inbox for triage, and the empty palette only knew what changed in the data, not where *you* had been.

**Alternatives rejected.** Persisting jumps server-side (a per-browser convenience, not data); a generic "Add to list" verb that prompts (typing `todo:` is faster and consistent with the inbox's own prefixes).

### 2026-09-06 — Updater polish: progress, notes, re-check (#370)

**Decision.** `install_update` emits `update-progress {downloaded, total, done}` from the download callback; the sidebar control shows a percent bar (or MB when the feed sends no length), then "Installing…". Clicking "Update to x" first shows the release notes from the feed in a confirm dialog. The silent check repeats every six hours while the window is open. Backlog #304 done; a public feed (#347) is still the owner's step.

**Why.** A multi-minute download with a spinner is indistinguishable from a hang — the thing the owner keeps reporting. Notes before installing are basic courtesy; the periodic check means a laptop left open still learns about a fix shipped that day.

**Alternatives rejected.** A separate updates page (the sidebar control is where the state already lives); auto-install without asking (a restart in the middle of writing is not calm).

### 2026-09-06 — Connect page: a live connection test that launches the real MCP command (#369)

**Decision.** `POST /api/v1/connect/test/` runs four checks server-side (API key set; API answers that key at the URL in the command; the exact MCP command with `--check` starts and reaches the API; `claude` on PATH), each with a fix line. The MCP server gained `--check`: it lists projects through the API and counts its tools, printing one JSON line. Backlog #290 done.

**Why.** "Is it connected?" had no answer inside the app. Running the very command Claude Code will run is the only test that cannot lie — and it immediately caught a real bug: `python -m mcp_server.server` registered 29 of 88 tools because the `__main__` block sat mid-file (the frozen `atlas-mcp` imported the module and was unaffected). The block now ends the file and a test pins that.

**Alternatives rejected.** A browser-side fetch to the API (proves nothing about the MCP process); spawning an MCP client over stdio (heavy; `--check` covers the same wiring).

### 2026-09-06 — Desktop hands stored files to the operating system (#368)

**Decision.** In desktop mode the workspace tree carries `local_path` for every stored file; the Files menu offers **Open with the system app** and **Show in folder**, backed by two Tauri commands (`open_path`, `reveal_path`) that accept only an existing regular file. Servers never report local paths.

**Why.** A researcher's files are used by other programs — a CSV in R, a figure in Illustrator, a PDF in the reader they already know. Downloading a copy from a local app is absurd; the file is right there. This is the desktop half of "contain any file from disk" (#30).

**Alternatives rejected.** The Tauri opener plugin (another permission surface for two commands); reporting local paths everywhere (leaks server layout for no gain).

### 2026-09-06 — Compiles never run inside the request (#367)

**Decision.** `writing/tasks.enqueue_compile` queues the huey task on server installs and, in *immediate* mode (desktop, Redis-less dev), runs the compile on a daemon thread that closes its DB connection when done. Both compile views call it.

**Why.** Immediate-mode huey executes the task inline inside the HTTP request, so on the desktop the click on Compile held the request for the whole run — a first Tectonic run downloads its bundle for minutes — and the studio's "stalled compile" hint could not tell that apart from a hang. The studio polls compile-status anyway; nothing needed the synchronous result.

**Alternatives rejected.** A real huey consumer thread in the desktop process (more moving parts for one long task); making compile synchronous with a short timeout (the first run is legitimately slow).

### 2026-09-06 — CRUD everywhere: in-app dialogs, context menus, every object editable and deletable in the SPA (#364)

**Decision.** Three owner reports in one evening ("I made a project to test, now I can't delete it", "left click doesn't have much functionality", "CRUD is missing from the whole project") were the same defect: the SPA had migrated the *reading* of most objects but not their editing. This slice closes it as a rule, not a patch:
- `components/Dialog.tsx` — `confirmDialog` / `promptDialog` / `noticeDialog` / `errorDialog` with one `<DialogHost />` at the root. No page may call `window.prompt/confirm/alert` again (guarded by `core/tests/test_crud_everywhere.py`): the desktop webview can swallow native dialogs, which is why "+ Folder" looked dead. Destructive confirms are red; the ones that erase a lot (project, manuscript) require typing the name.
- `components/Menu.tsx` — `useMenu()` (right-click) and `<Kebab />` (the ⋯ every row carries) share one popup with keyboard navigation. Pages declare actions as data, so right-click, ⋯ and the detail pane all offer the same list.
- Coverage: project settings + archive + delete (overview, card menus); Files (file: open/new tab/download/copy path/rename/delete; folder: new folder inside/upload here/rename/delete; blank: new folder/upload/refresh; F2/Del; drop onto a folder uploads into it); decisions edit/delete + dated; figures rename/delete; prompts create/edit/delete; literature priority/status/remove-from-project + Add papers; reference metadata editor + delete; research: hypothesis edit, experiments edit/delete, datasets rename/location/version/delete, **research questions panel** (the object nothing in the app could create); plan: add/rename/delete phase; manuscripts delete (typed title) + shelve.
- Failed writes surface as an error dialog with the server's text instead of vanishing.

**Why.** §1 "a place for everything" includes the way out: an object you cannot rename or delete is clutter you are stuck with. One dialog and one menu component keep the answer to "how do I change this?" identical on every page.

**Alternatives rejected.** Per-page modals (twelve styles of the same question); sending people to the classic UI or the admin for deletes (the front door is the SPA now, #342); native dialogs with a desktop-only polyfill (the desktop is the primary target).

### 2026-09-06 — Django serves `/media/` in every settings module (#365)

**Decision.** `config/urls.py` routes `media/<path>` to `django.views.static.serve` unconditionally (behind the login middleware) instead of the `static()` helper that only works with `DEBUG=True`.

**Why.** Owner report: the studio's PDF pane said *Missing PDF* for `/media/manuscripts/pdf/manuscript-1.pdf`. Desktop settings run with `DEBUG=False` and no reverse proxy, so nothing served uploads at all — every compiled PDF, attached paper and figure 404'd in the installed app. A single-user app has no proxy to hand this to.

**Alternatives rejected.** Whitenoise-style media (wrong tool; media is per-user data); an API endpoint per file type (the URLs are already in the models' `FileField.url`).

### 2026-09-06 — `open_local_file` is an async Tauri command and returns bytes (#366)

**Decision.** The desktop file picker command is `async fn`, receives the pick through a channel and returns `{path, name, size, content?, data_b64}`; Files shows a text preview when the file is UTF-8, says "binary" otherwise, and offers **Add to this project** (into any folder) which uploads the bytes through the normal upload endpoint.

**Why.** Owner: "open from disk not working". A `blocking_pick_file` inside a synchronous command runs on the main thread — exactly where the dialog plugin documents it must not — so the picker never opened. Returning the bytes turns a viewer into the missing "bring a file in" path.

**Alternatives rejected.** The fs plugin with a scoped allowlist (broader surface than one user-picked file); text-only as before (PDFs and images are the common case).

### 2026-09-06 — One-file backup (#363)

**Decision.** `GET /api/v1/backup.zip` (`core/backup.py`) downloads a zip with a transactionally consistent copy of the SQLite database (both a byte-exact `atlas.sqlite3` for copy-it-back restores and a `database.sql` dump), or a `database.json` `dumpdata` on other databases, plus the whole media folder, a `MANIFEST.json` and a `README.txt` with the restore steps. The Diagnostics page has the **Download a backup** button.

**Why.** A single-user desktop app holding years of reading and writing needs one obvious way to take it all somewhere else; the data folder is knowable (Diagnostics shows it) but a zip is what people actually keep.

### 2026-09-06 — Connect page shows what is installed on this machine (#362)

**Decision.** `core/tooling.detect_tools` looks up `claude`, `node`, `git` on PATH (plus the LaTeX engine through the resolver) with a guarded `--version`, and `GET /api/v1/connect/` carries the result; the Connect page shows a chip per tool and, when Claude Code is missing, the install line. The terminal dock's **Claude** tab depends on `claude` being on PATH — now the page says so before the tab prints "command not found".

### 2026-09-06 — MCP: `get_diagnostics` and `suggest_review_themes` (88 tools, #361)

**Decision.** Claude can read the same diagnostics report as the app (with an optional network probe) and propose matrix columns from the papers. The daily skill points at `get_diagnostics` for "why didn't it work" questions; the literature skill uses `suggest_review_themes` before `add_review_theme`.

### 2026-09-06 — The calendar feed is finally served (#360)

**Finding.** `core/calendar.py` has built valid `.ics` for months (Backlog #9) and nothing served it — the tests were the only caller.

**Decision.** `GET /api/v1/calendar.ics` returns one VCALENDAR of every non-archived project's milestones and manuscript deadlines (`?project=<slug>` narrows). Calendar apps cannot send headers, so a `QueryKeyAuthentication` accepts `?key=<api key>` on this endpoint only; the session and the header still work. The dashboard's Deadlines card has a **subscribe (.ics)** button that copies the URL — with the key in it, which the tooltip says plainly.

### 2026-09-06 — Figures into the manuscript (#359)

**Decision.** In the studio's Files panel every image asset gets an ⊕ that inserts a `figure` environment (`\includegraphics[width=\linewidth]{path}`, caption, `fig:` label) at the cursor, and a **Project figures** list shows the project's image documents: one click copies the file into the manuscript as `figures/<name>` through the existing upload endpoint and inserts the environment. `seed_demo` now includes a small PNG figure so the gallery and the studio have one to show.

**Why.** Figures lived in the Figures page and manuscripts lived in the studio; moving a plot between them meant a download, an upload and typing the environment by hand.

### 2026-09-06 — Notes editor v2: CodeMirror Markdown (#358)

**Decision.** The note body is a CodeMirror 6 editor (`frontend/src/app/notes/MarkdownEditor.tsx`, `@codemirror/lang-markdown` added): Markdown highlighting (headings, emphasis, links, code, quotes), `[[` note-link and `@` cite completions from `/notes/suggest/` (with the "new note" option preserved), ⌘B / ⌘I / ⌘K formatting, ⌘S save, find, history, line wrapping, and a CSS-variable palette (`.md-editor`) for both looks. The hand-rolled textarea autocomplete (regex on `selectionStart`, own popover, own key handling) is gone; the preview, autosave and link panel are untouched.

**Why.** Notes are written every day; a textarea with a bolted-on popover is not a writing surface, and the studio already proved the CodeMirror core. One editor engine now serves LaTeX and Markdown.

**Alternatives.** A WYSIWYG editor (rejected: `[[links]]` and `@keys` are the point; Markdown stays visible and portable); keeping the textarea and adding shortcuts (rejected: no highlighting, no proper completion UI).

### 2026-09-06 — CI boots the frozen server before an installer ships (#357)

**Decision.** The release workflow now runs the PyInstaller output on each target OS: `--setup-only` (migrate, collect static, create the login), then serve on a spare port, fetch the login page, call `/api/v1/diagnostics/` with the minted key and require the bundled Tectonic path in the answer, and fetch the SPA bundle — printing the server log on failure. A scaffold test pins the step and its order.

**Why.** Every owner report today was a defect that existed only in the installed build (no engine, ACL, links, first run). The suite runs the Django code, not the frozen artifact; this step runs the artifact.

### 2026-09-06 — Today v2 and matrix theme suggestions (#356)

**Decision.** Today gets a keyboard (`j`/`k`, space ticks, `e` edits inline, `x` deletes, `⌥↑/↓` reorders through `position`, `n` focuses the input), inline editing by double-click, an amber "since Tue / N days old" chip on items carried over from earlier days, and project chips that link to the project. The review matrix gains **Suggest themes**: `literature/matrix.suggest_themes` runs the existing keyword extractor over each paper's title and abstract and ranks phrases by how many papers mention them, skipping themes that already exist (`GET /projects/{slug}/review-matrix/suggest/`); each chip adds a column.

**Why.** The Today list is used dozens of times a day, so every mouse trip counts, and old items should look old. Matrix columns were typed from memory; the papers already know their themes.

### 2026-09-06 — Exact highlight marks (#355)

**Decision.** A highlight now stores the selection's line boxes as fractions of the page (`Highlight.rects`, migration 0008; validated to at most 200 boxes in 0..1). The reader captures them from the selection's client rects at save time and paints them in an `.hl-layer` between the canvas and the text layer, so marks look like a real PDF viewer's, survive zoom, and no longer depend on matching span text; highlights without boxes (older ones, MCP-created ones) keep the text-match painter. The API's `perform_create` passes the boxes through the `add_highlight` service — the first browser check caught that it silently dropped them.

### 2026-09-06 — Diagnostics page (#354)

**Decision.** `GET /api/v1/diagnostics/` (`core/diagnostics.py`) gathers version, platform, data folder, database, LaTeX engine path, job mode, API-key state, the updater endpoints (probed only with `?network=1`), the last failed compile's log and the tail of the desktop server log, plus a plain-text rendering. `pages/Diagnostics.tsx` at `/diagnostics` shows it with pass/fail marks and a **Copy report** button; the Connect page and the sidebar's "Updates unavailable — why?" link there.

**Why.** Three of today's owner reports ("didn't compile", "check for update failed", "not allowed by ACL") took a round-trip each to understand. One paste should carry the answer.

### 2026-09-06 — Compile hardening for the desktop (#353)

**Finding.** The owner: "the latex didn't compile". The Windows installer does carry `tectonic.exe` (verified in the run 75 job log: 50 MB in `bin/`), so the likely killers were the 180 s compile timeout — Tectonic's first run fetches the TeX bundle over the network, which takes minutes — and, before the ACL fix, nothing in the shell working at all.

**Decision.** `COMPILE_TIMEOUT` is 900 s with a message that says what the wait is; `tectonic_path()` also looks next to the frozen executable (`_MEIPASS/bin`, `<exe>/bin`, `<exe>/_internal/bin`); the engine path is the first line of every compile log so a failure names the binary it used; on Windows the subprocess runs with `CREATE_NO_WINDOW` so no console flashes behind the app, and output is decoded as UTF-8 with replacement.

### 2026-09-06 — Desktop commands were refused by the ACL (#353)

**Finding.** The owner: "shell couldn't start — command terminal_spawn not allowed by ACL". The desktop webview loads the bundled server at `http://127.0.0.1:<port>`. Tauri 2 treats any http origin as *remote*, and a capability applies to remote origins only when it names them under `remote.urls`. Ours did not, so the window matched no capability and **every** command was refused — the terminal, the updater's check and install, the native file picker, and the new external-link opener. The earlier in-browser checks could not catch this because the browser has no Tauri IPC at all.

**Decision.** `desktop/capabilities/default.json` now declares `remote.urls` for `http://127.0.0.1:*` and `http://localhost:*` (any port: the shell picks a free one), guarded by a scaffold test. The updater button explains an ACL refusal on older builds and points to a one-time reinstall. This also means "check for update failed" on the installed build was this refusal first and the private-repo 404 second; both are now handled.

**Alternatives.** Serving the app through Tauri's custom protocol instead of http (rejected: the bundled Django server is the single source of truth and the browser build must stay identical); per-command permissions (not needed: application commands are allowed once a capability matches the origin).

### 2026-09-06 — Outbound links in the desktop app (#352)

**Finding.** The owner: "the button to get it manually failed". The Tauri shell only navigates within the local Atlas origin (a deliberate hardening), so every outbound link in the desktop app — the releases page, DOIs, API docs, "Open ↗" on a PDF host — silently did nothing.

**Decision.** A `open_external` command in the shell hands http(s)/mailto URLs to the operating system's browser (`cmd /C start`, `open`, `xdg-open`; everything else is refused, unit-tested), and the app installs one capturing click handler that routes any off-origin anchor through it (`frontend/src/app/external.ts`). In a normal browser nothing changes. The updater's "get it manually" uses it directly.

**Alternatives.** Widening `on_navigation` to allow any https host (rejected: the window would leave the app; the hardening exists so a compromised page cannot steer it); the tauri-plugin-opener crate (rejected for now: same result with zero new dependencies and no new capability grants).

### 2026-09-06 — First run on the desktop: login hint, welcome panel, demo loader, doctor (#351)

**Finding.** A fresh install (verified against an empty desktop-settings instance) showed a login form with no hint that the bundled login is `atlas / atlas`, then a dashboard saying "All clear, everywhere" with zero projects. `seed_demo` also could not be re-run: deleting a project with a manuscript re-created the manuscript's mirror folder mid-cascade (the `ManuscriptFile` post-delete signal re-synced while the parents were still inside the collector's transaction), leaving an orphan folder and a foreign-key error at commit.

**Decision.** (1) The login page shows the default credentials only on desktop builds and only while that password still works (`ATLAS_DESKTOP` setting, `default_login_still_active`). (2) With zero projects the dashboard opens a Welcome panel: create a project, **Load the demo project** (`POST /api/v1/demo/`, idempotent), connect Claude Code. (3) The mirror signal ignores cascade deletes (Django's `origin` argument) so projects delete cleanly and the demo reloads. (4) `manage.py doctor` finds Tectonic through the engine resolver and checks the update feed, naming the private-repo 404.

**Alternatives.** Auto-login on the desktop (rejected for now: the login is the only lock on a shared machine; a hint is enough); seeding the demo automatically on first launch (rejected: an empty Atlas is the right start for a real project — the offer is one click away).

### 2026-09-06 — Inbox keyboard triage and matrix CSV (#350)

**Decision.** The Inbox gets a cursor: `j`/`k` (or arrows) move it, `Enter` converts with the suggested target, `1`–`5` pick paper / today / note / milestone / decision, `f` files under the project, `x` dismisses, `?` shows the legend; keys are ignored while typing in the capture box, and hovering a row moves the cursor so mouse and keyboard agree. The review matrix gains a **CSV** export (key, title, year, one column per theme with the extracted finding or an `x`) built client-side from the table the page already holds.

**Why.** Triage is a batch activity; the mouse round-trip per capture was the slowest part of inbox zero. The CSV is what co-authors and R scripts ask for when a matrix leaves Atlas.

**Alternatives.** A server-side CSV endpoint (rejected: the page already has the full table; one less route in the schema); vim-style `d` for dismiss (rejected: `x` reads as "close" to everyone).

### 2026-09-06 — Quotes from highlights into the manuscript (#349)

**Decision.** The studio's Bibliography panel opens each cited paper (✎) to the passages the owner highlighted while reading; one click inserts them at the cursor as a `quote` environment with `\citep{key}` and the page (`quoteLatex`). The Library's highlight cards gain a **quote** action that copies the same thing as inline LaTeX, and `/manuscripts/:id/editor?quote=<highlight id>` inserts a specific highlight on open (the deep link the Library and MCP can hand out). No new backend: highlights already carry text, page and paper.

**Why.** Reading and writing were two rooms; the passage you marked on page 3 should be one click from the paragraph that needs it. This is the "quotes into manuscripts" item from the Library second-pass list.

**Alternatives.** A separate "Quotes" tab (rejected: the bibliography already lists exactly the papers that may be quoted); storing quotes as their own objects (rejected: a highlight *is* the quote — duplicating it would drift).

### 2026-09-06 — Library health and protocols move into the app (#348)

**Decision.** The bib report becomes `pages/Report.tsx` at `/projects/:slug/report`: the four checkers as cards with levels, `@key` links to each paper, a **Merge into first** action on duplicate findings (`POST /references/merge/`), and network checks (doi.org / Crossref) behind an explicit toggle so the page opens instantly. Protocols are written, read and re-versioned inside the Research page (`ProtocolPanel`: create v1, open, "new version" → `POST /protocols/{id}/new-version/`). Both classic pages keep working; the report URL maps to the app.

**Why.** After #342 every remaining classic link is a small betrayal of the "one front door" promise; these were the last two the SPA still pointed at.

**Alternatives.** Auto-merging duplicates (rejected: the checker's fuzzy title match needs a human "yes"); a modal editor for protocols (rejected: inline keeps the page calm and the version chain visible).

### 2026-09-06 — Auto-update: a private repo cannot feed the updater (#347)

**Finding.** The owner added `TAURI_SIGNING_PRIVATE_KEY`; every release since 0.1.67 carries `.sig` files and `latest.json`, so the signing half works. But the repository is private, and the Tauri updater fetches `https://github.com/<repo>/releases/download/desktop-preview/latest.json` without credentials — GitHub answers 404 (verified with curl). The launch-time check swallowed the error, so the app looked fine and simply never updated.

**Decision.** (1) The workflow gains a `mirror` job: after both platforms upload, it copies this build's installers, signatures and a URL-rewritten `latest.json` into a public releases repository named by the `RELEASES_REPO` secret using `RELEASES_TOKEN`, replacing older versions; without the secrets it emits a warning and exits cleanly. (2) The app's updater endpoints list the public feed first (`alizareh-coe/atlas-releases`) and this repo second, so either "create the public feed" or "make the repo public" fixes updates without a rebuild. (3) `UpdaterButton` no longer hides launch-check failures: it shows *Updates unavailable — why?* with a plain-language explanation (404 → private repo; signature mismatch → reinstall; network). (4) README gains an *Auto-update* section with the two owner actions.

**Alternatives.** Embedding a GitHub token in the app (rejected: anyone with the binary could read the repo); proxying the feed through the local Atlas server with a user-entered token (rejected: more moving parts than a public feed, and still needs a token per machine); asking the owner to make the repo public without a fallback (rejected: their call — both paths are wired).

### 2026-09-06 — UI audit pass 1: every page swept, the flaws fixed (#346)

**Decision.** A Playwright sweep of all 30 SPA routes (dark, 1440 px) checked horizontal overflow, sub-10 px text, empty bodies, console errors and redirects, and every screenshot was reviewed by eye. Findings and fixes: the Projects index leaked raw Markdown and said nothing about progress → rewritten (`pages/Projects.tsx`: grouped by status with archived folded, cards with accent, phase, progress bar, health pill, counts; `ProjectSerializer.summary` feeds it in one request); `/projects/new` fired `GET /projects/new/plan/` 404s from the command bar → guarded; five links still pointed at classic pages that now redirect straight back to the same SPA page (Documents "folders & upload", Files "documents page", Literature "matrix & reports", Plan "classic page", Reference "classic") → replaced with the real in-app destinations (Files for uploads, the review matrix) or removed; the bib report keeps an explicit `?classic=1` link until it has an SPA twin. The rest of the pages (dashboard, library, notes, graph, timeline, files, figures, queue, reading flow, review, decisions, automations, prompts, today, inbox, search, writing, studio, pet) passed both the automated checks and the eye test. The last sidebar link into classic — Connect Claude Code — became an SPA page (`pages/Connect.tsx` at `/connect`, `GET /api/v1/connect/`, `POST /api/v1/connect/skills/`) with a desktop-only "Run it here" button that types the `claude mcp add` line into the terminal dock.

**Why.** The owner: "general UI has many flaws". The automated sweep found no layout breakage; the real flaws were content leaks (Markdown), dead-end links created by the one-front-door redirect (#342), and an index page that had never had a v2 pass.

**Alternatives.** A visual-regression suite (parked in the Backlog: worth it once the design settles); fixing links one by one as they are noticed (rejected: the sweep is cheap and repeatable — `scripts/ui_audit.py` runs it again in one command).

### 2026-09-06 — Mochi v2: a living companion, not an emoji (#345)

**Decision.** `frontend/src/app/pet/Creature.tsx` replaces the 26 px static SVG: one layered owl whose pupils follow the cursor (CSS variables set from a single mousemove listener; it glances around by itself when the mouse rests), blinks, breathes, twitches its tufts, flaps when thriving, sleeps with a drifting *zzz*, and reacts to real events with squash-and-stretch hops, a confetti burst for milestones, hearts when poked, a *nom* for papers. Stages change the creature (egg with a crack and peeking eyes → hatchling with shell → scholar with round glasses → sage with cap, scarf and sparkles); all motion lives in `assets/css/app.css` (`.mochi`, reduced-motion aware). The sidebar shows it at 44 px and links to a new SPA page `/pet` (`pages/Pet.tsx`): big pokeable creature, speech line with local voice, this-week / streak / lifetime, the road to the next stage, four stats with the dominant one flagged, the feeding legend, and ten achievements. Backend: `core/pet.py` gains `streak_days`, `achievements`, `POINTS_LEGEND`, `rename_pet`; `GET /api/v1/pet/` returns them; `POST /api/v1/pet/` renames. The classic `/pet/` page redirects to the app (#342 map).

**Why.** The owner: "our pet is terrible man! it needs some real UI improvements, something that goes viral". A companion is only shareable if it feels alive — eye tracking and reactions are the whole trick — and only defensible in a research tool if every number comes from real work, which the existing points model already guaranteed.

**Alternatives.** Lottie/Rive animations (rejected: new dependency and binary assets; hand-authored SVG + CSS is 9 KB and themable); canvas physics (rejected: sidebar cost); a decaying "hunger" mechanic (rejected on the product's own rule: it never nags, sleeping means you rested too).

### 2026-09-06 — Terminal dock on every page + Atlas skills for Claude Code (#344)

**Decision.** The desktop terminal becomes a global **dock** (`frontend/src/app/TerminalDock.tsx`, mounted in the app layout): ⌃` toggles it anywhere, tabs hold independent shells, drag-to-resize and maximize, a **Claude** button opens a tab running `claude` (Atlas is already its MCP server). `desktop/src/terminal.rs` now manages many PTYs (ids on every output/exit event, `terminal_kill`), sets `TERM` and `ATLAS_DESKTOP`, and honours `ATLAS_SHELL`. The Files page's own terminal mount is replaced by the dock toggle. In a browser the dock explains that the shell lives in the desktop app. Four **skills** ship in `mcp_server/skills/` (`atlas-daily`, `atlas-literature`, `atlas-writing`, `atlas-plan`): tool-by-tool playbooks with safety conventions; the Connect Claude Code page lists them with install state and a one-click install into `~/.claude/skills/` (`core/skills.py`, `POST /connect/claude/skills/`). A test asserts every backticked tool in a skill is a real MCP tool.

**Why.** The owner asked for "cmd or terminal inside it just like VS Code" and noted that "claude might need some skills for this". The terminal existed but was buried inside one page and single-session; Claude had 86 tools and no idea which order to use them in.

**Alternatives.** A web-served terminal (rejected: arbitrary code execution over HTTP; the guard test forbids it); project-scoped skills in `.claude/skills` of a project folder (rejected: the user's projects are not git checkouts; personal skills follow the user everywhere); a single "atlas" mega-skill (rejected: Claude loads skills by description match, four focused ones trigger better).

### 2026-09-06 — The LaTeX studio moves into the app; desktop builds ship Tectonic (#343)

**Decision.** `frontend/src/app/pages/Studio.tsx` at `/manuscripts/:id/editor` is a full-window, VS-Code-shaped editor rendered outside the app layout: activity sidebar (Files with new/upload/rename/delete, Outline, Bibliography with click-to-cite and add-from-library, History with labelled snapshots, diffs and restore), a tabbed CodeMirror 6 editor built on the shared `frontend/src/editor` core (LaTeX grammar, snippets, `\cite{}` completion from the whole project library, live cite-check), a pdf.js preview with page navigation and zoom, a Problems panel wired to the compile diagnostics (click → file + line, deduplicated), autosave with a status bar (line, file, word count, missing cite keys, compile state, keymap), settings (Vim keymap, font size, spellcheck, compile-on-save), Quick Open (⌘P) over files and sections, and ⌘S / ⌘↩ / ⌘B / ⌘\ / ⌘J shortcuts. The CodeMirror theme and syntax colours read CSS variables from `.studio` so one theme serves Observatory and Paper. The classic editor page keeps working but browsers are redirected to the studio (#342 map). The workbench file list now bootstraps `main.tex` from `latex_source`, and `seed_demo` seeds a two-file manuscript with real cite keys, a table and an equation.

**Engine.** `writing/compile.py` resolves Tectonic from `ATLAS_TECTONIC`, then the bundled `bin/tectonic[.exe]`, then PATH, and fails with an actionable message. The release workflow downloads Tectonic 0.15.0 per platform into `bin/` before PyInstaller freezes the server (the spec bundles it), so Recompile works on an installed app — until now the desktop build had no engine at all and every compile failed. A compile that gets no answer for four minutes tells the user about `make worker` instead of spinning.

**Why.** The owner: "the latex editor is terrible … nothing close to real world standards". The old editor was the biggest exit into the classic UI, was light-only, cramped (72 vh preview) and could not compile on the desktop.

**Alternatives.** Porting the 1,000-line vanilla editor script as-is into a React shell (rejected: it was written around DOM ids and would keep two code paths alive); Monaco (rejected: 5 MB, no LaTeX grammar, and the CM6 core with codemirror-lang-latex was already there); bundling a full TeX Live (rejected: gigabytes; Tectonic downloads exactly the packages a document needs).

### 2026-09-06 — One front door: classic pages send browsers to the app (#342)

**Decision.** `core/ui_middleware.ClassicRedirectMiddleware` redirects a plain browser GET (Accept `text/html`, not HTMX, not XHR) for a classic trailing-slash page to its SPA twin, using `core/spa_routes.spa_equivalent` (mirrors `frontend/src/app/links.ts`; a test pins both). Escape hatches: `?classic=1` or entering through `/classic/` sets an `atlas_ui=classic` session cookie so classic stays browsable; every classic page now carries a banner whose "Back to the app" link (`?ui=app`) clears it. The sidebar's "← Classic Atlas" link is gone (it sat right under the theme toggle and was a one-misclick exit); classic is reachable from ⌘K ("Classic Atlas (old UI)") and by URL.

**Why.** The owner reported that the app "suddenly jumps back to the older UI and my todo list disappears". The SPA still exited into classic through the LaTeX editor button, the pet link, and any ⌘K / search row without an SPA mapping (references and manuscripts were unmapped) — and classic had no link back, and no Today page. One front door removes the whole class of bug instead of patching links one by one.

**Alternatives.** Patching every classic link in the SPA (rejected: the next unmapped URL brings the bug back); deleting the classic UI (rejected for now: the editor, pet page and connect page still live there — each becomes an SPA page in the following slices); redirecting the Django test client too (rejected: hundreds of classic view tests are scripts, not people; requiring an explicit `text/html` Accept keeps them meaningful and matches real navigations).

### 2026-09-06 — Research v2 slice 1: the hypothesis ledger (#341)

**Decision.** The research viewsets (hypotheses, experiments, datasets) become writable, and evidence gets its own `/api/v1/evidence/` resource (`project_filter` walks `hypothesis__project__slug`). `HypothesisSerializer` nests evidence rows (with a `reference_detail` summary, note and document titles), the supports/contradicts/mixed tallies and `suggested_status` from the evidence balance. Evidence writes bump the hypothesis' `updated_at` (`_touch_hypothesis`) so list/detail ETags change — the same stale-304 bug the manuscript studio had (#327), caught again by Playwright. MCP gains `add_hypothesis`, `set_hypothesis_status`, `add_evidence`, `log_experiment` (86 tools). `Research.tsx` is rewritten as a ledger: propose box, hypothesis cards with the evidence balance bar, "evidence says X →" one-click accept, an inline evidence form with paper/note autocomplete (reusing the notes suggest endpoint), experiment log and dataset registry; both destructive buttons confirm.

**Why.** The Research page was the last area without a v2 pass and the only one where the SPA could not create anything — every hypothesis had to come from the admin. A ledger is only useful if attaching evidence is a five-second act from the page you are reading on.

**Alternatives.** Evidence as a nested write on the hypothesis (rejected: a flat resource is simpler for MCP and for deletes); a modal per evidence row (rejected: inline is faster and matches the rest of the SPA).

### 2026-09-06 — Review matrix v2: the extraction table (#339)

**Decision.** `literature/matrix.py` turns the review matrix into an extraction table: `add_theme`
(case-insensitive reuse, auto order), `resolve_theme` (id or name — a new name creates the column),
`set_mark` (reference by id or bibtex key; create / update note / clear), `matrix` (themes with
coverage, rows with cells keyed by theme id) and `matrix_markdown`. API on projects:
`review-matrix/` gains `table`; `POST review-matrix/themes/`, `PATCH|DELETE
review-matrix/themes/{id}/`, `POST review-matrix/mark/`, `GET review-matrix/markdown/`. MCP
`set_review_mark`, `add_review_theme` (82 tools). New SPA page `/projects/{slug}/matrix` (also a
quick link on the overview): sticky paper column and theme header with coverage bars, click to mark,
click again to type the finding (Enter saves, right-click clears), inline theme rename/delete, paper
filter and "only untouched", Copy as Markdown, `.md` download, Draft synthesis note.

**Why.** Elicit's paper × question table is the feature researchers screenshot; Atlas has had the
data model since Phase 2 but only a classic toggle grid. With cells that hold the extracted finding
and an MCP tool to fill them, Claude can read the project's PDFs (`search_in_pdf`, highlights) and
draft the table for the researcher to correct — offline, on their own library.

**Alternatives considered.** Free-form column types (numbers, enums) — parked: a 300-character
note per cell covers extraction; typed columns can come with an export to CSV. Auto-suggested
themes from keywords — parked (the keyword cloud exists; a "suggest themes" button is a small
follow-up).

### 2026-09-06 — Search v2 + Reference page parity (#337)

**Decision.** Search results now explain themselves: `core.search.describe` adds a `snippet`
(for papers the PDF page hit with its `page` and `where: "in the PDF"`, else an excerpt of the
abstract; for notes/decisions/phases/manuscripts an excerpt of their text around the first term),
an `app_url` that opens the object in the SPA, and a one-line `meta`; the API also returns
`project_name`. The Search page is rewritten: `?q=` in the URL, results grouped by kind with counts,
terms marked in labels and snippets, "in the PDF · p.N" chips, ↑↓/Enter navigation. The standalone
Reference page gains the Cite block (remembered style, in-text and `\cite{}` copies) and the
Highlights section, links "open in the Library", and replaces the PDF iframe — which the
`X-Frame-Options: DENY` header (kept, it is a security test) blanked — with a "Read & highlight →"
jump that deep-links the Library reader via `?q=<key>&read=<id>`.

**Why.** A search that only lists titles makes the reader open five things to find the one; the
snippet with the page is the answer in place, and it showcases the PDF full-text index. The
Reference page was the one paper view without highlights or citations.

**Alternatives considered.** Relaxing frame options to SAMEORIGIN for the iframe — rejected: the
workbench reader is better than an iframe and the header stays strict.

### 2026-09-06 — Inbox v2 slice 1: smart capture triage (#335)

**Decision.** `notes/capture.py` reads a capture (`detect`: DOI / arXiv id / URL, and the prefixes
`todo:` `idea:`/`note:` `decision:` `milestone:`; long or multi-line text suggests a note; the rest
suggests a Today item) and converts it (`convert`) into a paper (via `add_reference_by_identifier`,
filed into the project), a note (title from the first line, URL appended), a Today item, a milestone
(current phase, or a "Backlog" phase created on demand, optional due date) or a decision record —
then marks the capture processed and filed. The list serializer carries `hint`; `POST
/quick-capture/{id}/convert/`; `?processed=` filter; MCP `list_inbox`, `convert_capture` (80 tools).
The Inbox page is rewritten in the Observatory identity: live "looks like a …" hint while typing,
⌘Enter capture, rows with detected chips and one-click targets (the suggested one highlighted),
project select, File and Dismiss; optimistic removal and a toast with an "open →" link. **Dashboard
v2 judged done** after slice 1; current area: Inbox.

**Why.** An inbox that only files text under a project is a to-do list with extra steps. Research
captures are usually a paper, a task or an idea; turning them into the real object is the triage,
and doing it in one click is what makes the inbox get emptied.

**Alternatives considered.** LLM classification of captures — rejected: the prefixes and ids cover
the common cases deterministically and offline; the suggested target is only a highlight, every
target stays one click away. Auto-converting DOIs on capture — rejected: the owner should choose the
project, and a capture may be a reminder rather than a request to add.

### 2026-09-06 — Dashboard v2 slice 1: this week, everywhere (#333)

**Decision.** `core/dashboard.py` gains `week_everywhere` (two cross-project queries: open
milestones and tasks due within seven days in planning/active projects, overdue first, each carrying
its project slug/name/colour and phase) and `project_health` (the current phase's roadmap health per
active project). `GET /dashboard/` now returns `week`, `todos_open`, `heatmap` (the cached 26-week
grid the classic page already had) and `health` on each active row; MCP `get_dashboard` (78 tools).
The SPA dashboard adds "This week, everywhere" (tick-to-complete with optimistic removal), health
pills under each active project, an "on today's list" tile linking to Today, and the heatmap at the
bottom (hidden in calm mode). **Overview v2 judged done** after slice 1; current area: Dashboard.

**Why.** CLAUDE.md's Phase 5 acceptance is literally "what should I work on today, everywhere?" —
the needs-attention lead answered the urgent part; the week list answers the rest, and completing
from the dashboard means the answer updates without leaving it.

**Alternatives considered.** Reusing `plans.focus.week_focus` per project — rejected: N projects ×
several queries; two flat queries do it. Next-up items on the dashboard — rejected: without a
project context "next" is noise; the project overview keeps it.

### 2026-09-06 — Overview v2 slice 1: one glance, in the Observatory (#331)

**Decision.** `projects/overview.py` adds four blocks to the overview API: `week_digest` (the
project's timeline events of the last seven days, counted by kind with the six newest items),
`questions` (open first, then partially answered, answered, abandoned; with their phases),
`manuscripts` (live ones by nearest deadline, with days left and any venue-budget overruns), and
`hypotheses` (counts by status). The SPA overview is rewritten in the Observatory identity: ring +
gradient milestone count in the header, quick links, a current-phase card (health pill, objective,
glowing bar, window), the compact This-week strip, a three-up row (digest, questions + hypotheses,
manuscripts), count tiles that link into the right section, next milestones, recent documents and
decisions. **Writing v2 judged best-in-field** after three slices; current area is the Overview.

**Why.** CLAUDE.md calls the overview the heart of Atlas: "one glance = full situational
awareness". It answered "where are we" but not "what changed" or "what is still open"; the digest and
the questions block close that, and manuscripts with overruns bring the writing pipeline into view.

**Alternatives considered.** A per-project activity heatmap — parked for the Dashboard, where the
cross-project one lives. Pinned documents — parked; recent documents plus the Files page cover it.

### 2026-09-06 — Writing v2 slice 3: the venue budget (#329)

**Decision.** `Manuscript.venue_limits` (JSON, migration writing 0012) stores the target venue's
limits for words, abstract words, figures, tables, references and pages; `writing/budget.py`
computes usage (LaTeX detex word count over the .tex files, abstract word count, `figure`/`table`
environments, bibliography size, PDF pages after a compile via pypdf) and rates each against its
limit: ok / near (≥ 90 %) / over, with a one-line summary. Limits are validated on the serializer
(`clean_limits`: known keys, positive integers only). API `GET /manuscripts/{id}/budget/`; limits
via the normal PATCH; MCP `get_manuscript_budget`, `set_venue_limits` (77 tools). UI: a Venue
budget card in the studio with an inline six-field limits form and colour-coded bars.

**Why.** "Am I over?" is the question asked ten times a day in the last week before a deadline;
Overleaf answers it with a plugin and a guess. Keeping the limits on the manuscript makes the
answer live everywhere — in the studio, from Claude, and later on the dashboard.

**Alternatives considered.** A shared `Venue` table with known journals' limits — parked: a
handful of numbers per manuscript is convention-over-configuration; a venue library can be built
on top when there are enough manuscripts to share them. Page estimates without a compile —
rejected: a number that is wrong is worse than "unknown until compiled".

### 2026-09-06 — Writing v2 slice 2: the reviewer-response tracker (#327)

**Decision.** `writing/reviews.py` parses pasted reviews into points (reviewers split on
"Reviewer N" / "Referee N" headings, points on numbered or bulleted lines, unmarked paragraphs
folded into the previous point), logs a `reviews_received` event whose notes link the note with
`[[…]]`, and writes a "Response to reviewers — <title> (<date>)" note: `## Reviewer N` sections,
`- [ ] **RN.k** <point>` with a `> Response:` slot under each. Progress = ticked boxes / boxes in
the newest such note for that manuscript (scoped by title prefix, so two manuscripts in one project
don't share). API `POST /manuscripts/{id}/reviews/`, `GET …/response-progress/` (`{progress: …|null}`
— a bare null renders as an empty body in DRF); MCP `log_reviews`, `get_response_progress` (75
tools). UI: choosing "Reviews received" in the timeline form reveals the paste box; a progress card
links to the note; the compile card gains the submission `.zip` link. Fixed on the way: the
manuscript detail ETag is built from `updated_at`, so events and bibliography changes now touch the
manuscript — otherwise the SPA (and MCP polling) kept a 304-stale timeline.

**Why.** The revision round is where papers die: reviewer points scattered across an email, a
response letter rebuilt from scratch. Turning the reviews into a checklist note the moment they
arrive, and showing "7/12 answered" on the manuscript, keeps the round moving — and the note is
already in the project's graph, citing the papers the reviewers asked for once you add `@keys`.

**Alternatives considered.** A dedicated ReviewPoint model — rejected for now: the note is
editable, exportable and linkable for free, and checkbox progress is honest enough; a model can
come if per-point status or reviewer assignment is needed. Parsing with an LLM — rejected: the
heuristics cover the common shapes and never fail (an unparseable paste still scaffolds R1.1).

### 2026-09-06 — Writing v2 slice 1: the manuscript studio (#325)

**Decision.** The SPA manuscript page becomes the studio: everything about one paper on one screen,
with the LaTeX editor one click away. New API on manuscripts: `bibliography` (GET rows with cite
key / title / year / authors; POST adds a library paper, idempotent, with an optional cite-key
override), `DELETE bibliography/{reference_id}`, `cite-check` (every `\cite`-family key across all
.tex files — or `latex_source` — against the bibliography, plus `resolvable`: missing keys the
library already knows, with ids), `bib` (text/x-bibtex download), `events` POST and
`DELETE events/{id}`; manuscripts are creatable through the API. MCP `get_manuscript_bibliography`,
`add_manuscript_reference`, `remove_manuscript_reference`, `manuscript_cite_check`,
`add_submission_event` (73 tools). UI: board in the Observatory identity with a new-manuscript form
and a "deadlines within two weeks" strip; studio with an editable title/venue/deadline header, a
status pipeline (past steps ticked), abstract with autosave and word count, source & compile card
(files, main file, compile, status pill, diagnostics, PDF link, approximate word/heading/caption
counts), bibliography card (search the project's literature → Add, cite-key chips copy `\cite{}`,
"cite all", .bib), cite-check card (missing keys with one-click add from the library, uncited
entries), submission timeline with log/delete.

**Why.** Overleaf edits; Paperpile cites; neither answers "is this paper's bibliography consistent
with what I actually cite, and where is it in the pipeline?" The studio makes that the default view
and keeps the classic editor for the source itself.

**Alternatives considered.** Embedding the LaTeX editor island in the studio — parked: the editor
is a full-height workspace with its own file tree; a link is honest for now. A separate events
viewset — rejected: events belong to a manuscript and never need listing across manuscripts.

### 2026-09-06 — Notes v2 slice 3: templates and export with a bibliography (#323)

**Decision.** `notes/templates.py` renders five templates from project data: *literature* (title
"Family Year — title", first line `@key`, metadata + DOI, sections In one sentence / Claims / Method /
Limitations / Why it matters, then every highlight of the paper as block quotes with page and
comment, and a `[[Highlights — key]]` link when that note exists; the reference is attached), *daily*
(title = ISO date, unique per day; this week's focus from `plans.focus` as checkboxes, then Log and
Captured), *meeting*, *experiment*, *blank*. `export_note` returns the body as written plus a
References section formatted by `literature.citations.bibliography` in the chosen style. API:
`GET /notes/templates/`, `POST /notes/from-template/`, `GET /notes/{id}/export/?style=`; MCP
`create_note_from_template`, `export_note` (68 tools). UI: the New-note pane offers the templates (the
literature card searches the project's papers inline), the editor toolbar gets "export" (copies
Markdown with the bibliography in the Library's remembered citation style), and the Library detail
pane gets a "Note" button that starts a literature note in the paper's project. **Notes + graph
judged best-in-field** after three slices (workbench with @citations, navigable vendored graph,
templates + export); next area: the Writing studio.

**Why.** Zettelkasten tooling asks the researcher to build literature notes by hand; here the paper,
its key and the highlights already taken arrive in one click, and the note leaves with a
bibliography. The daily note is the ADHD-friendly page the owner asked for, seeded from the plan.

**Alternatives considered.** User-editable template bodies — parked: convention over configuration,
and the five cover the research loop; a `templates` setting screen can wait. Pandoc-style
`[@key]` brackets — rejected: `@key` alone is what people type and what the autocomplete inserts.

### 2026-09-06 — Notes v2 slice 2: Graph v2, vendored and navigable (#321)

**Decision.** `3d-force-graph` 1.73.4 and `force-graph` 1.43.5 are vendored under
`static/vendor/forcegraph/` (MIT, unmodified dist builds) and both the SPA page and the classic
template load them from there — the desktop app must not depend on unpkg being reachable. A guard
test fails the build if either page references unpkg again. `core/graph.py` now returns per-node
facts (year, venue, authors, citations, PDF, highlight count for papers; words and last edit for
notes; degree for all; `app_url` for SPA navigation) and `stats` (counts, links by kind, orphans, top-5
hubs). The Graph page is rewritten: search with match count and Enter-to-focus, paper/note and
link-kind toggles, hide-unconnected, neighbourhood focus mode with depth 1/2 (computed client-side
over the full graph, which is project-sized), hover dimming of non-neighbours, camera fly-to on
click in 3D, directional particles on citation edges, dark/light canvas from the theme, a hubs card
and a node panel with facts, Open, Focus and the clickable neighbour list. React never renders
children inside the library's mount div (that crashed the page: the library cleared React-owned
nodes); overlays are siblings.

**Why.** A graph you can't search or focus is decoration. Focus mode + the neighbour list turn it
into navigation: from a hub paper to the notes that cite it and back. Vendoring is what makes the
graph exist at all in an offline desktop session.

**Alternatives considered.** Server-side neighbourhood queries (`?focus=`) — rejected for now:
the whole project graph is a few hundred nodes and one request; revisit when projects have
thousands of references. Bundling the library through Vite instead of a script tag — rejected:
three.js in the island bundle would triple its size for one page.

### 2026-09-06 — Notes v2 slice 1: the notes workbench with @citations (#319)

**Decision.** Notes adopt Pandoc-style citation keys: `@bibtex_key` in a body attaches the paper to
the note (`sync_note_references`, additive — manual links are never removed) and renders as a link
to the paper in the preview; `[[Title]]` keeps linking notes. New API: `GET /notes/{id}/links/`
(outgoing, backlinks, references, unresolved titles/keys, unlinked mentions), `GET /notes/suggest/`
(autocomplete for both triggers, prefix matches first, references limited to papers filed in the
project), `GET /notes/unwritten/`; `references_detail` on the note serializer; MCP `list_notes`,
`get_note`, `update_note`, `get_note_links` (66 tools). The SPA Notes page becomes a workbench:
list with search and the "linked but unwritten" stubs, editor with a live preview beside it and
autosave (1.2 s / ⌘S), an autocomplete popover for `[[` and `@` (client-side re-ranked against the
characters typed now, since the query is debounced), and a link panel (Cites / Links out / Backlinks
with mentions-without-a-link). One lazy component serves all three note routes so switching notes
keeps the list state.

**Why.** Obsidian and Logseq made `[[links]]` table stakes; what a researcher's notes lack there is a
first-class tie to the literature. `@key` is the notation people already use in Markdown manuscripts,
so a note that cites becomes a graph edge and a bibliography for free.

**Alternatives considered.** A rich-text/CodeMirror editor — rejected for this slice: a textarea with
a preview keeps the Markdown honest and ships without a dependency; caret-accurate popovers can come
later. Removing references when a key disappears — rejected: manual attachments from the reader
would be lost. Global reference suggestions — rejected: the project's own literature is the
relevant set, and the library workbench files papers in one click.

### 2026-09-06 — Plan v2 slice 4: phase context, questions on the plan, keyboard reschedule (#317)

**Decision.** The plan API now returns each phase's objective, target window and attached research
questions, plus the project's full question list; the phase card shows a context block (objective —
click to edit, autosaved on blur; question chips coloured by status with detach; "+ research
question" attaches through `PATCH /questions/{id}/ {phases}`), and the header carries editable date
inputs. The roadmap's bars and diamonds are focusable; ←/→ nudge a day, Shift+←/→ a week, saving on
each press. **Plan judged best-in-field after four slices** (document outline, roadmap with health and
forecast, this-week focus, drawer, context, API + MCP parity) — next area: Notes + knowledge graph.

**Why.** CLAUDE.md's research-first value puts questions and phases together; until now the link was
only editable in the classic forms. Objectives are the "why" of a phase and belong at the top of the
card, not in a form. Keyboard rescheduling makes the roadmap usable without a mouse and with a
screen reader (the bars are sliders with value text).

**Alternatives considered.** Creating questions from the plan page — parked; the Research page owns
question CRUD and the Plan only links. Natural-language dates — parked again; date inputs and the
outline cover it.

### 2026-09-06 — Plan v2 slice 3: this week + the milestone drawer (#315)

**Decision.** `plans/focus.py` computes one project's week: overdue milestones and tasks (oldest
first, milestones before tasks on the same day), everything due within seven days, then up to three
undated/later milestones of the current phase so the list never goes empty while work remains.
`GET /projects/{slug}/focus/`; the overview embeds the same block plus a `health` reading for the
current phase (from the roadmap service); MCP `get_week_focus` (62 tools). UI: a "This week" strip at
the top of the Plan (and, compact, on the overview) with in-place completion; a milestone drawer
(title, due date, notes with autosave, tasks add/toggle/delete, delete) opened from any milestone
title; the plan API now returns milestone notes. The drawer is opaque (`.drawer-solid`) because the
Observatory glass panels bleed the page through.

**Why.** The Plan answered "where are we" but not "what now": the researcher still had to scan every
phase for the nearest date. The strip is the answer in one glance, and completing from it keeps the
plan honest. The drawer closes the last gap that sent people to the classic page (notes, dates).

**Alternatives considered.** Cross-project "this week everywhere" — that belongs to the Dashboard
area and will reuse `week_focus`. Natural-language dates in quick-add ("next fri") — parked; the
outline + date input cover it for now. A modal instead of a drawer — rejected: the plan stays
visible for context.

### 2026-09-06 — Plan v2 slice 2: the roadmap (#313)

**Decision.** `plans/roadmap.py` turns the plan into timeline rows: each phase gets a window (its
target dates, else inferred: after the previous phase / from its milestones' due dates / six weeks,
flagged `inferred`), its milestones with due/done/overdue, a health state computed from the share of
milestones done against the share of the window elapsed (±15 % band → on_track; blocked / overdue /
upcoming / done / empty are explicit), a one-line reason, and a finish forecast = today + remaining ×
the measured days-per-milestone once two are done. `GET /projects/{slug}/roadmap/`; rescheduling
reuses `PATCH /phases/{id}/` and `/milestones/{id}/`; MCP `get_roadmap`, `set_phase_dates` (61 tools).
The Plan page grows a Phases | Roadmap | Outline switch (remembered in localStorage). The roadmap is
plain React + pointer events: month gridlines, a glowing today line, bars coloured by health with
the progress fill inside, dashed bars for suggested dates, a striped forecast tail, diamonds for
milestones (filled = done, red glow = overdue); drag a bar to move, its edges to resize, a diamond
to change a due date — optimistic locally, one PATCH on release.

**Why.** "Where are we against the plan?" needs time on an axis, not a list. Inferred windows mean
the view is useful from the first milestone; the health reading names *why* a phase is behind so
the fix is obvious; drag-to-reschedule makes the roadmap the place plans get adjusted, not a report.

**Alternatives considered.** A Gantt library (frappe-gantt, dhtmlx) — rejected: a dependency and its
own styling for a view that is 300 lines of React; the Observatory look would fight it. Dependencies
between phases (finish-to-start arrows) — parked: phases are already ordered, and arrows add noise
before there is a scheduling engine. Per-milestone "days late" statistics — parked to the dashboard.

### 2026-09-06 — Plan v2 slice 1: the plan as a document (#311)

**Decision.** The Library is judged best-in-field after eight slices (import from anywhere, faceted
workbench, discovery lenses, six citation styles, tags + smart views, duplicate merge, in-place reader
with highlights and reading notes, full-text search inside PDFs; API + MCP parity throughout). Next
area per the cycle order: the Plan. Slice 1 makes the plan writable as a document: `plans/outline.py`
exports the plan as a Markdown outline (`# phase [status] (start → end) {#id}`, `> objective`,
`- [ ] milestone (due …) {#id}`, indented tasks) and applies an edited outline back — `{#id}` tokens
keep identity across renames (so completion timestamps, notes and links survive), lines without an id
create, missing ids delete, checkboxes set completion, order = position. `preview()` reports created /
renamed / deleted before anything is written; parse errors carry line numbers. API `GET/POST
/projects/{slug}/outline/` (`dry_run`), MCP `get_plan_outline` / `set_plan_outline` (59 tools). The SPA
Plan page is rewritten in the Observatory identity: orbit-ring progress, gradient count, glass phase
cards with glowing accent bars, click-to-cycle status, milestone/task check-off, inline quick-add, and
an "Edit as outline" mode (monospace editor, Tab indents, ⌘S saves, live dry-run panel, syntax card).

**Why.** Every PM tool makes you click through forms to plan; researchers plan in text. An outline
that round-trips losslessly is faster to write, diffable, pasteable into a proposal, and the same
contract Claude can use to draft or restructure a plan in one call.

**Alternatives considered.** A drag-and-drop outliner component — rejected: heavy, and a textarea with
a live preview is honest about what a save does. Matching by title instead of ids — rejected: renames
would look like delete + create and lose history. Making the outline the storage format — rejected:
the relational model drives progress roll-ups, the overview and the dashboard.

### 2026-09-06 — Library v2 slice 8: search inside your PDFs (#309)

**Decision.** Every attached PDF is read once with pypdf into `literature.ReferenceText` (one string
per page + the joined body; `source_name` remembers which file it came from). A `post_save` receiver
on `Reference` enqueues `extract_text_task` whenever the PDF is new or changed (huey; immediate in the
desktop and dev settings) and drops the row when the PDF is removed; `manage.py index_pdf_text` backfills.
Matching is `icontains` on the body on every backend (the desktop runs SQLite) — Postgres additionally
folds `text__body` into the global-search vector at weight D. The workbench search annotates
`pdf_match` per row, the detail pane shows "Found in the PDF" with page + snippet, and the reader
gets a find bar that walks the matching pages and paints the term on the text layer. API:
`GET /references/text-search/?q=` (library-wide, optional project), `GET /references/{id}/text-search/?q=`,
`POST /references/{id}/index-text/`; `text_status` on every reference. MCP: `search_pdf_text`,
`search_in_pdf` (57 tools).

**Why.** Zotero and Paperpile both index PDF text; a library that only searches titles and abstracts
loses exactly the queries a researcher asks ("which paper mentioned the dissociation?"). Page-level
storage is what makes the answer actionable: the hit names the page and the reader opens on it.

**Alternatives considered.** A Postgres `SearchVectorField` with a GIN index on the body — better at
scale, but SQLite desktop builds would need a second path; `icontains` is honest and identical on
both, and a trigram/FTS upgrade stays possible behind `pdf_match_filter`. Storing text in
`Reference.extra` — rejected: a multi-megabyte JSON field on the hot row. Extracting at import only —
rejected: PDFs also arrive by Unpaywall fetch, API upload, and merge; the signal covers all of them.

### 2026-09-06 — Library v2 slice 7: read and highlight inside the workbench (#307)

**Decision.** Highlights become a model (`literature.Highlight`: reference, optional project, page, text,
comment, colour) instead of lines appended to a note. `reading.add_highlight` still mirrors the passage
into the project's "Highlights — <key>" note when a project is given (the note graph keeps working) and
bumps `to_read` links to `skimmed`. The classic reader's save endpoint now goes through the same service.
The workbench gets a pdf.js reader in the centre pane (vendored build, lazy per-page render, text layer,
selection → colour bar → POST /highlights/), and saved highlights are painted back by matching their text
against the page's text spans — no stored rectangles, so a re-rendered or re-imported PDF still shows them.
Reading notes reuse `ProjectReference.notes` (one textarea per project, debounced PATCH). Per-row
`POST /references/{id}/fetch-pdf/` wraps the existing OA download. MCP: `list_highlights`, `add_highlight`,
`get_highlights_markdown`, `get_reading_notes`, `set_reading_notes`, `fetch_pdf` (55 tools).

**Why.** Zotero's reader is the one thing people say they can't leave it for; Paperpile and ReadCube
charge for it. Reading is where a library earns its keep, and every highlight should be a first-class row
Claude can list, comment on and paste into a manuscript — not a line buried in a note body.

**Alternatives considered.** Storing highlight rectangles (exact repaint, but breaks when the PDF is
replaced, and doubles the payload) — rejected for now; text matching is good enough and honest.
Embedding the classic reader page in an iframe — rejected: no shared state with the detail pane.
A separate `/read` SPA route — rejected: the whole point is not leaving the list.

**Release workflow.** Pruning old installers moved from the start of every matrix job to a post-build
`prune` job that runs only when every platform succeeded: the owner opened the release mid-run and found
no `.exe` because the Linux job had already deleted the previous Windows installer.

### 2026-09-06 — Library v2 slice 6: duplicate clusters and a real merge (#305)

**Decision.** `library.duplicate_groups()` clusters probable duplicates with a union-find over
the existing `check_duplicates` findings (near-identical normalised titles; DOI matches are
impossible in the database because DOI is unique) plus identical arXiv ids, and suggests the
most complete record to keep (PDF 8, DOI 4, abstract 2, year 2, venue 1, +authors, +3 per
project link, +tags). `library.merge_references(keep, merge)` folds everything into the kept
record inside a transaction: project links (the better reading status / high priority / merged
notes / review marks win when both exist), tags, note links, manuscript bibliographies, evidence,
citation edges (deduplicated, self-edges dropped), comments (generic FK), the PDF file, and
empty scalar fields; `extra.merged_from` records the folded keys; the merged record's DOI and
file are released before the kept one saves (unique constraint). Exposed as
`GET /references/duplicates/`, `POST /references/merge/`, MCP `find_duplicates` /
`merge_references` (49 tools), a `duplicates` facet count, and a **Duplicates** mode in the
workbench (rail chip → grouped cards with a keep radio and "Merge into the selected").

**Why.** Every library that imports from more than one source grows duplicates; the bib report
flagged them for months without a fix action, and the workbench made bulk import easy enough
that a merge became the missing half. Losing a project link, a note, or a PDF during cleanup is
the failure mode every researcher fears — hence the relation-by-relation move with tests.

**Alternatives.** (a) Auto-merge on import when titles match — rejected: title similarity has
false positives (editions, errata, translations); a human picks the survivor. (b) Soft-delete the
merged rows — rejected: the export/dedupe paths would need to filter them everywhere; the
`merged_from` trail on the kept record preserves the history that matters.

### 2026-09-06 — In-app updates go live: signed feed on the published preview release (#303)

**Decision.** (1) The updater keypair now exists: the public key is committed in
`desktop/tauri.conf.json`; the private key is held by the owner and belongs in the
`TAURI_SIGNING_PRIVATE_KEY` repo secret. (2) The release workflow flips
`createUpdaterArtifacts` on only when that secret is present, so builds never go red for a
missing key. (3) The rolling `desktop-preview` release is **published as a prerelease** (a
draft can't be fetched by the app), with a prune step keeping only the newest build's assets;
the updater endpoint is the tag URL (`releases/download/desktop-preview/latest.json`), not
`releases/latest`, which ignores prereleases. (4) The shell exposes `check_update` (silent, on
launch) and `install_update` separately; the sidebar control becomes "Update to x.y.z" when a
build is available, installs on click, and offers a restart — with a "get it manually" link
when the feed is unreachable.

**Why.** Owner: "auto update or update button so I won't need to download it every time and
install again." Tauri's updater refuses unsigned artifacts, so signing is the only route; the
one thing the code cannot do is add the secret to GitHub — that stays a one-time owner action,
and everything else is ready the moment it exists.

**Alternatives.** (a) Download the installer and launch it (no signing) — rejected: no
integrity check on a binary that runs as the user, and the NSIS/MSI dance is what the owner
wants to stop doing. (b) Commit the private key to the workflow — rejected outright.
(c) Generate a fresh key per build — rejected: the public key is baked into the installed app,
so updates would never verify.

### 2026-09-06 — Library v2 slice 5: tags and smart views (#301)

**Decision.** `literature.LibraryTag` (global, case-insensitive-unique labels with an optional
colour) on `Reference.tags`, and `literature.SavedView` (a named dict of the list endpoint's
filter params). The workbench rail gains **Smart views** ("+ save" appears whenever a filter is
active; one click restores the exact query, including the search text) and **Tags** (counts,
an Untagged bucket). Tags are applied from the bulk bar ("tag…" with suggestions), from the
detail pane (chip editor), or by writing `tags: [names]` on a reference through the API;
missing tags are created. API: `library-tags` (with counts; POST reuses a case-insensitive
match), `library-views`, list filters `tag=` / `untagged=`, bulk `tag` / `untag`, facets carry
`tags`, `untagged`, `views`. MCP: `list_library_tags`, `tag_references` (47 tools).

**Why.** Zotero's collections/tags and Paperpile's labels + saved searches are how people keep
a 1,000-paper library navigable; Atlas had projects only. Saved views are the cheapest possible
"collections": they compose every filter the rail already has instead of a second hierarchy.

**Alternatives.** (a) Reuse `documents.Tag` — rejected: per-project by design, while the
library is global. (b) Nested collections — rejected: smart views + project filing cover it
without a tree to maintain; revisit only if users ask.

### 2026-09-06 — A plain "Today" list, separate from plan tasks (owner request, #299)

**Decision.** `core.TodoItem` (text, done, done_at, position, optional project) with a
dead-simple SPA page at `/today` (input + Enter, one-click tick with an optimistic update, done
items sink to a "Done" section, "Clear done"), a "Today" entry at the top of the sidebar,
`/api/v1/todos/` (+ `clear-done`), and MCP `list_todos` / `add_todo` / `complete_todo`.

**Why.** The owner: "I have ADHD and I keep losing track of the stuff I need to do for the day…
something very simple." Plan tasks live under milestones and carry research structure; the
inbox is for unprocessed thoughts. Neither is a scratch list you glance at ten times a day.
Open items are never auto-cleared — losing an item overnight is the failure mode to avoid.

**Alternatives.** (a) Reuse `plans.Task` with a null milestone — rejected: it would leak into
plan progress roll-ups and the model's invariant (every task under a milestone). (b) Reuse
`QuickCapture` with a flag — rejected: the inbox's job is triage, and mixing the two makes
both noisier. Parked ideas: due dates/reminders, drag-to-reorder, a dashboard widget (#300).

### 2026-09-06 — Library v2 slice 4: formatted citations without a CSL engine (#297)

**Decision.** `literature/citations.py` formats bibliography entries, in-text forms, and whole
bibliographies in six styles (APA 7, MLA 9, Chicago author-date, Harvard, Vancouver, IEEE) as
hand-written pure functions over the metadata Atlas holds, with volume/issue/pages now carried
into `Reference.extra` by the Crossref and OpenAlex mappers. Exposed as
`GET /references/{id}/cite/?style=`, `GET /references/cite/?ids=&style=` (alphabetical for
author-date styles, numbered in the given order for Vancouver/IEEE), MCP `format_citations`, a
Cite block in the workbench's detail pane (style picker remembered in localStorage, Copy
citation, the in-text form as a copy button), and **Copy citations** in the bulk bar.

**Why.** "Copy a citation" is the single most frequent thing researchers open Zotero for, and
the reason Paperpile's browser button exists; six styles cover the vast majority of venues.

**Alternatives.** (a) citeproc-py + CSL styles — rejected for now: 2k+ style files, a heavy
dependency, and a JSON-schema conversion layer, for output the six hand-written styles already
give; the module is shaped so a CSL engine could replace it behind the same `cite()` /
`bibliography()` contract later. (b) Client-side citation.js — rejected: would duplicate the
formatting in the SPA and leave the API/MCP without it.

### 2026-09-06 — Library v2 slice 3: grow the library from any paper (#295)

**Decision.** Three OpenAlex lenses on every reference, inside the workbench's detail pane:
*Similar* (`related_works`), *It cites* (`referenced_works`, batched 50 at a time), and
*Cited by* (`filter=cites:`, most-cited first). Every row is annotated with library membership
in one query (by DOI and by OpenAlex id), so the UI offers **+ Add** (via the existing
`by-doi` endpoint, into the current project filter when one is set), **in library** (a link),
or an OpenAlex link for rows without a DOI. The resolved OpenAlex id is stored on the reference
the first time, so later lenses cost one request less. Same slice: **Export .bib** for a
selection or for the whole filtered view (`GET /references/export/?ids=…` or the list
filters), **Copy BibTeX** to the clipboard, and a **Fetch OA PDFs** bulk action that queues the
existing open-access fetch for every selected paper without a file. MCP: `discover_related`,
`export_bibtex` (41 tools).

**Why.** This is ResearchRabbit's whole pitch and Zotero has nothing like it; putting it one
click from every paper, with dedupe and project filing built in, is the "finally" moment for
literature review. Export-of-selection is the most common thing Paperpile users do daily.

**Alternatives.** (a) Semantic Scholar's API — rejected: needs an API key for useful rate
limits; OpenAlex is keyless and already used. (b) A full citation-graph page instead of a pane —
already exists (Graph); the pane is about *action* (add), not visualisation. (c) A download
endpoint with `Content-Disposition` only — kept, plus clipboard copy, because the Tauri webview
does not download files.

### 2026-09-06 — Library v2 begins: one import engine for every source (#293)

**Decision.** The Library is the first feature area to be made best-in-field (owner: "one
feature at a time… better than the profitable companies"). Slice 1 is getting papers IN from
anywhere through one path: `literature/importers.py` parses BibTeX, CSL-JSON (Zotero's export
and its local API), and RIS (EndNote/Mendeley/Web of Science) into the same metadata dicts, and
dropped PDFs are read (pypdf, first 3 pages) for a DOI/arXiv id → real metadata fetched → file
attached; PDFs without an id are kept as stubs titled from the PDF and flagged `needs_metadata`
so nothing is ever lost. Everything dedupes by DOI, arXiv id, or normalised title + year
(≥ 8 chars), across formats. Exposed as `POST /api/v1/references/import/` (multipart files +
pasted text), `POST /api/v1/references/import-zotero/` (Zotero 7 local API, paginated, with an
actionable error when Zotero is closed or its API is off), and MCP tools `import_references` /
`import_from_zotero`. The old `services.import_bibtex` keeps its callers but new imports go
through the shared dedupe path.

**Why.** Every commercial library tool wins or loses on day one: can I bring my 400 papers in?
Zotero users export CSL-JSON or run Zotero locally; Mendeley/EndNote users have RIS; everyone
has a folder of PDFs. Dedupe across formats is what makes repeated imports safe.

**Alternatives.** (a) Zotero web API with an API key — rejected for now: needs a key and a
network; the local API is zero-config on the machine Atlas (desktop) runs on. (b) GROBID for PDF
metadata — rejected: a 500 MB Java service; the DOI-on-page-one heuristic plus Crossref covers
the vast majority, and stubs catch the rest. (c) Adding `pypdf` breaks the locked dependency list
in CLAUDE.md §2 — accepted and logged: pure Python, tiny, and the frozen desktop build carries it
(spec THIRD_PARTY updated).

### 2026-09-06 — "Observatory": a new visual identity, dark by default (owner-directed, #291)

**Decision.** The owner rejected the calm-editorial look outright ("I still don't like the UI at
all… make this crazy enough for YouTube"). Atlas now has a signature identity, **Observatory**:
a deep-space canvas with a slow aurora and star grain, glass panels with luminous hairlines, an
electric-violet accent paired with cyan/magenta in gradients, display type (Space Grotesk) for
headings and numerals, staggered entrances, and a **living constellation** of the active
projects (a zero-dependency canvas module, `static/js/constellation.js`) behind the dashboard
greeting and on the login screen. The shell is an icon rail with a glowing active bar and an
"Ask Atlas anything ⌘K" spotlight; the command bar is a glass spotlight; the dashboard opens
with a time-aware greeting ("Good evening. 2 things need you.") and orbit-ring project progress.
Dark is the default; "Paper" (light) stays as an explicit choice via the same toggle.

**How it reaches every page without a rewrite.** Tailwind v4 emits colours as `var(--color-*)`,
so redefining the stone/indigo tokens under `.dark` re-skins all 16 SPA pages and every classic
template at once; panels get glass via the literal `dark:bg-stone-900` class token they already
carry (`[class~="dark:bg-stone-900"]`). Only Layout, Dashboard, CommandBar, and login were
touched by hand. Fonts are vendored (OFL) so the desktop app looks the same offline.

**Alternatives.** (a) A React redesign page-by-page — rejected for now: 5.6k lines of TSX for
the same visual result the tokens give; individual pages can still get bespoke treatment later
(backlog #292). (b) Keep follow-the-OS theming (#273) — rejected: the owner wants the new look on
first launch; the light theme is one click away. (c) three.js for the hero — rejected: the
citation graph already depends on a CDN that an offline desktop can't reach; a 2D canvas
particle field is dependency-free and cheap. §7 of CLAUDE.md ("calm and editorial") is
superseded by this owner direction; the calm-mode toggle and reduced-motion support remain.

### 2026-09-06 — Desktop ↔ Claude Code: ship `atlas-mcp` in the installer, zero-config (#289)

**Decision.** Make the installed desktop app driveable from Claude Code with one line and no
secrets to copy. Three pieces: (1) `config/settings/desktop.py` mints an API key on first launch
and persists it as `<data dir>/api_key` (an explicit `ATLAS_API_KEY` still wins); `run_desktop`
publishes `<data dir>/server.json` with the live URL (the port can differ from 8000 since #286).
(2) The MCP server is frozen with PyInstaller too (`desktop/server/atlas_mcp.{py,spec}` →
`atlas-mcp`) and shipped as a second Tauri bundle resource; with no `ATLAS_API_URL`/`ATLAS_API_KEY`
in its environment it discovers both from the data dir (`mcp_server/desktop_config.py`, still
Django-free), so the registration is `claude mcp add atlas -- "<install dir>/atlas-mcp/atlas-mcp"`.
(3) A **Connect Claude Code** page (`/connect/claude/`, linked from both sidebars) prints that
line for *this* install with the real path (the shell passes it as `ATLAS_MCP_BIN`), plus the key
and a JSON snippet for other MCP clients; on a dev/server install it prints the explicit
`--env ATLAS_API_URL/ATLAS_API_KEY … python -m mcp_server.server` form instead.

**Why.** Phase 6's acceptance ("from Claude Code, the owner can list projects…") was only true
for a repo checkout: the desktop build started with an EMPTY API key (so the API rejected every
call) and had no MCP server on the machine at all. The owner's ask was "100% integratable with
Claude Code" — for a desktop user that means no Python, no .env, no copying keys.

**Alternatives.** (a) Print the key in the `claude mcp add` line — rejected: it lands in shell
history and `.claude.json`; discovery from the data dir gives the same one-liner with no secret in
it (the key is still shown on the page for other clients). (b) Have `atlas-mcp` fail to start when
Atlas isn't running — rejected: Claude Code would then lose the tool list whenever the app is
closed; instead tool calls return "Atlas is not reachable … is the Atlas app running?".
(c) Bundle the MCP server INTO `atlas-server` (one binary, a `--mcp` flag) — rejected: the MCP
server must stay a pure API client (CLAUDE.md §5 Phase 6), and a separate binary keeps that
boundary visible. Verified end to end with the real `claude` CLI: `claude mcp list` → `√ Connected`
against the frozen binaries; a stdio client listed 37 tools and created a project through them.

### 2026-09-06 — Desktop: finish the SQLite switch by removing the Postgres remnants (#286)

**Decision.** Strip everything the bundled-Postgres design (#210g) left behind after the SQLite
switch (#266): the two CI steps that downloaded zonky's embedded-postgres binaries per OS, the
`resources/pg` bundle resource, the `ATLAS_PG_BIN` plumbing in the Tauri shell, the
`postgres.exe` taskkill in the NSIS hooks, the Postgres/`MSVCR120.dll` advice on the in-app
diagnostic page, and the dead `core/desktop_runtime.py` module (262 lines) with its 12 tests.
Keep `run_desktop`'s one-time cleanup of a stale `pgdata/` (that is the upgrade path for machines
that ran the old build). At the same time make the shell **step aside to a free port** when 8000
is taken (`choose_port` in server.rs) and derive `CSRF_TRUSTED_ORIGINS` from `ATLAS_PORT`.

**Why.** Every installer shipped ~50 MB of Postgres it never ran, the failure page told users to
install a VC++ redistributable that could not help, and a developer's `runserver` on 8000 made the
desktop app fail to bind (the CSRF origins were also hardcoded to :8000, so a different port would
have rejected every POST). This is the parked #268. The desktop README also still said the server
was "NOT YET" bundled.

**Alternatives.** (a) Leave the Postgres bundling as an "option" behind a flag — rejected: the
owner chose SQLite, and dead alternate paths are exactly what made the saga hard to debug.
(b) Fail loudly when 8000 is busy instead of choosing another port — rejected: the user cannot fix
that from inside the app, and nothing in the app depends on the port number. (c) Re-enable
AppImage now that the native Postgres `.so`s are gone — deferred (#288): worth one CI experiment,
but not bundled into this change so the release stays green.


### 2026-06-17 — Theme follows the OS by default now that dark mode is complete (#273)

- **Decision:** the theme bootstrap (base.html, spa.html, and the standalone login page) now
  resolves to: an explicit saved choice wins, otherwise follow the OS `prefers-color-scheme`.
  Previously dark was strictly opt-in — the script only added `.dark` for an explicit stored
  "dark" and ignored the OS — because dark coverage was partial and we didn't want to ship
  half-dark pages to OS-dark users. Dark mode is now complete app-wide (#270), so honoring the
  OS is the correct, expected default; the toggle still records an explicit override, and with
  no stored choice we track OS changes live.
- **Why:** a researcher whose machine is in dark mode expects a dark app on first visit without
  hunting for a toggle; the login screen (the desktop app's first screen) was previously always
  light despite having `dark:` variants, because it had no bootstrap script at all.
- **Alternatives rejected:** a server-side cookie/setting (adds a settings surface, violates §1
  "no settings screens"; the localStorage script is zero-config and flash-free); keeping opt-in
  (now that coverage is complete, opt-in is just a worse default).

### 2026-06-13 — [REV] Files explorer keyboard navigation

[REV] cycle (cadence: 1 per 10): made the workspace tree keyboard-drivable like a real
IDE explorer, building on Ctrl-P quick-open. The visible tree is flattened in render order
(folders + their expanded children/files), an arrow layer walks it: ↑/↓ move the focus
ring, → expands a collapsed folder (or steps in), ← collapses, Enter opens a file or
toggles a folder. The tree pane is role="tree", focusable, with a focus ring + scroll-into-
view; clicking a row also syncs the keyboard focus. Pure client-side, no new endpoint.
Verified live (focus → navigate to manuscript-8 → ArrowRight expands → Enter opens main.tex).



### 2026-06-13 — Unified tree via live mirror, not a source-of-truth rewrite (Owner #30, slice 1c-ii-B2)

The plan's slice 1c imagined flipping the manuscript editor/compile/API to read Documents
and demoting ManuscriptFile to a shadow. Doing that means rewriting the compile tree-writer,
the revisions snapshot, and — riskiest — the manuscript-files DRF serializer (a ModelSerializer
over ManuscriptFile) into a Document-backed serializer with byte-identical JSON, all under the
six-MCP-tool contract. High risk, and the owner's actual ask ("see all my files in one tree,
open any file") doesn't require it.

DECISION: keep ManuscriptFile as the canonical store for the editor/compile/API/MCP (contract
untouched, all tests trivially green) and MIRROR every ManuscriptFile write into the unified
Document tree via post_save/post_delete signals (writing/signals.py -> resync_manuscript_tree).
Same dual-store pattern as the long-stable latex_source<->main-file alias. B1's general() scoping
keeps the mirrored nodes out of the general Documents UI, so the slice-2 explorer can show the
WHOLE tree (general + manuscript-source, live) while nothing else changes. Rejected the pure flip
as gold-plating for a single-user app; if a true single source of truth is ever wanted it can come
later. The frozen contract tests (1c-i) stayed byte-identical through this — proof the editor/MCP
see no difference.



### 2026-06-12 — File-workspace epic slice 1a: paths module + ProjectFile fields (Owner #30)

First sub-step of the unified-tree slice 1, deliberately sized small + green-pushable after
the 2nd container rollback. `documents/paths.py` is now the canonical home for
`validate_manuscript_path` + the strict path constants (writing/models.py re-imports them, so
`writing.models.validate_manuscript_path` still resolves for the historical 0006 migration —
a hard move would have broken that migration's recorded reference). Added
`kind_for_node_path` (tex/bib/asset/other) for the general tree. `Document` grew four inert
fields — `content`, `rel_path`, `role` (GENERAL/MANUSCRIPT_SOURCE), `kind` — plus `file`
becomes blank=True; one additive migration (0003), NO unique constraint yet (the rel_path
uniqueness + backfill lands with the data migration in slice 1c, so 1a can't violate existing
data). Next: 1b = Manuscript.root_folder/main_file FKs; 1c = ManuscriptFile→ProjectFile data
migration + contract bridge + tests.



### 2026-06-12 — Left icon rail: drawers on the left, research stays right ([REV] cycle 135)

Parity-plan cycle 5 shipped: a ~40px vertical icon rail (Files / Outline / History / Research,
monochrome inline-SVG stroke icons) replaces the stacked always-on sidebar sections; one drawer
at a time, the active icon collapses its drawer, the choice persists (atlas-editor-drawer).
Two deliberate deviations from Overleaf: (1) the Research icon toggles the existing RIGHT-side
research panel rather than moving it into the left drawer — it is a reading surface that wants
width next to the PDF, and its loader is already wired to #research-toggle (the rail just
delegates and repaints); (2) the sidebar restore strip is gone (the rail IS the restore
affordance) but the gutter chevrons stay as a secondary collapse path. Element IDs all
preserved; word count remains as an always-visible drawer footer. Rejected: a Settings rail
icon (settings live in the View menu; duplicating them buys nothing).

### 2026-06-11 — Research timeline: "zoom" is period grouping; paper-read date is a proxy ([REV] cycle 95)
- **Decision:** The timeline's zoom is day/week/month *grouping* of one flat event payload
  (client-side), not a canvas zoom — research consulted (timeline UI pattern guides) favors
  vertical layouts with grouping for long event lists, and it keeps the API a single simple
  endpoint. "Paper read" uses the link's `updated_at` as a proxy (reading isn't separately
  timestamped) and is suppressed when it lands on the add date, so same-day add+read doesn't
  double-post. Markdown export is oldest-first because its use case is a paper's
  methods/history chronology.
- **Alternatives rejected:** a real zoomable canvas (d3/vis-timeline — dependency weight,
  violates §2, and grouping answers the same need); a `read_at` field migration (schema
  churn for marginal precision; parked — if it ever matters, log it as a backlog item).

### 2026-06-11 — OSS-over-hand-rolled plan (Owner idea #28): CM6 island, Split.js, synctex-js

**Decision (plan of record, docs/plans/2026-06-11-cm6-oss-migration.md):**
- **Migrate the LaTeX editor to CodeMirror 6** as a vanilla-JS Vite island (the islands build
  already exists), deleting ~200 lines of hand-rolled snippet-walker + 4 hint functions + the
  lint shim and removing 11 cdnjs script/CSS tags — which also **closes Backlog #114** (the
  editor dies offline). Native snippetCompletion / @codemirror/{autocomplete,search,lint},
  @replit/codemirror-vim, codemirror-lang-latex (all MIT). 3 vertical slices (A single-file
  parity → B multi-file + comments + lint → C cite B1/B2 parity). Likely drops emacs/sublime
  keymaps (not first-class in CM6) → Default + Vim.
- **Split.js** (MIT, ~2 KB, zero-dep) for the resizable/collapsible panels slice; onDragEnd →
  persist localStorage + view.requestMeasure().
- **synctex-js** (client-side, vendored) for the SyncTeX forward-jump slice; first add
  --synctex to writing/compile.py (pairs with #131 --keep-intermediates) and pdf.js TextLayer
  (#116). Deferred until after CM6.
- **Keep hand-rolled:** detex word count, difflib diff, the pet — replacing them would add a
  Perl/C runtime or weight for no gain (rule #28 is "borrow when clearly better", not always).
- **Sequencing:** CM6 sub-epic BEFORE the heavy Overleaf-UI cycles (it fixes the offline bug
  and gives Split.js/SyncTeX a clean view API). The cycle-121 error-log relocation was
  template-only and independent — already shipped.

**Alternatives considered:** stay on CM5 + just vendor it locally (fixes #114 only, keeps the
hand-rolled walker — kept as the fallback if CM6 is deferred); React island for the editor
(rejected — §2 keeps the editor vanilla; CM6 is framework-agnostic). split-grid (needs CSS
Grid); a hand-written/ported C synctex parser (rejected per #28).

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

308. ~~The `codemirror-lang-latex` package runs its own linter (missing `\documentclass`, per-file undefined `\ref`) whose underlines appear in the editor but never in the Problems panel, and whose per-file label check contradicts the cross-file one from #470 — either route its diagnostics through the panel with a `latex` tag or disable it in favour of `writing/lint.py` (idea added by #470)~~ (done 2026-09-12, #471: the package linter is off; its environment and brace checks live in writing/lint.py)
307. Port `mcp_server/` to the mcp 2.x API (FastMCP → MCPServer, transport changes) so the `<2` pin from Audit #25 can go; keep the 102-tool contract and the README/docs guards unchanged (idea added by Audit #25)
306. Library v2 slice 7 candidates: ~~inline PDF preview pane in the workbench (needs pdf.js vendored for offline desktop)~~ (the in-workbench reader); ~~per-reference reading notes + highlights surfaced in the detail pane~~ (both in the detail pane; swept 2026-09-07); ~~"Find PDF" per row with a status pill (done 2026-09-07, #386)~~; ~~drag-to-reorder for smart views (done 2026-09-07, #400)~~.
305. ~~Library v2 slice 6 (done 2026-09-06): duplicate clusters with a suggested keep, relation-preserving merge, Duplicates mode in the workbench, API + MCP. See the 2026-09-06 decision.~~
304. ~~Updater polish (done 2026-09-06, #370: progress events + bar, release notes confirm, 6-hourly re-check)~~ — original note: download progress in the sidebar control (the install closure has a chunk callback), release notes from latest.json shown before installing, a "check on a schedule" while the app is open (currently once per launch).
303. ~~In-app updates live (done 2026-09-06): keypair generated (public key committed, private key handed to the owner for the TAURI_SIGNING_PRIVATE_KEY secret), sign-when-secret CI logic, preview release published as a prerelease with asset pruning, silent launch check + one-click install + restart in the sidebar. See the 2026-09-06 decision.~~
302. Library, remaining vs. Paperpile/Zotero after slice 5: duplicate merge (keep links/PDF/tags), inline PDF preview pane in the workbench, ~~tag colours in the UI (done 2026-09-07, #381: swatches, rename, delete from the rail)~~, ~~drag-to-reorder smart views (done 2026-09-07, #400)~~, per-reference notes surfaced in the detail pane.
301. ~~Library v2 slice 5 (done 2026-09-06): LibraryTag + SavedView, rail sections (Smart views with "+ save", Tags with Untagged), bulk/detail tag editing, API + MCP. See the 2026-09-06 decision.~~
300. ~~Today list, later (⌘K `todo:` verb done 2026-09-06, #371; hero widget done 2026-09-07, #380; drag-to-reorder done 2026-09-07, #383; due times + sidebar nudge + carry-over count done 2026-09-07, #431).~~
299. ~~Today list (done 2026-09-06, owner request): core.TodoItem + /today page + sidebar entry + /api/v1/todos/ + MCP list/add/complete. See the 2026-09-06 decision.~~
298. Citations, later: a CSL-engine backend (citeproc-py) behind the same cite()/bibliography() contract for the long tail of styles; a "Cite" button on the Reference page and the PDF reader; citation export as RTF/Word-ready HTML.
297. ~~Library v2 slice 4 (done 2026-09-06): formatted citations in six styles + in-text forms + bibliographies; cite endpoints; MCP format_citations; Cite block in the detail pane and Copy citations in the bulk bar; volume/issue/pages carried from Crossref/OpenAlex. See the 2026-09-06 decision.~~
296. Library v2 slice 4 candidates (judge after slice 3): (a) reference tags + smart lists (saved filter views in the rail), (b) duplicate merge (the bib report flags duplicates; merging keeps links/PDF/notes), (c) per-reference notes + highlight summary surfaced in the detail pane, (d) inline PDF preview pane in the workbench, (e) "Find PDF" per row with a status pill after fetch.
295. ~~Library v2 slice 3 (done 2026-09-06): discovery lenses (similar / cites / cited-by) with one-click add in the detail pane, export .bib for selection/view + copy BibTeX, bulk Fetch OA PDFs; MCP discover_related + export_bibtex. See the 2026-09-06 decision.~~
295. Library v2 slice 3 candidates (pick the most "finally" one): (a) PDF-first reading flow from the workbench — open the reader in the detail pane with highlights → notes; (b) smart collections / saved filters ("unread 2024 in Project X", "no PDF yet") pinned to the rail; (c) "find PDFs for all" (OA fetch) as a bulk action + per-row OA badge; (d) author facet + author pages; (e) Zotero collections → projects mapping on import; (f) BibTeX/CSL export of any filtered selection (respecting facets) — Paperpile-style "export what I see".
294. ~~Library v2 slice 2 — the workbench (done 2026-09-06): facets | list | detail; whole-page drop zone; import panel (files + paste + link-to-project) with per-item results; keyboard j/k/enter/x/o; multi-select bulk bar (link, status, find metadata, delete); year histogram; needs-metadata recovery via DOI/arXiv/Crossref title search; load-more pagination; `projects` on every reference. API: `/references/facets/`, list filters + sorts (NULLs last), `/references/bulk/`, `/references/{id}/find-metadata/`. Screenshots in README.~~
294. Library v2 slice 2 — the workbench UI: three-pane Library (facets | list | detail), drop-anything import zone with per-file progress, keyboard j/k/enter/x, multi-select bulk actions (link to project, reading status, priority, delete), "find metadata" for needs_metadata stubs, sort/filters, load-more pagination. Backend: `/references/facets/`, list filters (year, has_pdf, entry_type, venue, sort), `/references/bulk/`.
293. ~~Library v2 slice 1 — import engine (done 2026-09-06): CSL-JSON/RIS/BibTeX/PDF/Zotero-local through one dedupe path; import + import-zotero API; MCP tools. See the 2026-09-06 decision.~~
292. Observatory, second pass: bespoke treatment for the pages a video lingers on — ~~Project Overview (constellation of that project's references + notes as the header — done 2026-09-07, #387)~~, ~~the Plan (phases as an orbital timeline — done 2026-09-07, #392)~~, ~~the Library (cover-style reference cards — done 2026-09-07, #397)~~, and the 3D graph page (Observatory palette for nodes/links, bloom). Also vendor 3d-force-graph so the graph works offline in the desktop app.
291. ~~Observatory visual identity (done 2026-09-06): dark-by-default tokens re-skinning every page, aurora + star grain, glass panels, vendored Inter/Space Grotesk, constellation canvas on the dashboard hero and login, icon rail with ⌘K spotlight, spotlight command bar, orbit-ring progress, time-aware greeting. Plan API now returns project_name/project_color (the SPA plan page had an empty breadcrumb and an invisible progress bar). See the 2026-09-06 decision.~~
289. ~~Desktop ↔ Claude Code, zero-config (done 2026-09-06): API key minted+persisted in the desktop data dir; `server.json` with the live URL; `atlas-mcp` (frozen MCP server) shipped in the installer and discovering both by itself; "Connect Claude Code" page with the exact `claude mcp add` line per install; friendly "is the Atlas app running?" tool error. See the 2026-09-06 decision.~~
290. ~~Connect page: a live "test the connection" button (done 2026-09-06, #369: four server-side checks, MCP `--check`)~~ — original note: (server-side: spawn the MCP server? no — call the API with the key and report; client-side can't reach the CLI). Low priority; `claude mcp list` covers it.
288. ~~(Retried 2026-09-07, #405 — red again: linuxdeploy fails on the PyInstaller payload too. Closed.)~~ AppImage retry — it was dropped (#210f) because linuxdeploy could not relink the bundled Postgres `.so`s; with Postgres gone (#286) the only native libs are PyInstaller's, so adding `appimage` back to `bundle.targets` may just work. One CI experiment on a branch; keep .deb/.rpm regardless.
287. macOS desktop build — add `macos-latest` to the desktop-release matrix (Tauri + PyInstaller both support it; the frozen server needs the same Tailwind + freeze steps). Unsigned .dmg will hit Gatekeeper ("damaged"/right-click Open) until notarization is set up, so document that alongside D3.
286. ~~Strip the dead Postgres bundling from the desktop app (done 2026-09-06, was parked as #268): removed the per-OS embedded-postgres CI steps, the `resources/pg` bundle resource, ATLAS_PG_BIN in the shell, postgres.exe in the NSIS hooks, the Postgres/MSVCR120 advice on the diagnostic page, and `core/desktop_runtime.py` + its 12 tests. Added `choose_port` (8000 else a free port) so a dev `runserver` no longer breaks the launch, with CSRF origins following ATLAS_PORT; a real `run_desktop --setup-only` test on a fresh SQLite data dir; desktop README rewritten (it still said the server was "NOT YET" bundled). Frozen binary verified end to end on :8077 (login 302→200, CSRF POST 302, foreign Origin 403). See the 2026-09-06 decision.~~
285. ~~(Retired 2026-09-07: the classic dashboard is no longer the front door; the SPA's calm mode covers its own chrome.)~~ Adopt `calm:hidden` on more secondary chrome (follows #275) — now that the `.calm` variant exists, quiet the remaining noise sources in calm mode: the classic dashboard's activity heatmap, the figure-gallery per-image counts, and any "X this month" stat figures on the classic overview. One class each, no new state. Could also add a tiny "Calm" affordance to the classic base.html so calm mode is discoverable outside the SPA dashboard (idea added by the cycle that shipped #275, 2026-06-17).
284. ~~⌘K palette recents (done 2026-09-06, #371: "Recent jumps" from localStorage, 6 entries)~~ — original note: ⌘K palette recents/empty-state — when the query is empty the palette shows the "Actions" + page-context block, but not the user's recent jumps. A short "Recent" group (last 3-4 navigations, persisted to localStorage like the classic base.html search-recents already does) would make reopening ⌘K a one-keystroke return to where you were. Pairs with the new group-header rendering (#279) (idea added by the cycle that shipped #279's header, 2026-06-17).
283. ~~Extend ErrorState to the secondary pages (done 2026-06-17): wired the retryable error state into Decisions, Timeline, Figures, Inbox, and Review (the latter previously masked a failed load as a perpetual "Assembling your week…"). 16 SPA pages now share the error state; guard asserts all 16. Chose this lower-risk coverage pass over the #282 render-prop refactor (rollback frequency made churning 11 working pages unwise this cycle).~~
282. ~~(Shipped 2026-09-07, #409: `queryGate` + `QueryBoundary`, nine pages wired, guard test.)~~ A shared `<QueryBoundary>` (or `useQueryView`) wrapper — loading-skeleton + ErrorState are consistent but still hand-wired per page (every page repeats the isLoading/error/!data ladder, now 16×). A small wrapper taking the query result + a skeleton + a render fn would remove the boilerplate and guarantee no page forgets the error branch. Still-unwired: Graph, Reference detail, Research, Automations, ReadingFlow, NewProject. Do this as a careful refactor when the container is stable (idea updated by the cycle that shipped #283, 2026-06-17).
281. ~~Roll ErrorState into the primary pages (done 2026-06-17): wired the retryable ErrorState into the six main index/detail pages that previously had NO error branch at all (Projects, Library, Notes, Writing, Literature, Search) — a failed load on any of them now shows "Try again" instead of silently rendering empty or crashing. 11 pages total now on the shared error state. Guard strengthened to assert all 11 keep it.~~
280. ~~Retryable ErrorState component (done 2026-06-17): replaced the bare red "Couldn't load…" lines on the 6 highest-traffic SPA query failures (Dashboard, Documents, Files content + tree, ProjectOverview, Plan) with a shared, dark-aware ErrorState that offers a "Try again" button (refetch) — transient API hiccups recover in place, no full reload. Guard test asserts it's built + no page regresses to the bare pattern.~~
279. ~~More palette verbs (continuing #276/#277) — keep adding the safe, reversible actions the owner repeats: "Copy current project .bib", "Go to today's review", "New quick capture" (beyond the capture: prefix). (Done 2026-09-07, #391: those three plus warm-up, backup and the web inspector.)~~ Keep them side-effect-light so a mistaken Enter never destroys anything. ~~The "Commands" group header is DONE (2026-06-17): palette rows now show a section label per kind (Commands / Go to / Complete) inserted whenever the kind changes, so verbs read as actions distinct from navigation; guard asserts the header is built.~~ Remaining: the additional verbs themselves.
277. ~~"Toggle calm mode" palette verb (done 2026-06-17): ⌘K now offers it alongside "Toggle dark mode", discoverable by typing calm/focus/quiet/stats; flips the shared calm state and flashes the result.~~
278. ~~Calm mode live-updatable (done 2026-06-17): extracted frontend/src/app/calm.ts (readCalm/setCalm/toggleCalm + a useCalm() hook). setCalm persists AND dispatches a same-tab "atlas-calm-change" event; useCalm also listens to cross-tab `storage`. The dashboard now uses useCalm() so the palette verb (#277) flips it live without a remount.~~
276. ~~Surface the theme toggle in ⌘K (done 2026-06-17): the command palette now offers a "Toggle dark mode" verb (kind: "verb"), discoverable by typing dark/light/theme/appearance, flipping window.__toggleTheme() and flashing the resulting state. Verb matches rank above nav results. Guard test asserts the source + committed spa.js agree.~~
275. ~~Calm mode app-wide via a `.calm` class (done 2026-06-17): calm.ts now toggles a `.calm` on <html> (like `.dark`), the base/spa bootstrap scripts apply it before paint from the atlas-calm key, and a `@custom-variant calm` lets any surface use `calm:hidden`. First adopter: the SPA sidebar pet's speech bubble is quieted in calm mode (the pet stays, its chatter goes). Guard asserts the variant compiles + the wiring. Now other dense chrome (classic dashboard heatmap, figure-gallery counts) can opt in with one class.~~
274. ~~Calm mode for the dashboard (done 2026-06-17): a zero-config, localStorage-persisted ("atlas-calm") "Calm mode / Full view" toggle on the SPA dashboard header that hides the monthly vanity stats grid (papers read / notes written / milestones done / inbox count), leaving the actionable surfaces — Needs attention + Active projects + Deadlines + Upcoming milestones. Same no-settings-page pattern as #273's theme. Guard test asserts the source + committed Dashboard-chunk agree (bundle was rebuilt). Scope note: SPA-dashboard-only; #275 parks promoting it to an app-wide body class.~~
273. ~~Theme follows the OS by default (done 2026-06-17): now that dark mode is complete app-wide (#270), the bootstrap in base.html/spa.html/login.html resolves to explicit-saved-choice-else-OS-prefers-color-scheme instead of strict opt-in; the toggle still records an explicit override and we track OS changes live when no choice is stored. The standalone login page (the desktop app's first screen) previously had no theme script at all, so it was always light despite its dark: variants — now fixed. Guard test asserts all three templates consult prefers-color-scheme and the old opt-in comment is gone.~~
269. ~~Desktop app had no CSS (fixed 2026-06-17): the owner's SQLite build launched (saga over!) but rendered an UNSTYLED login page. Cause: static/css/app.css is a gitignored build artifact (Tailwind output) and the desktop-release CI never built it, so the frozen bundle shipped no stylesheet. Fix: a 'Build Tailwind CSS' workflow step (downloads the Tailwind standalone CLI for the runner OS, compiles assets/css/app.css -> static/css/app.css --minify) BEFORE the freeze that bundles static/. Verified the build locally (Tailwind v4.3.0, 47KB); guard test asserts the step exists and precedes the freeze. Pushing rebuilds the installer WITH styling.~~
267. ~~Auto-clean the old Postgres data dir on the SQLite desktop (done 2026-06-17, owner asked for an updated installable build): run_desktop now rmtree's the stale pgdata/ + pgsock/ and deletes postgres.log from the data dir on startup, so a machine upgrading from the bundled-Postgres build to SQLite is cleaned automatically (no manual %APPDATA% wipe) and reclaims space. No-op on a fresh install. Verified the SQLite setup still completes with a stale pgdata present; guard test. This also re-triggers the desktop-release build so GitHub's desktop-preview has a fresh SQLite installer.~~ NOTE: still parked — strip the now-DEAD Postgres *bundling* (the pg binaries in spec/CI + desktop_runtime.py + ATLAS_PG_BIN in the Rust shell) to shrink the installer (#268).
266. ~~Desktop → SQLite (done 2026-06-17, owner-authorized: "if you see no fast solution then lets go sqlite!"). After a multi-day bundled-Postgres-on-Windows saga — each #265 diagnostic revealed a NEW Windows-specific Postgres bug (initdb exit 1, missing client tools, \\?\ prefix, console 0xC000013A crash loop, slow collectstatic, windowed stdin, psycopg connect hang, and finally a pg_ctl capture_output pipe-inheritance hang) — we switched the desktop app to SQLite, what every other single-user desktop app (Zotero, Obsidian, VS Code, Signal…) uses. config/settings/desktop.py now uses django.db.backends.sqlite3 (a file in the data dir, WAL mode); run_desktop dropped the ensure_postgres bring-up (migrate just creates the file → instant startup, no server/initdb/connection step). Postgres-only features degrade cleanly: the 4 trigram GinIndex migrations now use core.migration_ops.PostgresAddIndex (creates the index on Postgres, no-ops on SQLite — TrigramExtension already no-ops), and global search already falls back to icontains off Postgres (core/search.py). The web/server deployment keeps Postgres unchanged. Verified: fresh-SQLite migrate + check + run_desktop setup-only (195 static files, superuser, "Setup complete"); Postgres trigram search tests still pass. Parked #267 (strip the now-dead Postgres bundling — desktop_runtime.py + the pg binaries in the spec/CI + ATLAS_PG_BIN in the Rust shell — to shrink the installer).~~
265. ~~Owner desktop hang: instrument ensure_postgres (done 2026-06-17): the #263 diagnostic page worked — it showed Postgres UP/ready on 5433 but atlas-server.log EMPTY + 10-min timeout. Root cause: ensure_postgres was silent and wedged in the psycopg wait loop (libpq connect_timeout likely ignored on Windows → an unbounded silent block). Fix: flushed _log() at every step (never empty again) + a raw-socket _wait_for_tcp() precheck + a ThreadPoolExecutor-bounded psycopg connect (20s, shutdown(wait=False)) so a wedged connect RAISES (→ fast diagnostic) instead of hanging. Guard test. Remaining: confirm from the owner's NEXT diagnostic whether psycopg now connects (if it still times out at the bounded connect, the issue is libpq/psycopg in the frozen build — investigate the bundled libpq).~~
264. ~~AUDIT #24 (done 2026-06-16): full security+responsiveness pass — writable Protocol API is auth-gated/project-scoped/forge-proof; deps clean (starlette was a stale-venv false alarm, uv sync fixed); FIXED protocol_list O(n)→O(1) queries (load once + in-memory superseded set + lineage_cached, History gated on lineage_cached not the lazy .parent FK) + N+1 guard test. AUDITS.md #24 written.~~ Audit-cadence note: every ~10 slices → AUDITS.md; next ≈ AUDIT #25.
263. ~~Owner Windows desktop: show failures in-window (done 2026-06-16): the bundled-server launch failed silently behind WebView2's blank "can't reach this page", so we were debugging blind for many cycles. main.rs now opens a local splash, then a bg watcher navigates to the app on success or to a file:// diagnostic page (real atlas-server.log + postgres.log tails + data-dir + the VC++2013/MSVCR120 fix) on early child-exit or timeout. server.rs: tail_file + escape_html. cargo check clean; guard test. Build 0e012f2 green. Likely root cause surfaced by web search: missing Microsoft Visual C++ 2013 Redistributable (zonky pg binaries need MSVCR120.dll). Remaining: if the owner's diagnostic screenshot shows a different failure, fix that next.~~
262. Protocols on the SPA Research page (follow-on to #260): the React Research.tsx page lists hypotheses/experiments/datasets read-only (writes go to the classic pages); add a read-only "Protocols" section listing current protocols (GET /protocols/?project=) with their v{n} badge, mirroring the datasets section + the "add & edit on the classic page" affordance. ~~(Provenance half DONE 2026-06-16: ExperimentEntry.protocol FK (SET_NULL) → an entry records the exact protocol *version* it followed; scoped dropdown in the form, "Protocol: Title vN" link on the experiment log → #protocol-{pk}, protocol+protocol_label in the API, select_related to avoid N+1. Migration 0004; live-verified; 5 tests.)~~ ~~(SPA section DONE 2026-06-17: Research.tsx now has a read-only Protocols section listing the current protocols (GET /protocols/?project=, filtered to is_current) with a v{n} badge, mirroring the datasets section; empty state links to the classic page to write one. tsc clean, bundle rebuilt.)~~ #262 complete.
261. ~~MCP tool-list drift (done 2026-06-16): the README "Tools:" list had drifted (missing all 11 manuscript/LaTeX tools + get_timeline) and the intro said "16 tools" when there are 37. Rewrote the README list (grouped by area) to cover every tool + fixed the count, and added mcp_server/tests/test_docs.py: it parses the @mcp.tool() function names from server.py and fails if any is undocumented or the count is wrong — so it can't silently drift again. 2 guard tests.~~ NOTE: there are 37 MCP tools but the spec §6 only mandated ~12; the tool set grew with the API (manuscripts, prompts, templates, file-workspace, figures-adjacent, protocols).
260. ~~Protocol library UI (done 2026-06-16): a classic Research-tab page (templates/research/protocols.html, mirroring datasets.html) reachable at /projects/{slug}/research/protocols/ — lists the current protocols (is_current head of each chain), each with a v{n} badge, markdown-rendered body, a "New version" link, and a History disclosure (Protocol.lineage walks the parent chain). research/views.protocol_list + ProtocolCreateView + protocol_new_version (GET prefills from the current version, POST appends a new version); ProtocolForm; 3 urls; a Protocols tab in research/_tabs.html. The research pages are the canonical create/edit surface (the SPA Research page links to them). 4 tests (lineage + list-shows-current + create + new-version). The SPA read-only section is parked as #262.~~
259. Richer commit linking (follow-on to #4): optionally fetch the commit's message/author/date from the GitHub/GitLab API (behind a huey task, cached on the entry) so the experiment log shows the commit subject, not just owner/repo@sha. Needs network + handling private repos/tokens — keep it opt-in and offline-tolerant. Also: a reverse "experiments touching this repo" view. Deferred — the pasted-URL link already covers the 80% (idea added during #4)
258. ~~Figure count on the project overview (done 2026-06-17): added "figures" to the overview API counts dict — one COUNT on documents with content_type in PREVIEWABLE_IMAGE_TYPES (the exact figures-feed whitelist, SVG excluded). The SPA overview already renders counts generically (Object.entries(data.counts)), so it appears automatically as a "figures N" stat; bumped the counts grid lg:grid-cols-7→8 so all 8 fit one row. Backend test asserts figures counts only images; live-verified; schema clean.~~
257. ~~Make the Figures page discoverable (done 2026-06-16): three entry points — (1) a "View as gallery →" link on the SPA Documents page header (where images are uploaded); (2) a page-aware "Figures" quick-action in the command bar / assistant context (core/assistant._actions, in-project), pointing at the SPA path /projects/{slug}/figures/; (3) registered `figures` in links.ts toSpaUrl so that action (and any classic link) navigates SPA-internally without a reload. Also fixed a latent UP017 lint in core/calendar.py (dt_timezone.utc → datetime.UTC) the newer ruff now flags. Assistant test asserts the Figures action + url; tsc clean, bundle rebuilt.~~
256. ~~Figure-gallery UI page (done 2026-06-16): app/pages/Figures.tsx — a calm React grid that fetches /projects/{slug}/figures/, groups thumbnails by folder, offers a tag-filter chip row, and opens a click-to-lightbox (full image + download/close) over each figure's nosniff'd raw_url. Empty state points to Documents. Wired the route in main.tsx + a Figures quick-link on ProjectOverview. tsc clean (0 errors; the 32 pre-existing src/editor errors were just an incomplete node_modules — npm ci fixed them), vite build regenerated spa.js + Figures-chunk.js, the route is in the bundle, and the /figures/ data was live-verified end-to-end in #8-data. Frontend slice; built artifacts committed.~~
255. The three inline/download file responses (document_download, document_preview, api raw) now all hand-set `Cache-Control: private, max-age=86400` + (where inline) nosniff. If a fourth file-serving path appears, a tiny `cacheable_file_response(handle, content_type, *, inline)` helper in documents/ would keep the immutability/cache/nosniff contract in one place (pairs with the #251 inline-safety helper idea). Low priority (idea added during #254)
254. ~~Cache-Control on the API raw inline endpoint (done 2026-06-16): DocumentViewSet.raw set nosniff but no Cache-Control, while document_download/document_preview both cache the same immutable files for a day — so the workspace PDF/image preview re-downloaded every view. Added `Cache-Control: private, max-age=86400` (uploads are immutable; edits create new files), matching the other two paths; extended the raw test to assert it. AUDIT #23 follow-on.~~
253. ~~(Done 2026-09-07, #401: a read-only, rotatable feed token in the `?key=` URL.) Subscribable calendar feed (follow-on to #9's calendar half): the .ics endpoint authes via the X-API-Key *header*, but real calendar apps (Google/Apple/Outlook) subscribe by URL and can't send custom headers. A read-only, revocable per-user feed token in the path (e.g. /calendar/{token}.ics, login_not_required, constant-time compared, scoped to deadlines only) would make it actually subscribable. Defer until after AUDIT #23 since it adds a URL-bearing credential — design the token rotation/scoping carefully (idea added during #9-calendar)~~
252. The doctor's worker/redis, static-css, optional-components (Tectonic/Piper), and media+api-key blocks are still inline in handle() like the desktop block was before #208. If handle() keeps growing, the same extract-to-_check_X() treatment (a small ordered list of self.* section methods) would keep it a readable table of contents. Low priority — only worth it if another section accretes sub-checks (idea added during #208)
~~251. Centralize the inline-preview safety contract: both paths (documents.views.document_preview #249 and api DocumentViewSet.raw #250) now independently (a) allowlist a content type and (b) confirm magic bytes before serving inline. A tiny shared helper — e.g. documents.preview.inline_response(file, declared_type) returning a nosniff FileResponse or None — would make the rule live in one place so a future third inline surface can't forget the byte check. Low priority; revisit if a third inline path appears (idea added during #250)~~ (done 2026-09-07, #434: both paths return through `core/files.py::file_response`)
250. ~~Sniff bytes on the API raw inline endpoint too (done 2026-06-16): DocumentViewSet.raw picked its inline content_type purely from the file extension (.png → image/png) and never checked the bytes — the same mismatch class #249 closed for the document preview. It now reads the head, confirms it (sniff_image_type for rasters, a `%PDF-` check for PDFs), and 404s if the bytes don't match the extension-claimed type, so a mislabeled file (html named .png) can't reach the inline path. Reused documents.models.sniff_image_type; updated the existing raw test to a full PNG signature + added a mislabeled-extension 404 test.~~
224. ~~Windows desktop "127.0.0.1 refused to connect" (fixed 2026-06-14): the owner's install launched but the bundled server never served. Root cause: ensure_postgres passed `-k <socket_dir>` (a unix-socket path) inside pg_ctl's space-split `-o` string — Windows has no such socket and a username with a space splits the arg, so `pg_ctl start` failed, crashed run_desktop, and the window hit a blank ERR_CONNECTION_REFUSED. Fix: only pass `-k` on POSIX (the app connects over TCP loopback everywhere anyway); on a start failure raise a RuntimeError carrying postgres.log's tail; and tee the frozen server's stdout/stderr to <data-dir>/atlas-server.log (the windowed build has no console, so crashes were invisible — this also stops a stray print crashing on a None stdout). Pushing this rebuilds the installer for the owner to retry; 2 guard tests. (Can't run Windows here — fix is by code reasoning + the new log will confirm/deny if it persists.)~~
225. ~~Windows initdb.exe exits 1 (in progress 2026-06-14, #228): the atlas-server.log (the #224 logging worked!) showed initdb.exe runs but exits status 1 — so #224's socket fix was for a later step; the real failure is initdb itself, and my code didn't surface its stderr. #228 fixes three things: (1) _run now raises RuntimeError WITH stdout+stderr for EVERY pg helper, so the next log shows initdb's actual complaint; (2) a half-built pgdata (no PG_VERSION) from prior failed runs is rmtree'd before initdb (else "directory not empty" fails every retry); (3) the `\\?\` extended-length prefix Tauri puts on the binary path is stripped (initdb mis-resolves its share/ dir from it). Pushing rebuilds the installer. If still failing, the next atlas-server.log will name the exact initdb error.~~ Remaining for #225: main.rs should show a friendly in-app error page (with the log path) instead of the raw browser refused-to-connect.
229. ~~CI didn't rebuild on desktop server Python changes (fixed 2026-06-14): #228's fix lived in core/desktop_runtime.py, but desktop-release.yml's push paths were `desktop/**` + the workflow file only — so the installer never rebuilt and the owner would have re-tested an unchanged binary. The frozen server bundles core/desktop_runtime.py, run_desktop.py, config/settings/desktop.py and pyproject.toml, so those are now in the trigger paths (guard test added). I lack workflow_dispatch permission (403), so editing the workflow — which is in its own paths — is how I kick a build for a non-desktop/ change. (Broader app-model changes still won't auto-rebuild the desktop bundle; acceptable — those rarely need a desktop-only reship, and a version tag always rebuilds.)~~
231. ~~Windows: bundled Postgres has no client tools (fixed 2026-06-14, THE root cause): the owner's log proved #228's `\\?\` strip fixed initdb (it now succeeds) — the failure moved to `pg_isready not found`. The zonky windows-amd64 16.4.0 bundle ships ONLY initdb.exe/pg_ctl.exe/postgres.exe; NOT pg_isready/psql/createdb/createuser (verified by extracting the jar). ensure_postgres shelled out to pg_isready (wait), psql (db-exists), createdb (create) — all absent on Windows. Fix: do the readiness wait + `SELECT 1 FROM pg_database` + `CREATE DATABASE` through psycopg (already in the frozen server; migrate needs it) — no client-tool dependency, cross-platform (psycopg uses TCP loopback). Live-verified the wait+ensure logic end-to-end on the dev Postgres (create-if-missing + idempotent). Guard test forbids _pg_bin("pg_isready"/"psql"/"createdb"). The whole Windows saga was one onion: initdb-not-found(#210) → unix socket(#224) → \\?\ prefix(#228) → missing client tools(#231); no Windows machine needed — owner logs + jar inspection + live psycopg test diagnosed each.~~
211. ~~(AUDIT #20) Tighten the bundled-Postgres auth — trust-auth on 127.0.0.1 lets any local process reach the desktop DB without a password (fine for single-user, matches file ownership). A unix-socket-only listener or a generated password would harden it; low priority (idea added by AUDIT #20)~~ (struck 2026-09-07, sweep #467: obsolete — the bundled Postgres was replaced by SQLite (#266); there is no local DB listener)

### ★ #210 post-ship fixes (owner ran the Windows installer, 2026-06-14)
- **210-fix1 ✅ Windows "initdb not found" crash:** the installer launched + the frozen server ran, but `_pg_bin` looked for `initdb` while Windows ships `initdb.exe`. Fixed: `_pg_bin` now checks both `<name>` and `<name>.exe` and searches both ATLAS_PG_BIN and ATLAS_PG_BIN/bin; main.rs passes the pg ROOT (resource_dir/pg) so the bin/ fallback covers any layout. 2 new tests (.exe + bin-subdir). The frozen server + Tauri launch worked — this was the last runtime gap.
- **210-fix2 ✅ Single instance (owner: "don't open 10 windows"):** added tauri-plugin-single-instance as the FIRST plugin — a second launch focuses/unminimizes the existing window and exits. Critical here: each instance would start its own Postgres on the same data dir and corrupt it. cargo check passes.

### ★ OWNER-REQUESTED EPIC (2026-06-14) — Desktop distribution & auto-update (HIGH PRIORITY, do next)
Owner: "I want button for updating the app as well once I installed it; moreover I want ready-to-install stuff for Linux and Windows!" Two paired pieces (the updater needs a release feed the CI produces):
- **D1. ✅ Ready-to-install installers (Linux + Windows) — DONE 2026-06-14.** tauri.conf.json bundle targets set explicitly to [deb, appimage, rpm, nsis, msi] + publisher/category/descriptions; new .github/workflows/desktop-release.yml (tag v* or manual dispatch; ubuntu-22.04 + windows-latest matrix; installs webkit/gtk deps; tauri-apps/tauri-action builds + bundles + uploads to a DRAFT GitHub Release); desktop/README.md "Download / install" section. cargo check passes (restored webkit2gtk dev deps the rollback wiped); workflow + conf validated (yaml/json); 2 new scaffold guard tests (targets + workflow). The real binaries are produced by CI on a version tag — can't build a GUI/installer in this headless container.
- **D2. ✅ In-app "Check for updates" / auto-update button — DONE 2026-06-14.** Added tauri-plugin-updater (Cargo + serde_json) + registered the plugin in main.rs + a `check_for_updates` command (updater.rs: checks the GH Releases feed, downloads+installs, returns the new version) + `updater:default` capability + tauri.conf plugins.updater (endpoints → releases/latest/download/latest.json, pubkey placeholder) + withGlobalTauri. Frontend: UpdaterButton.tsx — a desktop-only ("__TAURI__" in window) SPA sidebar control with idle/checking/up-to-date/update-ready(restart)/error states; renders null in the browser. createUpdaterArtifacts kept FALSE so D1's installers keep building until the owner does the one-time keypair setup (documented in README: generate keypair, set pubkey, flip the flag, add TAURI_SIGNING_PRIVATE_KEY secret). cargo check + tsc pass; SPA verified clean; guard test asserts the whole chain is wired. The button itself can only be exercised in a real desktop build (headless container can't).
- **D2b. ✅ Update button actually restarts the app — DONE 2026-06-14.** The "Update ready — restart" button only did `window.location.reload()`, which reloads the webview but leaves the old process (and the old bundled server) running, so a freshly-installed update never took effect. Added a `restart_app` Tauri command (updater.rs: `app.restart()` — re-execs the new binary, diverges) registered in main.rs; UpdaterButton.tsx now invokes it instead of reloading. cargo check + tsc + 694 pytest green; scaffold guard asserts restart_app is exposed in main.rs/updater.rs (`app.restart()`) and the button calls it (not location.reload). Exercisable only in a real desktop build.
- Sequence: D1 (release feed + installers) ✅ → D2 (updater) ✅ → D2b (real restart) ✅. OSS-only (Tauri updater + GitHub Releases). REMAINING: owner's one-time signing setup to activate live auto-update (backlog D3).
- D2c idea (added during D2b): the updater downloads silently with a no-op progress callback — for a large bundled-Postgres build that's a long opaque wait. A future slice could surface download progress (emit a Tauri event from the `download_and_install` progress closure → a small progress bar in UpdaterButton) so "Checking…" doesn't look hung.

205. ~~Empty-state action sweep (done 2026-06-15): audited every border-dashed empty block; all had a primary action EXCEPT the reading queue, which showed "everything has been read" even on a fresh project with zero references — misleading + dead-end. Now branches on has_references: no refs → "No references are linked yet" + "Link a reference" action; refs all read → the (legitimately action-free) "Queue is clear" terminal state. exists() is one constant query, so the #226 N+1 guard still holds. 2 tests. The other empty states were already actioned.~~
204. ~~Writing board empty-state action (done 2026-06-14): _board.html's {% empty %} now renders an optional empty_action_url/label; the per-project Writing board offers "Start a manuscript" (writing:create) and the global Writing home offers "Go to a project". Honors the product guideline that every empty state offers its primary action. Live-verified on a fresh project; test asserts the action + create URL.~~
207. ~~Research-section density (done 2026-06-14): the three research tabs (ledger, datasets, experiments — which share a tab bar) widened to base_wide max-w-6xl + header mb-6→4 so switching tabs no longer jumps width; the datasets registry table (Name/Location/Checksum, a genuine wide table the #25 sweep hadn't reached) got py-2→1.5. All 3 added to the base_wide guard list. Live-verified 200 at width 1056, no JS errors.~~
### ★ OWNER EPIC #210 — Self-contained desktop app (IN PROGRESS, top priority)
Owner installed the app and hit "localhost refused to connect" — the shell needs the Atlas server running on their machine, which they don't have. Make the installed app stand alone. Plan (SQLite + Python sidecar, no Docker/Postgres/Redis):
- **★ OWNER DECISION (2026-06-14, via AskUserQuestion): BUNDLE FULL POSTGRES, not SQLite** — "no need to migrate stuff to sql, just make it install automatically". Full parity (incl. FTS); the app ships + auto-starts Postgres. The SQLite work (210a/b stay as harmless fallbacks) pivoted to bundled-Postgres below. Redis stays OUT (huey immediate) — only the DB is bundled.
- **210a. ✅ Desktop settings (done 2026-06-14):** config/settings/desktop.py — huey immediate (MemoryHuey, no Redis), WhiteNoise static, persisted SECRET_KEY, DEBUG off, DATA_DIR in ATLAS_DATA_DIR. (DB pivoted from SQLite → bundled Postgres per the owner decision, see #210g.)
- **210g. ✅ Bundled-Postgres lifecycle (done 2026-06-14):** desktop.py points at a LOCAL postgres (127.0.0.1:ATLAS_PG_PORT 5433, trust auth, user/db 'atlas'); core/desktop_runtime.py ensure_postgres() locates the binaries (ATLAS_PG_BIN → PATH → /usr/lib/postgresql/*/bin), runs initdb into ATLAS_DATA_DIR/pgdata on first launch, starts postgres (127.0.0.1 only, socket in the data dir), creates the atlas db, and registers an atexit fast-stop; run_desktop starts it before migrating. VERIFIED LIVE as a non-root user with the pg16 binaries: initdb→start→createdb→migrate→superuser all ran automatically ("Postgres is up." → "Created the Atlas login"). (postgres refuses to run as root, so the pytest suite guards the pieces, not the live initdb — that runs in the release CI.) 5 desktop tests.
- **210b. ✅ Search fallback (done 2026-06-14):** core/search.py now checks connection.vendor — non-Postgres (SQLite desktop) takes an icontains LIKE search over the same fields (shared _SEARCH_SPECS), returning the identical {type,object,project} shape; Postgres keeps full FTS + trigram. Verified end-to-end on the SQLite desktop settings (found a Reference) + a unit test. So global search works without Postgres (no ranking/typo-tolerance there, acceptable for single-user).
- **210c. ✅ run_desktop entrypoint (done 2026-06-14):** core/management/commands/run_desktop.py — migrate + collectstatic + ensure the single superuser (atlas/atlas, overridable via ATLAS_ADMIN_USER/PASSWORD) + serve with **waitress** (added as a dep; gunicorn is Unix-only so can't ship to Windows). `--setup-only` for tests. Verified LIVE end-to-end on SQLite: served the login page (200) + WhiteNoise static (200) on a port, no Postgres/Redis/Docker. The whole bundled server runs. 3 subprocess tests.
- **210d. ✅ PyInstaller freeze (done 2026-06-14):** desktop/server/atlas_server.py (frozen entrypoint → run_desktop under desktop settings) + atlas_server.spec (collects every local app + django/waitress/whitenoise/drf submodules, bundles templates/ + static/ at the frozen root where BASE_DIR resolves). Gotcha fixed: collect_submodules runs before pathex, so the spec does sys.path.insert(0, ROOT) first. BUILT ON LINUX + RAN STANDALONE: the 14MB atlas-server binary served the login page (200) + WhiteNoise static (200) on a fresh SQLite db with no Python/Postgres/Redis installed. pyinstaller added as a build-only dep group; build artifacts gitignored; structural guard test + a build README. Windows/macOS freeze on their own CI runners (no cross-compile) → 210f.
- **210e. ✅ Tauri server wiring (done 2026-06-14):** desktop/src/server.rs (spawn the frozen atlas-server with ATLAS_DATA_DIR/ATLAS_PG_BIN/ATLAS_PORT + wait_for_port via TcpStream) and main.rs: on setup() resolve the server (ATLAS_SERVER_BIN env, else the bundled resource_dir/atlas-server + pg/bin), spawn it, wait up to 180s (first run does initdb+migrate), load the window at http://127.0.0.1:port/; on RunEvent::Exit kill the child. Dev (no bundled server) falls back to ATLAS_URL. desktop_runtime gained a best-effort stop-before-start so an orphaned Postgres from a hard-kill is reclaimed next launch. cargo check + 2 Rust wait_for_port tests pass. **FULL E2E PROVEN: the frozen atlas-server binary, run as a non-root user with the pg16 binaries, auto-started Postgres + migrated + served the login page (200) + shut Postgres down cleanly — a complete self-contained Atlas with zero infrastructure.**
- **210f + 210i. ✅ Installer assembly (done 2026-06-14):** desktop-release.yml now, before the tauri build, sets up Python+uv, `uv sync --group build`, freezes the server (pyinstaller atlas_server.spec → desktop/server/dist), and fetches the portable Postgres binaries per-OS from zonky embedded-postgres-binaries (Maven jar → .txz → desktop/resources/pg) — Linux + Windows steps. tauri.conf bundle.resources ships server/dist/atlas-server + resources/pg so they land in resource_dir (main.rs already resolves them). cargo check needs the resource paths to exist, so committed .gitkeep markers (the real artifacts are CI-fetched + gitignored). yaml/json valid, cargo check green, guard test. The real per-OS assembly runs on the CI runners — the desktop/** push auto-triggers it (watch + iterate via the Actions API). EPIC #210 is now feature-complete end-to-end; CI iteration may be needed for the cross-platform postgres/pyinstaller details.
- Tradeoffs (logged): SQLite not Postgres (fine for single-user; lose FTS → 210b), no Redis (immediate jobs), no Docker. Reversible — the dev/prod path is untouched.
- Owner walls that motivated this: (1) Windows Smart App Control blocks the unsigned .exe → needs code signing (Azure Trusted Signing / SignPath); (2) the connection-refused that this epic fixes.
209. ~~Prompts gallery count line (done 2026-06-14): "N prompts saved" / "N prompts matching the filter" footnote, matching the library + literature lists (#199 family). Pluralized, filter-aware. Test asserts both the saved-count and the filtered-count.~~
208. ~~Factor the doctor's desktop checks into `_check_desktop()` (done 2026-06-16): handle() had grown a ~30-line inline desktop-updater block; extracted it verbatim into Command._check_desktop(base) so handle() reads as a flat list of sections again. Behavior-preserving (the four existing doctor tests still pass through the full command); added two tests for the helper's previously-uncovered branches — the configured-green path and the no-tauri-conf skip.~~
DESKTOP-ICONS. ~~Full multi-resolution icon set (done 2026-06-14, while answering the owner's "is it installable?" — pushed fd9e159): generated 32/128/256 PNGs + a Windows .ico from the 512² source and listed them in bundle.icon, so the release build produces properly-iconed Linux + Windows installers (a single png would fail the Windows MSI/NSIS targets). Also confirmed I can't trigger the build from here — git proxy blocks tag pushes and the GH integration token is 403 for workflow_dispatch; the owner triggers it via the Actions "Run workflow" button / a tag / a local cargo tauri build.~~
206. ~~Doctor updater misconfig check (done 2026-06-14): doctor now distinguishes two states — placeholder pubkey + createUpdaterArtifacts OFF → warn (benign, not set up yet, #203); placeholder pubkey + createUpdaterArtifacts ON → FAIL (exit 1), because Tauri can't sign the artifacts so the release build would break. Test injects a misconfigured tauri.conf via a tmp BASE_DIR and asserts the failure + exit 1.~~
247. ~~Cite-checker handles \nocite (done 2026-06-15): CITE_RE matched \cite/\citep/\textcite/etc. but not \nocite{key} — a legitimate LaTeX command that includes a reference in the bibliography without an in-text citation. So a \nocite'd key was wrongly flagged as "uncited in bib". Added nocite to the alternation; \nocite{*} ("include everything") yields key "*", already skipped. Test covers \nocite{a,b} + \nocite{*}.~~
246. ~~Slow collectstatic timed out the window (done 2026-06-15): with #245's crash loop gone (no more black console — confirmed in the owner's screenshot), the window still showed refused-to-connect because the server hadn't bound :8000: first-run collectstatic under CompressedManifestStaticFilesStorage gzip+brotli-compresses + manifest-hashes every file, which takes minutes on Windows — longer than main.rs's 600s auto-reload poll. Switched the desktop staticfiles backend to plain django StaticFilesStorage (collectstatic just COPIES; WhiteNoise serves uncompressed, which is fine on localhost; no manifest = also robust to a missing {% static %} ref). Measured ~2s vs the compress/hash path. Now the server binds quickly and the window auto-reloads. Build 0.1.17; guard test asserts plain storage.~~
245. ~~Postgres 0xC000013A console-Ctrl+C crash loop — THE root cause (done 2026-06-15): the owner's postgres.log showed the logical-replication-launcher worker "terminated by exception 0xC000013A" (STATUS_CONTROL_C_EXIT) on repeat — Postgres was being Ctrl+C'd, crash-recovering, and hit again in an endless loop, so it never finished startup → empty atlas-server.log → 1-hour black hang. Root cause: atlas_server.spec had console=True, so the frozen server ran in the black console window, and the Postgres it spawned shared that console's control group; any console control event killed Postgres's background workers. Fix: console=False (windowed — also removes the black box; output already goes to atlas-server.log) + start the pg helpers with Windows creationflags CREATE_NEW_PROCESS_GROUP|CREATE_NO_WINDOW (_CREATIONFLAGS) so they're isolated from console signals entirely. This is the deepest layer of the whole saga and explains the hang the timeouts (#244) would only have surfaced, not cured. 16 desktop tests + guard. Build 0.1.16.~~
244. ~~Setup must not hang forever (done 2026-06-15): owner reported the server console black for 1 HOUR with the window unchanged — a true hang. The empty atlas-server.log localises it to ensure_postgres (the "Postgres is up." write never happened), most likely the old hung instance the #242 file-lock prevented replacing. Added timeouts so nothing blocks indefinitely: `_run` setdefault timeout=180 (wedged initdb/pg_ctl → RuntimeError), self-heal pg_ctl stop timeout=60, and psycopg connections carry options="-c statement_timeout=15000" (a stuck query times out). With verbosity=1 (#241), a hang now surfaces a clear error in the log within ~3 min instead of a black window. Guard test asserts the timeouts. Build 0.1.15.~~
242. ~~Installer file-lock on update (done 2026-06-15): owner's "Error opening file for writing: …pg\bin\postgres.exe" — a still-running atlas-server.exe + its child postgres.exe from a prior launch locked the binaries, so the NSIS installer couldn't overwrite them. The single-instance plugin guards the APP but not the spawned server/postgres if the app was force-closed. Added desktop/installer-hooks.nsh with NSIS_HOOK_PREINSTALL + PREUNINSTALL macros that `taskkill /F /T /IM atlas-server.exe` + `postgres.exe`, wired via bundle.windows.nsis.installerHooks — so an install/update over a running app just works. Guard test asserts the hook is wired + taskkills both. (Can't run the NSIS installer here; if the config is wrong the Windows build fails red and 0.1.13 stays — safe.) Workaround meanwhile: Task Manager → end those processes → reinstall, or click Ignore (postgres.exe is identical across builds).~~
243. ~~get_absolute_url for research-thinking models (done 2026-06-15, completes #240): after adding hypotheses/questions/experiments to search (#240), the API/MCP search serialized url=None for them (the generic serializer uses get_absolute_url, which they lacked). Added get_absolute_url to Hypothesis/ResearchQuestion/ExperimentEntry → their list page + a #hypothesis-/#question-/#experiment-{pk} deep-link anchor (matching id added to ledger/experiments/question_list templates so it scrolls). Simplified the search.html + _suggest.html branches to use get_absolute_url (the suggest dropdown's else-branch now handles all three). 1 API test (urls present + anchored). No migration.~~
241. ~~Desktop first-run: visible + faster (done 2026-06-15): owner's console showed atlas-server.exe alive but the window refused-to-connect — run_desktop ran migrate+collectstatic at verbosity=0 (silent → the "empty log" mystery) while the window loaded before serve() bound 8000. Fixed: verbosity=1 (log shows "migrating…/collecting…/Atlas is running"), and collectstatic is skipped on repeat launches of the SAME build via a .collected_version marker keyed on ATLAS_VERSION — server.rs passes env!(CARGO_PKG_VERSION), and CI now stamps desktop/Cargo.toml in lockstep with tauri.conf.json so the version actually changes per build (re-collects after an update). cargo check + tests pass. Pairs with 0.1.12's auto-reload: first launch slow-but-self-loading, later launches quick. (Note: a console window still shows — the frozen server is console=True; could go windowed later, but it's useful for "is it alive" right now.)~~
240. ~~Search covers the research-thinking tools (done 2026-06-15, completes #239): added Hypothesis (statement), ResearchQuestion (question), ExperimentEntry (title+body) to the FTS path + icontains fallback, with search.html branches linking to the ledger / questions / experiment-log pages, suggest-dropdown hrefs, and a header special-case so "hypothesis" reads "hypotheses". Global search now spans references, notes, documents, decisions, phases, milestones, manuscripts, hypotheses, questions, experiments. Live-verified (Load→hypothesis, Incentive→experiment; a stop-word like "Does" finds nothing, expected FTS behavior). 7 search tests.~~
203. ~~Doctor updater-pubkey warning (done 2026-06-14): `manage.py doctor` now reads desktop/tauri.conf.json and WARNs (not fails — exit 0) when the updater pubkey is still the REPLACE_ME placeholder, pointing at the desktop/README D3 steps; says "signing configured" once set. Surfaces the one-time owner step so a release isn't tagged expecting auto-update. Test covers the placeholder-warning + exit 0.~~
202. ~~CI npm-audit guard (resolved 2026-06-14, already covered): ci.yml's `audit` job runs `make audit` → scripts/audit.sh which already does `npm audit --omit=dev` and fails on any shipped-dep vuln (and pip-audit). The 0-vuln state from #159 is already CI-guarded. Closed as already-done.~~
D3. (Owner one-time) Activate live auto-update — generate the Tauri updater keypair, put the pubkey in tauri.conf, flip createUpdaterArtifacts to true, add TAURI_SIGNING_PRIVATE_KEY as a repo secret (steps in desktop/README). After that, tagged releases publish a signed latest.json and the in-app button does real updates. Not a code slice — owner action; could add a tiny doctor check that warns if the pubkey is still the placeholder (idea added during D2)
220. ~~"0 spectacular warnings" guard (done 2026-06-14): test_schema_generates_without_warnings runs `manage.py spectacular --fail-on-warn --validate` in a subprocess and asserts exit 0, so any future undocumented endpoint, unresolved type hint, or enum collision fails the suite instead of silently degrading the contract the MCP server reads. Locks in #218/#219. Mechanism proven (the same flag exits non-zero against the pre-#218 139 warnings).~~
227. ~~In-app image lightbox (done 2026-06-15, #227-followup): the DocumentsTable now shows IMAGE previews in an in-app lightbox (backdrop click or Esc to dismiss, with Download/Close) instead of leaving for a new tab; text previews still open a tab (an in-app text panel is more work for less value). Backed by a new Document.preview_kind ("image"/"text"/None) surfaced as previewKind in the props; the image src is the existing safe inline-serve endpoint (#227). is_previewable now derives from preview_kind. tsc + build clean; 2 backend tests + built-chunk verified.~~ Remaining idea: a tiny inline row thumbnail for images.
239. ~~Global search covers manuscripts (done 2026-06-15): search was built in Phase 3 (references/notes/documents/decisions/phases/milestones) and never extended to Phase-4+ types, so a researcher couldn't find their own paper. Added Manuscript (title^A + abstract) to the FTS path AND the _SEARCH_SPECS icontains fallback + a search.html result branch (it slots in cleanly: has get_absolute_url, __str__=title, pluralizes as "manuscripts", and the suggest dropdown's else-branch already handles it). Live-verified ("Strategic" → the real manuscript). Test added. NEXT (#240): hypotheses / research questions / experiments also belong in search but lack get_absolute_url and use non-title fields (statement/question/body), and "hypothesis"+s mis-pluralizes in the header — needs get_absolute_url on those models + per-type template branches in search.html AND _suggest.html + a header plural fix.~~
238. ~~Inbox triage count (done 2026-06-15): the quick-capture inbox now footnotes "N items to triage." (pluralized), matching the #199/#232 situational-awareness count pattern. Considered a global sidebar "Inbox · N" badge but a context processor would add a count query to every page (risking the budget guards) — kept it to the inbox page. Template-only; 1 test.~~
237. ~~"Mentioned but not yet written" stub list (done 2026-06-15, #236-fu): the notes list now shows a section of titles referenced via [[wiki-links]] across the project but not yet written, each a "+ Title" create-link (pre-filled, builds on #236). New services.unwritten_note_titles(project) — one query, case-insensitive, deduped, sorted. ALSO fixed a pre-existing N+1: the list ran note.incoming_links.count() per row → now annotate(backlink_count=Count(...)). 4 tests incl. an N+1 guard. Obsidian-style orphan/stub surfacing for the note web.~~
236. ~~Clickable unresolved wiki-links (done 2026-06-15): an unresolved [[Title]] in a note body used to render as dead italic text; now it renders as a "+ Title" link to the note-create form with the title pre-filled (`?title=`, NoteCreateView.get_initial) — Obsidian/Roam-style frictionless note creation. body_with_resolved_links emits the create-link; works in the live preview too (fake note has a real project). 2 tests (rendering + prefill); live-verified.~~
235. ~~Sniff magic bytes before inline preview (done 2026-06-15): document_preview trusted the browser-reported content_type stored at upload, so a forged/mislabeled file with an image content_type would be served `inline` as that image type (nosniff already blocked execution, but it was the only line of defense). Added documents.models.sniff_image_type(head) — checks the real PNG/JPEG/GIF/WebP/BMP magic signature — and the view now serves inline only when the bytes confirm a whitelisted raster type, else falls back to text/plain. The bytes win over the label. Unit test on the sniffer + a spoofed-image (html-as-png → text/plain) view test; updated the legit-image test to upload real PNG bytes.~~
234. ~~Pluralize overview count links (done 2026-06-15): "All {{ n }} documents/decisions →" on the project overview now uses |pluralize ("All 1 document →"). Swept all templates for `{{ number }} noun` without pluralize — these two were the only true bugs; the "X/Y milestones" progress ratios and the reading-queue "X/Y themes" coverage badge are the app's endorsed ratio idiom (UI guideline: "3/7 milestones"), left as-is. 1 guard test.~~
233. ~~Humanized manuscript deadline label (done 2026-06-15): the three deadline countdowns (board, manuscript detail, project overview) each hand-rolled the wording and had a "1 days"/"deadline passed" vs "N days ago" mismatch + a pluralization bug. Added Manuscript.deadline_label ("due today" / "N days left" / "overdue by N days", correctly singular at 1) + deadline_is_soon (<7d incl. overdue, the red cue); all three templates now use them. Parametrized property tests cover every case; updated the one existing overview assertion. DRY + consistent + grammatical.~~
232. ~~Count lines on decisions + questions lists (done 2026-06-15): extended the #199 situational-awareness pattern — the per-project decision log now footnotes "N decisions recorded." and the research-questions list "N research questions." (pluralized). Calm "where is what, how is it going" cue (product value #1). Template-only, guarded by the non-empty branch; 2 tests.~~
226. ~~More N+1 guards (done 2026-06-14): added constant-N guards for the reading queue and the review matrix — the two per-reference list/grid surfaces that were unguarded. (Check-before-building paid off: the dashboard, documents, library, overview, plan, and two APIs ALREADY had ceilings in test_query_budgets.py, so the idea's "dashboard" target was a stale premise.) Both confirmed flat — 8 refs cost no more queries than 3. The main app surfaces are now N+1-fenced.~~
228. ~~Review project-chip links (done 2026-06-14): on the cross-project /review page the milestone, decision, and experiment rows (plain divs) now link their project-name chip to that project's overview, using the project_slug added in #216. The paper and note rows stay as-is — their whole row is already a Link, so nesting a second Link would be invalid HTML. tsc + build clean; review chunk test still green.~~
221. The 0-warnings schema guard (#220) shells out to manage.py each run (~1-2s); if test time ever matters it could call the generator in-process via drf_spectacular's SchemaGenerator + drainage GENERATOR_STATS instead of a subprocess — lower priority, the subprocess is simpler and matches the desktop tests' pattern (idea added during #220)
223. ~~Query-budget guards for documents + literature (done 2026-06-14): both views now have an N+1 guard test that measures the warm query count with 3 rows, then asserts 8 rows cost no more — data-count-independent, so it catches a future per-row query added to _doc_row, the island props, or a filter, not just a fixed budget. Confirms AUDIT #21's "constant query" finding and locks it in (like the weekly_review(8) guard).~~
202. A CI/guard check that `npm audit --omit=dev` stays clean (now that #159 got it to 0) — a make target or test that fails if a shipped-dep advisory appears would catch the next one early without a manual audit (idea added during #159)
200. ~~Count line on the documents list (resolved 2026-06-14, no change needed): the DocumentsTable React island ALREADY conveys the count — the filter input placeholder reads "Filter N documents…" and a "N matches" badge appears while filtering. Adding a footnote would duplicate it. Closed as already-covered (the matrix could still get one if ever wanted, but it's a grid not a list).~~
199. ~~Count lines on the literature lists (done 2026-06-14): the per-project Literature list now footnotes "N references … (linked / matching the current filter)" and the reading queue "N papers still to read", matching the library index's existing count — a calm situational-awareness cue (product value #1). Pluralized; filter-aware. Test asserts the count renders; live-verified both (22 refs / 14 to-read).~~
194. The three "remember a list view" controls (library sort, project-lit order, queue order) all use a global session key — fine for single-user, but if a future control wants per-project memory, remembered_choice could take an optional namespace suffix (idea added during #193)
193. ~~Reading-queue order persistence (done 2026-06-14): the queue order (Priority / Fill matrix gaps) now persists via core.session.remembered_choice with a "priority"/"gaps" allow-list; the Priority pill links explicitly to ?order=priority so it always stores intent. Test asserts session["queue_order"] sticks; live-verified gaps stays active across a bare revisit.~~
192. ~~Validate ?sort= before storing it in the session (found by AUDIT #18, fixed 2026-06-14): folded into the #191 helper — remembered_choice only writes the value to the session when it's in the allow-list, so junk is never persisted (and is still re-validated on read). Test asserts a hostile ?sort= is neither returned nor stored.~~
191. ~~Session-remember helper (done 2026-06-14): core/session.py remembered_choice(request, param, session_key, allowed, default) centralizes the read-?param-or-restore-from-session dance with validate-before-store; library_index (#176) and project_literature (#190) both refactored onto it (net −~15 lines, identical behavior — existing round-trip tests stay green). 4 helper unit tests.~~
198. The documents page still issues ~3 folder-table queries (the cached list + a couple from current_folder lookup / tree template); diminishing returns now, but worth a glance if a future audit flags it (idea added during #197)
197. ~~Fold folder_tree's own query (done 2026-06-14): folder_tree(project, prefetched=None) takes an optional pre-loaded folder list; it had exactly one caller (documents_index), which now loads project.folders.all() ONCE and feeds it to the nested tree, the bulk-move select, and the row selects. Folder-table queries 4→3 (total 12→11); budget tightened 16→15. The fallback keeps folder_tree standalone-callable.~~
181. ~~Documents folder-query redundancy (done 2026-06-14): investigated the ~5 folder-table queries — folder_tree itself is already one query (builds nesting in memory, no N+1); the redundancy was the bulk-move <select> re-fetching project.folders.all despite the #180 cached `folders` context var. Pointed it at the cache: folder-table queries 5→4, total 13→12; tightened the budget test 18→16 to lock it in. Remaining duplicate (folder_tree's own query) split to #197.~~
180. ~~Documents move-`<select>` N+1 (found by AUDIT #17, fixed 2026-06-13): `_doc_row.html` re-queried `project.folders.all` per document row (10 folder-table q across ~5 rows, O(rows)). Fixed by passing one cached `list(project.folders.all())` from documents_index and iterating `folders|default:project.folders.all` so HTMX single-row swaps still fall back to a single query. Folder-table queries dropped 10→5 (now row-independent); a django_assert_max_num_queries(18) test with 5 folders × 15 docs guards the regression.~~
185. ~~Typeahead "no match" feedback — when the buffer matches nothing, the hint pill could flash red/shake briefly so it's clear the keystroke landed but found nothing, instead of silently holding focus (idea added during #168/#169) — done 2026-09-07, #402~~
184. ~~Extend the typeahead hint pattern to the classic documents/folder tree (HTMX) — the React Files tree now has it; the server-rendered tree could get a small JS sprinkle for parity (idea added during #168/#169) — classic-only; retired 2026-09-07~~
169. ~~Cancel typeahead on focus leave / Escape (done 2026-06-14): Escape clears a pending buffer (and is swallowed so it doesn't also collapse/deselect), and onBlur on the tree clears it, so returning to the tree never triggers a surprise jump from a stale buffer. DOM-verified: Escape removes the hint span.~~
168. ~~Active typeahead buffer hint (done 2026-06-14): the current buffer shows as a small dark mono pill in the tree's top-right while typing, auto-clearing 1s after the last keystroke (and on Escape/blur), so you can see what you've typed when names share a prefix. DOM-verified: the hint span carries the typed text.~~
167. ~~Type-to-select in the Files tree (done 2026-06-13): pressing a letter jumps focus to the next visible row whose name starts with the typed buffer (Finder/VS Code behavior); 800ms reset window, modifier-aware so Ctrl-P is untouched; complements the arrow nav + Ctrl-P. Live-verified: typing 'a' jumped to analysis-notes.md.~~
166. Extend .card-title to the editor-rail/research-panel labels with a tight variant (.card-title-tight, no mb) so the editor panels share the token too without spacing drift (idea added during #155)
201. A periodic "dead-idea sweep" of the backlog — three slices this run turned out already-done (documents sort #177, documents count #200) or near-trivial; a quick pre-check "does this already exist?" before picking would save cycles (idea added during #196)
196. ~~Tighten the base_wide guard (done 2026-06-14): test_wide_pages.py now also fails if any of the 9 wide pages re-declares {% block main_class %} — base_wide.html owns the width, so a page re-setting it is redundant or silently fighting the shared column. 3 guard tests total.~~
195. ~~base_wide guard test (done 2026-06-14): core/tests/test_wide_pages.py asserts the 9 dense pages extend base_wide.html and that base_wide.html keeps {% extends %} as its literal first tag + max-w-6xl — so the #25 density width (and the #183 extends-first gotcha) can't silently regress. 2 tests, fast (grep-only).~~
183. ~~Shared wide-content base template (done 2026-06-14): new templates/base_wide.html extends base.html and overrides main_class to max-w-6xl; the 9 density'd pages (dashboard, overview, plan, writing home, library, documents, project-literature, reading queue, matrix) now extend it instead of each re-declaring the main_class block. Gotcha caught live: {% extends %} must be the literal first tag (a leading {% comment %} 500s every page) — switched to a {# #} comment after extends; all 9 re-verified 200 at width 1056.~~
186. #25 density sweep is COMPLETE across the main surfaces (overview, dashboard, plan, writing board, library, documents, reading queue, matrix, project literature) — next density-adjacent work should be the shared base list-page wrapper (#183) so future pages inherit the rhythm instead of re-applying it by hand (idea added during #182)
182. ~~Project literature index density (done 2026-06-14): literature/project_literature.html widened to max-w-6xl + header mb-6→4; the filter bar / keyword cloud / link list were already tight. Live-verified 200 at width 1056, no JS errors, screenshot reviewed. The per-project Literature landing now matches the rest of the #25 sweep — density is consistent across every literature surface.~~
179. ~~Reading-queue + review-matrix density (done 2026-06-13): reading_queue.html + matrix.html widened to max-w-6xl, order-filter/intro margins 6→4, matrix th/td py-2→1.5; finishes the #25 table/list sweep across literature (library #165, documents #171, queue + matrix #179). Both live-verified 200 at width 1056, no JS errors, matrix screenshot reviewed (calm, cohering with the icon nav).~~
178. ~~(Done 2026-09-07, #421: dashed sparse footer + upload CTA.)~~ Documents-table empty/sparse state polish — with the wider layout a 3-row table leaves a lot of whitespace; a calmer empty-ish state or a max-height could tighten sparse projects (idea added during #171)
171. ~~Density pass on the documents/folder tables (done 2026-06-13): the per-project Documents page widened to max-w-6xl (block main_class), header mb-6→4, table header + every _doc_row.html cell py-2→1.5; the folder rail already used .card. Live-verified: 200, main width 1056, rows render, no JS errors, screenshot reviewed (cohering with the new sidebar + subnav icons). Completes the #25 table sweep alongside #165.~~
191. Factor the "remember a whitelisted ?param in the session" pattern into a tiny helper (now used by #176 library sort and #190 literature order) so future persisted controls don't re-implement the get/restore dance (idea added during #190)
190. ~~Persist the per-project literature order (done 2026-06-14): the order pill choice saves to session["literature_order"]; visiting the per-project Literature page with no ?sort= restores it (default "added"), mirroring #176's library sort. Test covers the round-trip; live-verified choosing Title persists across a bare revisit.~~
189. ~~Per-project literature order control (done 2026-06-14): the list (a _link_row list, not a column table) gets a small set of order pills — Recently added (default), Title, Year, Most cited — via a LITERATURE_SORTS whitelist (field, desc) with nulls_last and reference title as the stable tiebreaker; the active status/priority/keyword filters are preserved through base_params. 2 tests (year ordering + hostile-sort fallback). Live-verified: "Most cited" activates (?sort=cited) and reorders, no JS errors, screenshot reviewed.~~
188. aria-sort on the library's server-rendered headers already exists (#170); the React DocumentsTable now matches (#177). Audit the OTHER React tables (review matrix? reading queue?) for the same a11y treatment for consistency (idea added during #177)
177. ~~Sortable per-project documents table a11y (done 2026-06-14): discovered the documents table was ALREADY client-side sortable via its React island (title/folder/size/added, asc/desc, added-desc default) — reverted a redundant server-side attempt. Instead made the React sort headers accessible: aria-sort reflects the active column/direction, scope="col", and the headers are keyboard-operable (Enter/Space toggles), matching the library's server-rendered aria-sort. Live-verified: default Added=descending, click Title→ascending (Added→none), keyboard Enter toggles to descending, no JS errors.~~
187. ~~Persist filters (done 2026-06-14): the per-project literature list now remembers its status & priority filters across visits via the shared remembered_choice helper, like the sort order already does — "" ("All") is a real, persistable choice that clears a remembered filter, and every value is allow-list-validated before it touches the ORM (#192). Live-verified against the real DB (set→store→restore→All-clears→hostile-rejected); 3 tests. Documents folder/tag NOT done here: folder is navigational (tree clicks) and tag is a per-project pk that would need project-namespaced session keys — see #194/#212.~~
212. ~~Persist the documents tag filter per-project (done 2026-06-14): documents_index now remembers the tag filter via remembered_choice with a slug-namespaced session key (`doc_tag:{slug}`, realising the #194 namespace idea — no helper change needed, the key arg was already free-form), validated against the project's live tag pks so "", a deleted tag, or a foreign pk all fall back to All. Folder stays navigational. Live-verified against the real DB (set→restore→clear→foreign-rejected→per-project-isolated); 4 tests.~~
214. ~~Clear-filter links must actively clear, not bare-link (done 2026-06-14): persisting the literature (#187) and documents (#212) filters silently regressed their "Clear" links — they pointed at a bare/scope-only URL, which now RESTORES the remembered filter from the session instead of clearing it. Fixed both templates to send explicit empty params (`?status=&priority=`, `?…&tag=`), which stores "" and clears the memory. Reproduced the bug live (bare Clear left status='read'), fixed, re-verified; 2 regression-guard tests assert the explicit-empty hrefs render. Lesson: a persisted control's reset affordance must send the empty value, never just omit the param.~~
213. The remembered-filter pattern (literature #187, documents #212) now spans status/priority/tag; if a third surface wants it, consider a tiny `remembered_filters(request, project, specs)` wrapper that loops a list of (param, key, allowed, default) so each view stops hand-rolling the calls — only worth it at 3+ filters on one page (idea added during #212)
215. A grep-based guard test could assert no template links to a persisted-filter view with a bare URL when a Clear/reset affordance is intended — but it's hard to express cleanly (which links are "resets"?); cheaper to just keep the per-link href assertions (#214). Revisit only if a third persisted filter ships and the manual guards feel repetitive (idea added during #214)
216. ~~Cross-project review notes linked to a broken URL (fixed 2026-06-14): the /review page built note links as `/projects/${slug ?? ""}/notes/${id}`, so on the cross-project view (no route slug) every note pointed at `/projects//notes/…`. The weekly_review() data layer only exposed the project NAME, not its slug. Added `project_slug` to every review item (papers/notes/milestones/decisions/experiments — the select_related already loaded the projects, so query budget unchanged at ≤8) and switched the note Link to `n.project_slug`. Live-verified on real data (note 42 → /projects/attention-and-memory/notes/42); data-layer test + built-JS guard (project_slug in Review-chunk). The other item types now also carry slugs, so the API/MCP get_weekly_review consumers can deep-link too.~~
217. ~~Review-page project chips → drill-down links (DEAD/already-done, swept 2026-06-16): re-reading Review.tsx, the milestone (line 124), decision (138) and experiment (148) project chips are ALREADY `<Link to=/projects/{slug}>`; the paper (116) and note (131) chips are plain spans only because they're nested inside row-level `<Link>`s (anchors can't nest). So the actionable part is fully implemented and the rest is structurally impossible without restructuring the rows — nothing to ship. Dead-idea sweep per #201.~~
218. ~~OpenAPI schema didn't document the X-API-Key auth (fixed 2026-06-14): drf-spectacular couldn't resolve the custom APIKeyAuthentication, so it warned on EVERY view and emitted a schema with no security scheme — the exact contract the MCP server + clients read (§6). Registered an OpenApiAuthenticationExtension (api/schema.py, target_class APIKeyAuthentication → apiKey/header/X-API-Key, name ApiKeyAuth), imported from ApiConfig.ready(). Also added return type hints to 3 SerializerMethodFields (get_backlinks→list[dict], get_supports/get_contradicts→int) and request= inline_serializers to the two APIViews drf-spectacular was DROPPING ("unable to guess serializer": BotActionAPIView, CommentsAPIView). Result: 139 warnings + 2 errors → 1 warning + 0 errors; every path now carries `ApiKeyAuth: []` and the two SPA endpoints are documented. Live-verified the running server's /api/schema/ exposes securitySchemes.ApiKeyAuth; guard test added.~~
219. ~~Enum-name collision on "kind" (done 2026-06-14): ManuscriptFile.Kind (tex/bib/asset) and SubmissionEvent.Kind (submitted/…) share the field name with different choice sets, so drf-spectacular merged them into a generated "Kind0fbEnum" and warned. Added ENUM_NAME_OVERRIDES to SPECTACULAR_SETTINGS mapping each to ManuscriptFileKindEnum / SubmissionEventKindEnum. Schema is now 100% clean: 0 warnings, 0 errors, exit 0. Guard test asserts both component names exist. Completes the #218 schema-quality thread.~~
176. ~~Persist the library sort (done 2026-06-14): an explicit ?sort= is saved to request.session (library_sort/library_dir); arriving at /library/ with no sort param restores the last-used order instead of snapping to title-asc. Test asserts a sorted visit then a bare visit keeps the order; live-verified Year-desc persists across a param-less revisit with the arrow shown.~~
170. ~~Sortable library columns (done 2026-06-13): Reference/Year/Venue/Cited headers are server-side sort links (?sort=&dir=, no JS) via a _sort_th.html partial; a LIBRARY_SORTS whitelist keeps ?sort= off arbitrary ORM fields, nulls_last keeps blanks off the top, title is the stable tiebreaker, the search query is preserved, and the active column shows a ↑/↓ + aria-sort. 4 tests incl. a hostile-sort fallback. Live-verified: Year asc 1995→ / desc 2022→.~~
165. ~~Density pass on the library/literature index (done 2026-06-13): widened to max-w-6xl, header/search margins 6→4, table header + row padding 2→1.5; calm and scannable, 25 rows verified, query budget held. Documents tables split out to #171.~~
164. ~~Audit-cadence note in PROGRESS — track 'milestones since last audit' explicitly so AUDIT #17 timing is unambiguous after the rollback-scrambled milestone numbering (idea added by AUDIT #16)~~ (struck 2026-09-07, sweep #467: obsolete — slices are numbered (#4xx) and audits are logged in AUDITS.md)
163. ~~Reset-layout confirmation — Reset layout reloads immediately; a tiny inline confirm (or undo toast) would prevent an accidental wipe of a carefully-tuned arrangement (idea added during #150) — moot in the SPA (no reset-layout control); retired 2026-09-07, #402~~
162. ~~Pet speaks its mood+stage blurb on hover/click — the voice now varies by mood; let the pet optionally read its mood_blurb so you hear the personality, not just a fixed line (idea added during #149) — covered: the click reads the rotating mood bubble; retired 2026-09-07, #402~~
175. Editor chrome / writing board could reuse core/_nav_icon.html names where they overlap (writing, documents) so there's literally one icon source file, retiring any remaining bespoke inline SVGs (idea added during #173)
174. ~~Persist + indicate keyboard focus across the subnav (roving tabindex / arrow-key tab traversal) now that it's a richer icon bar — small a11y win matching the Files-tree nav (idea added during #173) — classic subnav only; the SPA has no icon subnav; retired 2026-09-07~~
173. ~~Lucide icons on the project context subnav (done 2026-06-13): all 11 tabs (Overview/Plan/Documents/Literature/Questions/Writing/Notes/Research/Graph/Decisions/Edit) now carry a calm Lucide glyph from core/_nav_icon.html (Literature reuses the library glyph); the bar wraps gracefully (flex-wrap) so the icons never overflow. 2 added guard tests (subnav↔partial lockstep). Screenshot reviewed: calm, Overview active.~~
172. ~~Active-item icon tint — nav icons are uniformly stone-400; tinting the active item's icon with the accent (or stone-600) would reinforce "you are here" without extra chrome (idea added during #161) — done 2026-09-07, #402~~
161. ~~Lucide icons in the classic sidebar/nav (done 2026-06-13): a core/_nav_icon.html partial inlines the Lucide (MIT) stroke set so the classic Django sidebar shares the React workspace's icon language — Dashboard/Projects/Library/Writing/Prompts/Inbox/Assistant + the mobile menu button; ☰ and ✨ glyphs retired. 4 guard tests (base↔partial lockstep, no bare emoji, rendered). Screenshot reviewed: calm. Editor-chrome already done in #137; subnav split to #173.~~
159. ~~Vite 6→8 upgrade (done 2026-06-14): bumped vite ^6→^8 + @vitejs/plugin-react ^4→^6; npm audit --omit=dev now 0 vulns (esbuild advisory GHSA-gv7w-rqvm-qjhr closed). Vite 8 reshuffled chunk module-id matching so the chunkFileNames heuristics needed updating: the editor-core chunk is now the shared CodeMirror bundle (detect "codemirror", not just /src/editor/), and Vite 8's opaque "chunk"/"dist"/"index" fallback names map to a tidy "shared-chunk.js". Clean-rebuilt (rm islands/* first) so no stale orphans (removed client-chunk/index-chunk + the now-inlined TerminalPanel.css). tsc clean; all 5 key surfaces (SPA dashboard, Files, classic documents, library, latex editor) live-verified with zero JS errors / zero failed JS requests + screenshot.~~
160. ~~Harden the Tauri webview navigation allowlist (done 2026-06-13, from AUDIT #15): the desktop shell's WebviewWindowBuilder.on_navigation only permits the Atlas host (localhost), so a compromised loaded page can't steer the app window off-origin; cargo check passes, structural test asserts the guard.~~

(populated by phase gates; work top to bottom only after the Phase 6 gate passes)

1. ~~In-browser PDF viewer with highlight-to-note (done across the Library v2 slices: the workbench reader with highlights, notes, comments; swept 2026-09-07, #436)~~
2. ~~Literature review matrix (papers × themes) (DEAD/already-done, swept 2026-06-16): the matrix exists — GET /api/v1/projects/{slug}/review-matrix/ ("which paper covers which theme") + a React review-matrix surface + seed_demo data. Nothing to build. Dead-idea sweep per #201.~~
3. ~~Embedding-based related-paper suggestions (the offline version shipped as local TF-IDF cosine — Library rail, Reference page and MCP `get_related_in_library`; OpenAlex covers papers outside the library; swept 2026-09-07, #436)~~
4. ~~GitHub commit ↔ experiment linking (done 2026-06-16): ExperimentEntry gained a commit_url URLField + a commit_label property that prettifies a GitHub/GitLab commit URL to owner/repo@shortsha (else the host). Wired through the form, admin list_display, the ExperimentEntrySerializer (read-only commit_label), the classic experiments.html (a ⎇ owner/repo@sha link), and the React Research experiment log. Pure pasted-URL link — no GitHub API call — so it's offline/host-agnostic. Migration 0002; live-verified the read path + label parse; 3 tests (label parsing across hosts, rendered link, form accepts url). The "fetch commit metadata" richer version stays parked as #259.~~
5. ~~Cmd+K command palette (DEAD/already-done, swept 2026-06-16): app/CommandBar.tsx is a complete Cmd/Ctrl+K palette — fuzzy jump-to-anything (subsequence scorer), real verbs (capture:, done:), page-aware quick actions from the assistant context endpoint, recents, and an "Ask Claude" MCP handoff. Bound to (metaKey||ctrlKey)+k in CommandBar. Already shipped back in cycle 65; nothing to build. Dead-idea sweep per #201.~~
6. ~~Auto-generated weekly review (DEAD/already-done, swept 2026-06-16): the weekly review exists — core/reviews.weekly_review() + WeeklyReviewAPIView (/api/v1/weekly-review/) + the React Review page (cross-project /review and scoped /projects/:slug/review, with week-back nav and a copyable digest). Nothing to build. Dead-idea sweep per #201.~~
7. ~~Protocol library with versioning — API-first slice done 2026-06-16: new research.Protocol model (project, title, body markdown, version, parent self-FK) — append-only, so editing means a new version: protocol.new_version(**overrides) clones with version+1 and parent set, and is_current = "no later version names me as parent" (head of the chain). Exposed as a WRITABLE DRF viewset /api/v1/protocols/ (the one research viewset that's writable — protocols are an MCP-managed, machine-friendly feature so Claude can author/revise them) with a POST {id}/new-version/ action; version+parent are read-only (the history chain can't be forged). Registered in admin + router; schema --fail-on-warn clean. Migration research/0003; live-verified create→new-version→list (v2 current, v1 superseded); 8 tests. Remaining: a classic/SPA project UI page (list current protocols + version history + edit-as-new-version) — parked as #260.~~
8. Results/figure gallery — ~~data layer done 2026-06-16 (API-first): GET /api/v1/projects/{slug}/figures/ returns every inline-previewable raster image in the project (newest first) — id, title, folder, tags, size, content_type, created_at + a `raw_url` that serves the image inline (reusing #250/#254). documents.selectors.project_figures is a pure, N+1-free selector (filter content_type startswith image/ in DB, exact preview_kind whitelist in Python, excludes SVG); API-key gated, project-scoped, schema-documented (--fail-on-warn clean). Live-verified end-to-end (uploaded a PNG → appeared in the feed → raw_url served image/png inline + nosniff + cache). 7 tests.~~ ~~Remaining: the gallery UI page (#256) — a React grid of thumbnails linking to raw_url, grouped by folder, with a tag filter.~~ (The Figures page `/projects/{slug}/figures` shipped it; swept 2026-09-07.)
9. Email/calendar deadline reminders — (email half retired 2026-09-07: it needs SMTP credentials, a settings screen in disguise; the calendar feed + feed token (#401) and the deadline-reminder bot into the Inbox cover the need) ~~calendar half done 2026-06-16: GET /api/v1/projects/{slug}/calendar.ics/ exports the project's milestone due dates + manuscript deadlines as an iCalendar (RFC 5545) feed of all-day VEVENTs (core/calendar.py, a dependency-free generator with escape + 75-octet line folding; completed milestones marked ✓/CONFIRMED). Authed via the existing X-API-Key; schema validates with --fail-on-warn; live-verified (7 events on the demo project). 8 tests.~~ Still open: the email-reminder half (needs SMTP config) and a token-in-URL feed so a calendar app can subscribe without a header (see #253).
10. ~~OpenAlex "discover similar" (done 2026-06-11, cycle 31): `literature/discover.py` resolves the work, batch-fetches related_works, filters out DOIs already in the library; ⌕ Discover panel on reference detail with one-click + Add (reuses by-DOI import incl. background PDF fetch); verified live on a real paper.~~
11. ~~Conditional GETs (API lists since #384; served files since #434; swept 2026-09-07)~~ — original: ETag/Last-Modified on API list endpoints and far-future cache headers on media/static, so MCP polling and the PDF reader get cheap revalidation (idea added by cycle 4, from the performance pass)
12. ~~“Read aloud” for whole PDFs (done 2026-06-11, cycle 32): ▶ Listen in the reader — streams text-layer pages through /tts/ from the page in view, sentence-aware chunking for long pages, pause/stop mini player, auto-scroll to the page being read, graceful voice-missing message.~~
13. ~~Worker-deploy note (done 2026-06-11, cycle 33): `make worker` restart target + README warning; doctor detects stale workers via a CODE_STAMP round-trip task.~~
14. ~~Keyword cloud + queue filters (done 2026-06-11, cycle 35): weighted keyword cloud on the project literature page (10-min cached), clicking filters both the literature list and the reading queue by ?kw=.~~
15. ~~Responsive layout (done 2026-06-11, cycle 34, UI/UX): hamburger drawer below lg with backdrop + Escape close (Alpine), content reflows with responsive padding, wide tables scroll horizontally; verified at 420px in a real browser.~~
16. ~~`make doctor` (done 2026-06-11, cycle 33): manage.py doctor checks db/migrations/redis/worker-liveness+freshness/CSS/Tectonic/voice/media/API-key with ✓⚠✕ output and exit codes; verified live incl. catching a genuinely stale worker.~~
17. ~~Prompt variables (done 2026-06-11, cycle 36): `{{placeholder}}` parsing on Prompt (`variable_names` property), per-card fill-in inputs on the gallery, copy button substitutes filled values before writing to the clipboard.~~
18. ~~Bot run history charts (done 2026-06-11, cycle 37): pure-CSS bar sparkline of the last 20 runs per bot on the Automations page — bar height = headline number parsed from each result line (`BotRun.count`), failed runs in red, hover tooltip with date + result; history list capped at 5 with chart above; seeded demo runs. (Last-N retention shipped earlier in cycle 12.)~~
19. ~~LaTeX compile service — vendor the Tectonic binary (like Tailwind/Piper pattern) behind a huey task with compile logs surfaced in the editor (idea added by cycle 13)~~ (Done: the studio compiles with bundled Tectonic, logs in the problems panel; swept 2026-09-07.)
20. ~~Comment mentions (done 2026-06-11, cycle 38): `core/mentions.py` resolves `[[Note Title]]` (when exactly one note matches, any project) and `@cite-key` into markdown links before markdownify/nh3; applied via the `mentions` template filter in comment threads; unresolved/ambiguous mentions stay as typed; seeded demo comment exercises both.~~
21. ~~Queue gap-ordering (done 2026-06-11, cycle 41): "Fill matrix gaps" toggle on the reading queue — each queued paper scores by its least-read theme (READ/ANNOTATED counts), under-read themes float up with an amber "fills: <theme> (n read)" badge, unmarked papers sort last; default priority order unchanged.~~
22. ~~Pet hop (done 2026-06-11, cycle 42): milestone completion sends `HX-Trigger: atlas:milestone-completed`; a body listener restarts a calm two-bounce CSS animation on the sidebar pet (reduced-motion respected; un-checking stays quiet); verified in a real browser both ways.~~
23. ~~Tree grove (done 2026-06-11, cycle 43): "The grove" card on the dashboard — one tree per active project via the existing project_tree tag, size scales with milestone count (64px + 5/milestone, capped 112px), each tree links to its project; verified live with a screenshot.~~
24. ~~Upload progress bars (done 2026-06-11, cycle 44): bulk upload now sends one XHR per file with a slim live progress bar, done/failed state per row (filenames rendered via textContent), sequential to keep the server calm. Also repaired a template corruption found mid-slice: the upload script had been duplicated into the title and breadcrumbs blocks, redeclaring consts and silently breaking drag-and-drop — regression test added.~~
25. ~~Suggest keyboard nav (done 2026-06-11, cycle 45, UI/UX): ↑/↓ cycle a highlight through the sidebar suggestions (proper combobox/listbox roles + aria-activedescendant), Enter opens the active result, first Escape clears the list keeping focus, second blurs; browser-verified end to end. Recent-searches memory split out to Backlog #52.~~
26. ~~GIN trgm indexes (done 2026-06-11, cycle 46): GinIndex(gin_trgm_ops) on the five trigram-fallback columns (project.name, reference/note/document/decision title), migrations depend on core.0003_pg_trgm; fallback switched from `similarity()>0.25` (seq-scan only) to `__trigram_similar` (% operator, threshold 0.3) so the planner can use the indexes — EXPLAIN-verified Bitmap Index Scan; typo search re-verified live.~~
27. ~~MCP ETag cache (done 2026-06-11, cycle 47): the MCP client remembers ETag+body per GET (path, params), sends If-None-Match and reuses the cached body on 304 — verified [200, 304] live against the real API; client stays pure httpx (AST test green). Last-Modified on media split out to Backlog #54.~~
28. ~~Loop-resilience note — chain notifications can drop and watchdog monitors expire at 30 min; watchdog is now re-armed every cycle (lesson from the cycle-21→22 stall)~~ (struck 2026-09-07, sweep #467: note, not a task — the loop's own process; kept in CLAUDE/PROGRESS rituals)
29. ~~Dev-process note — runserver/worker restarts must use pkill -f "[m]anage.py ..." (bracket trick) or they kill their own shell; documented after the cycle-23 debugging (idea added by cycle 23)~~ (struck 2026-09-07, sweep #467: note, not a task — the bracket-trick is in the scratchpad start scripts)
30. ~~Editor split view — compiled PDF preview pane beside the source with sync scroll (idea added by cycle 24) — the split view shipped with the studio; sync scroll done 2026-09-07, #394~~
31. ~~Comment markers rendered in the PDF margin at their anchor position (idea added by cycle 25) — done 2026-09-07, #396 (page-anchored bubbles + comment-on-this-page)~~
32. ~~tl;dr for whole PDFs — summarize the text layer per section in the reader (idea added by cycle 26) — done 2026-09-07, #395~~
33. ~~SyncTeX-style jump (done 2026-09-07, #378: double-click the PDF → source, ⌘⇧J → PDF)~~
34. ~~Animated demo GIF for the README (done 2026-09-07, #430: `scripts/demo_gif.py` → `docs/demo.gif`, `make demo-gif`)~~ — original idea: scripted Playwright run through the killer 60-second flow (idea added by cycle 28)
35. Slim the Docker image — multi-stage build, piper/onnx as optional extra (~800 MB → ~300 MB) (idea added by cycle 29)
36. ~~Containerized LaTeX compile — run Tectonic in a throwaway container/namespace to close the \input file-read residual risk if Atlas ever goes multi-user (idea added by cycle 30 audit)~~ (struck 2026-09-07, sweep #467: closed by `--untrusted` in writing/compile.py (path validation + Tectonic's untrusted mode); multi-user is a §1 non-goal)
37. ~~Discover-similar in the reading queue — a "explore neighbors" action per queue item (idea added by cycle 31) — done 2026-09-07, #403~~
38. ~~Listen prefetch — synthesize the next chunk while the current one plays to remove gaps (idea added by cycle 32) — done 2026-09-07, #404 (chunked + prefetched)~~
39. ~~Doctor on the Automations page — render the same checks in the UI with a stale-worker banner (idea added by cycle 33) — covered by the Diagnostics page (engine, jobs, feed, warm-up, access, front-end errors); swept 2026-09-07~~
40. ~~Swipe + touch targets (done 2026-06-11, cycle 39, UI/UX): drawer closes on a >60px left swipe (Alpine touch handlers; short swipes ignored), milestone/task check-offs grew to 20/16px visuals with an invisible `after:-inset-2.5` pseudo-element giving ≈40×40px tap targets (+ shrink-0 so flex rows can't squeeze them); verified at 420px in a real touch browser.~~
41. ~~Keyword cloud on the project overview card (idea added by cycle 35) — done 2026-09-07, #398 (a weighted chip row)~~
42. ~~Audit log page — surface recent logins (incl. throttled attempts) and API activity on a simple "Activity & access" page, building on the new throttle counters (idea added by cycle 5, from the security pass) — done 2026-09-07, #399 as Diagnostics › Access + /api/v1/access-events/~~
43. ~~Prompt variable defaults — `{{name|default}}` syntax pre-fills the fill-in inputs, and last-used values are remembered per prompt in localStorage (idea added by cycle 36) — done 2026-09-07, #393~~
44. ~~(Done 2026-09-07, #423: QuickCapture.bot_run, ?run= filter, bars link.)~~ Clickable chart bars — clicking a bot history bar filters the Inbox to captures created by that run (needs a run→capture link) (idea added by cycle 37)
45. ~~Mentions everywhere — apply the same [[note]]/@cite-key resolution to decision records, experiment entries, and quick captures (one filter, three templates) (idea added by cycle 38)~~ — shipped 2026-09-07 (#407: core/rendering, `*_html` fields, Prose component; protocols too)
46. ~~Edge-swipe open (done 2026-06-11, cycle 48, UI/UX): touchstart within 24px of the left edge + >60px rightward swipe opens the drawer (window-level Alpine handlers); mid-screen swipes ignored — touch-verified at 420px.~~
47. ~~`make audit` (done 2026-06-11, cycle 91): scripts/audit.sh runs the anon-access + key-auth + #77-catch-all + open-redirect + pip/npm probes as one read-only command, exit-coded; every audit cycle starts here now.~~
48. ~~Matrix gap column hints — show each theme's read-count in the review matrix header so gaps are visible there too, linking back to the gap-ordered queue (idea added by cycle 41)~~ — shipped 2026-09-07 (#408)
49. ~~More pet reactions — a sparkle on phase completion and a brief "om nom" when a reference is marked read, all through the same HX-Trigger pattern (idea added by cycle 42)~~ — already true in the SPA (`petReact("milestone")` on check-off, `petReact("paper")` on read; retired 2026-09-07)
50. ~~Grove seasons — paused projects show bare autumn trees and archived ones fade out, so the grove reflects the whole portfolio at a glance (idea added by cycle 43)~~ — dead: the grove was a classic-UI widget the SPA never carried; the Projects page folds archived work instead (retired 2026-09-07)
51. ~~(Done 2026-09-07, #422: core/tests/test_template_lint.py.)~~ Template lint pass — a tiny pytest that walks every template and asserts title/breadcrumbs blocks contain no `<script>` (the cycle-44 corruption class), plus django-template syntax check via the loader (idea added by cycle 44)
52. ~~Recent searches (done 2026-06-11, cycle 48, UI/UX): submits store the query in localStorage (5 max, deduped); focusing the empty box lists them as a keyboard-navigable listbox (queries rendered via textContent), Enter re-runs the search — browser-verified.~~
53. ~~Trigram index for the literature `?kw=` filter (done 2026-09-07, #465: `reference_abstract_trgm`)~~ — original: reference.abstract icontains scans could use a GIN trgm index too once libraries grow past a few thousand rows (idea added by cycle 46)
54. ~~Last-Modified/If-Modified-Since on media downloads (done 2026-09-07, #434: `core/files.py::file_response` — ETag + Last-Modified + 304 on the three file views; `/media/` already had it via static.serve)~~ (idea added by cycle 47)
55. ~~Pin a search (done 2026-09-07, #435: recents + ☆ pins on the SPA Search page, localStorage)~~ — original: star a recent search to keep it permanently at the top of the recents dropdown (idea added by cycle 48)
56. ~~Pet speech variety pack (done 2026-09-07, #465: weekday + month lines, six milestone reactions)~~ — original: seasonal/weekday lines and milestone-completion one-liners spoken in the hop moment via HX-Trigger payload (idea added by cycle 49)
57. ~~Search page budget (measured 2026-09-07: 14 queries / 27 ms for three demo queries — under the bar; struck)~~ — original: /search/ sits exactly at the 50ms bar; profile the per-type rank queries and consider a single UNION query or smaller LIMIT_PER_TYPE (idea added by cycle 50, from AUDIT #5)
58. ~~Tree tooltips (the grove lives only in the classic dashboard, replaced by the SPA; struck 2026-09-07)~~ — original: hovering a grove tree shows stage name + "n/m milestones" in a styled tooltip instead of the browser default (idea added by cycle 51)
59. ~~[REV] Atlas Assistant panel (done 2026-06-11, cycle 55 — the first revolutionary cycle): ✨ Assistant on every page — Cmd/Ctrl-K (or sidebar button) opens a calm slide-over React island; fuzzy jump-to-anything command bar (local subsequence scoring over a server-built index of projects/notes/references/prompts/manuscripts/pages, ≤400 entries, 5 queries); page-aware quick actions; 'Ask Claude about this' composes a context-rich MCP prompt (object + suggested atlas tools) with one-click copy; recent-activity feed for the current object. Backend: core/assistant.py + GET /assistant/context/ (session-gated). Built with parallel agent workflows per owner suggestion. NO paid APIs.~~ (idea added by cycle 52)
60. ~~Bulk-bar keyboard shortcuts (x and Esc earlier; shift-click / shift-x ranges and ⌘A done 2026-09-07, #433)~~ — original: x toggles selection on the focused row, shift-click selects ranges, Esc clears the selection (idea added by cycle 53)
61. Island dev-mode — `vite dev` proxy so island development gets HMR against the running Django server (idea added by cycle 54)
62. ~~[REV] Synthesis studio (the scaffold note shipped as the matrix's synthesis draft; the manuscript export shipped 2026-09-07, #437: `draft_related_work` → `sections/related-work.tex` with every key in the bibliography)~~ — original: select N papers from the matrix and get a structured literature-synthesis scaffold (themes × claims × evidence table prefilled from reading notes + keywords, exportable to a manuscript section) (idea added by cycle 55)
63. Assistant actions that act — POST quick actions in the panel (complete milestone, set reading status) with optimistic UI, reusing the bulk endpoints pattern (idea added by cycle 55)
63. ~~SPA shell polish — pet widget, global search, and the assistant summon inside the React layout so /app/ feels complete while sections migrate (idea added by cycle 56)~~ (struck 2026-09-07, sweep #467: done long ago — the React Layout carries the pet, global search and the assistant)
64. ~~SPA route prefetch (done 2026-09-07, #448: project cards prefetch the overview on hover)~~ — original: hovering a project card prefetches its overview query so navigation feels instant (idea added by cycle 57)
65. ~~SPA plan editing — phase/milestone/task create+edit modals in React so the plan page reaches full parity and the classic page can retire (idea added by cycle 58)~~ (struck 2026-09-07, sweep #467: done — Plan v2 (#311 onward) creates/edits phases, milestones and tasks in React; the classic plan page is gone)
66. ~~CSS build gate — add `make css && git diff --exit-code static/css/app.css` to the cycle gate so Tailwind classes used by new TSX never ship missing (idea added by cycle 59, from the ml-56 bug)~~ (struck 2026-09-07, sweep #467: done — `make assets-check` (css + js, fails on a stale committed output))
67. SPA error toasts — surface failed optimistic mutations (e.g. PATCH rejected) with a calm inline toast + automatic state rollback instead of relying on the next refetch (idea added by cycle 60, from AUDIT #6 review of the optimistic-write path)
68. Server-side reference search — ?search= on /api/v1/references/ (title/key/venue/authors icontains) so the SPA library scales past one page (idea added by cycle 61)
69. ~~Autosave for the SPA note editor (shipped with the CodeMirror notes editor; swept 2026-09-07)~~ — original: debounced PATCH 2s after typing stops, with the Saved indicator reflecting in-flight state (idea added by cycle 62)
70. ~~Log submission events from the SPA (the Writing page's event form posts to /manuscripts/{id}/events/; swept 2026-09-07)~~ — original: small add-event form on the manuscript timeline (kind, date, notes) via a SubmissionEvent API (idea added by cycle 63)
71. ~~Bulk milestone create (done 2026-06-11, cycle 71): POST /api/v1/milestones/ accepts a JSON list (many=True) and completed_at is settable at create — used immediately to plan future self-build cycles in one call. Friction-sourced from dogfood setup, now fixed.~~
72. ~~Milestone search (done 2026-06-11, cycle 71): ?q= filters milestones by title so scripts/SPA find one without fetching the whole plan. Friction-sourced from the first dogfood ship step.~~
73. ~~Command-index SWR cache (done 2026-06-11, cycle 77): the ⌘K bar's assistant-context (and plan) now load via React Query with staleTime — cached across opens, refreshed in the background. 3 opens → 1 fetch (was 3 fresh fetches); content paints instantly from cache. The plan query shares the Plan page's key so there's often zero extra fetch.~~
74. ~~[REV] Reading-flow mode (done 2026-06-11, cycle 75): /app/projects/:slug/read — keyboard-driven read-next session over the queue (1-4 reading status, n/p move, j quick-note, l listen TTS, Esc exit), one card at a time priority-ordered, progress bar, optimistic PATCH advancing on read/annotated; dedicated /reading-flow/ API. Flashcards for papers.~~
75. register_readonly API helper — one-liner read-only serializer+viewset+route for simple models; felt as boilerplate friction in cycle 66 (idea added by cycle 66, friction-sourced)
76. ~~Route-level code splitting — React.lazy per SPA section so spa.js stays lean as pages accumulate; bundle grew 30→38KB gz in cycle 67 (idea added by cycle 67, friction-sourced)~~ (struck 2026-09-07, sweep #467: done — every SPA page is a lazy island chunk under static/js/islands/)
77. ~~Shared route rule (done 2026-06-11, cycle 76): replaced the hand-mirrored SPA route list in core/urls.py with ONE catch-all — `^(?!api/|app/|static/|media/)(?!.*/$).+$` serves the shell for any slash-less path (classic keeps trailing-slash URLs). Adding a React page now needs zero Django changes; the cycle-74/75 drift class is gone. Tests cover unlisted pages served, classic intact, unknown /api/ still 404.~~
78. ~~SPA decision detail (done 2026-09-07, #443: timeline rows expand the rendered context / decision / alternatives)~~ — original: context/alternatives render in the timeline (saved now, shown truncated); felt while recording the cycle-69 decision (idea added by cycle 69)
79. ~~`make audit` (done 2026-06-11, cycle 91): scripts/audit.sh runs the anon-access + key-auth + #77-catch-all + open-redirect + pip/npm probes as one read-only command, exit-coded; every audit cycle starts here now.~~
80. ~~Bulk task create + search (done 2026-06-11, cycle 89): tasks endpoint mirrors milestones — POST a JSON list to create many (done settable at create), ?q= filters by title. The plan API is now uniform across milestones and tasks.~~
81. ~~SPA synthesis + coverage (done 2026-06-11, cycle 73): React literature page gets a Draft-synthesis button (X-SPA JSON → navigates to the note, no reload) and a coverage-gap nudge highlighting themes with ≤1 paper; closes Owner idea #11's active coverage-gap suggestion too.~~
82. ~~Coverage-gap → queue prefill (done 2026-06-11, cycle 94, UI/UX): thin themes in the nudge are clickable chips → `/queue?theme=X` shows unread candidates (theme words matched against title/abstract, already-marked excluded) via `theme_candidates` selector + `?theme=` on /api/v1/project-references/; quiet filter chip with Clear, NN/g-style filtered empty state; browser-verified.~~
83. ~~PROMOTE #77 to next-priority — the shared route manifest; cycle 74 hit the exact predicted drift (React route added, Django pattern forgotten, 404). Do it before more routes accrue (idea escalated by cycle 74)~~ (struck 2026-09-07, sweep #467: done — core/spa_routes.py + links.ts with a guard test (test_front_door))
84. ~~Weekly research review (done 2026-06-11, cycles 84-85): data layer core/reviews.py + /api/v1/weekly-review/, then the SPA page at /review + /projects/:slug/review — a calm skimmable 'this week' digest (papers/notes/milestones/decisions/experiments, each linked), top-line summary, ◀▶ week-back nav, per-project + cross-project, sidebar 'Review' link. The self-build project's own review shows the loop's week.~~
85. ~~Reading-flow for the whole library (done 2026-09-07, #450: `/library/read?<filters>` over `/references/reading-flow/`)~~ — original: a 'read flow' over any filtered reference set, not just one project's queue (idea added by cycle 75)
86. ~~Promote the route rule to docs — note the slash-less=SPA / trailing-slash=classic invariant in CONTRIBUTING so external contributors don't re-add per-route Django patterns (idea added by cycle 76)~~ (struck 2026-09-07, sweep #467: done — CONTRIBUTING.md carries the slash-less = SPA / trailing-slash = classic rule)
87. ~~Prefetch assistant index on mount (done 2026-06-11, cycle 78): Layout warms the ⌘K assistant-context query on app load, so even the very first ⌘K paints instantly.~~
88. ~~tl;dr in reading-flow (done 2026-06-11, cycle 79): 's' summarizes the current paper's abstract inline during a read session; resets on next/prev, in the key legend. The focused session is now Listen + tl;dr + note + status, fully keyboard.~~
89. ~~Seeded abstracts (done 2026-06-11, cycle 81): three demo references (incl. one to_read) now carry real abstracts, so tl;dr/Listen/reading-flow demo out of the box; closes the AUDIT #8 finding.~~
90. ~~Seeded abstracts (done 2026-06-11, cycle 81): three demo references (incl. one to_read) now carry real abstracts, so tl;dr/Listen/reading-flow demo out of the box; closes the AUDIT #8 finding.~~
91. ~~Sample PDF for a to_read paper in seed_demo — so the PDF reader/iframe also demos in the reading-flow, not just the abstract (idea added by cycle 81)~~ (struck 2026-09-07, sweep #467: done — seed_demo attaches a generated PDF to lavie2010attention)
92. Docs site (mkdocs-material) with the MCP setup guide front and center — next open-source slice after templates (idea added by cycle 82)
93. ~~Comments on documents (done 2026-06-11, cycle 96): document kind added to the comment allowlist (classic endpoint + /api/v1/comments/document/{id}/ both lit up); 💬 button with live count on every documents-table row opens a modal thread (ESC/backdrop/✕ dismissal, ⌘-Enter post) per owner modals rule + overlay-pattern research; counts piggyback on documents_table_props in one query; browser-verified post→persist→dismiss.~~
94. ~~Weekly-digest bot (done 2026-06-11, cycle 86): opt-in bot posts last week's summary (papers/notes/milestones/decisions/experiments counts) to the inbox via core/reviews.py; pairs the Review page with a Friday push. Quiet weeks post nothing.~~
95. ~~Research timeline (done 2026-06-11, cycle 95, [REV]): `core/timeline.py` aggregates 9 event kinds (milestones, papers added/read, notes, decisions, experiments, hypotheses, documents, manuscript events) into one stream; `GET /api/v1/projects/{slug}/timeline/` returns events + oldest-first markdown; MCP `get_timeline` tool; SPA `/projects/:slug/timeline` — vertical, color-coded, day/week/month zoom grouping, kind filter chips, copy-as-markdown; browser-verified with 41 live events.~~
96. ~~Review copy-as-markdown (done 2026-06-11, cycle 88): a 'Copy week' button on the Review page emits clean markdown (sectioned by papers/milestones/notes/decisions/experiments) for pasting into a lab journal or a Claude session.~~
97. ~~MCP weekly_review tool (done 2026-06-11, cycle 87): get_weekly_review(project, weeks_back) exposed over the MCP server (client fn + tool); Claude can pull 'what did I do this week' in chat. Verified live (30 milestones for self-build). Client stays pure httpx.~~
98. ~~MCP get_synthesis_scaffold (done 2026-06-11, cycle 93): read-only GET /projects/{slug}/synthesis/ (distinct from the note-creating POST) + MCP client fn + tool, so Claude can pull the theme-organized review scaffold to draft a section in chat — creates no note. Client stays pure httpx.~~
99. ~~Per-section copy (done 2026-09-07, #457)~~ — original: small copy buttons on each Review section (e.g. just the milestones) for finer-grained pasting (idea added by cycle 88)
100. ~~Generic list-create+search mixin (done 2026-06-11, cycle 98, tech improvement): AtlasViewSet gains `q_fields` (?q= icontains-OR search) and `bulk_create` (JSON-list POST) knobs; milestones/tasks/prompts overrides collapsed to two-line declarations; notes, decisions, research questions, hypotheses, and datasets opted into ?q= for free; live-verified on notes and decisions; 3 new tests incl. ?q= no-op without q_fields.~~
101. ~~`make audit` (done 2026-06-11, cycle 91): scripts/audit.sh runs the anon-access + key-auth + #77-catch-all + open-redirect + pip/npm probes as one read-only command, exit-coded; every audit cycle starts here now.~~
102. ~~CI workflow (done 2026-06-11, cycle 92): .github/workflows/ci.yml runs ruff check+format, pytest (postgres service), frontend tsc, and a committed-assets-not-stale check on every push/PR — the loop's hand-run gate now guards contributions. README CI badge.~~
103. ~~CI make-audit job (done 2026-06-11, cycle 99, tech improvement): second CI job (postgres service, uv sync, migrate, runserver with a 30s readiness loop) runs `make audit` on every PR; audit.sh now prefers $ATLAS_API_KEY over .env so CI needs no dotfile; verified locally via the exact env-var-only path.~~
104. ~~Duplicate of #95 — shipped together in cycle 95.~~
105. ~~Theme chips beyond the gap nudge (done 2026-09-07, #457)~~ — original: make every theme in the review matrix header link to its candidate queue, not just thin ones, so the prefilter is discoverable from the matrix too (idea added by cycle 94)
106. Design-notes file — a docs/DESIGN.md capturing the HIG-derived rules now binding (clarity/deference/depth, filtered-empty-state pattern, chip vocabulary) so every future UI slice starts from the same language (idea added by cycle 94, from the new owner design-research rule)
107. ~~Timeline event detail expand (done 2026-09-07, #443)~~ — original: click a dot to expand the event in place (decision context, experiment body, note preview) without leaving the page (idea added by cycle 95)
108. ~~Timeline on the overview (the week digest on the overview lists the week's events and links to the timeline; swept 2026-09-07, #444)~~ — original: a 5-event mini-timeline strip on the project overview linking to the full page (idea added by cycle 95)
109. ~~Comment threads from search (done 2026-09-07, #439: `comment` kind on both search paths, routes to the note / paper / editor)~~ — original: comments are invisible to global search; index comment bodies (FTS) so "where did I write that remark?" resolves (idea added by cycle 96)
110. ~~Pet hatching & species (done 2026-09-07, #427)~~ — original: a one-time hatch moment (deterministic from the install, Buddy-style) choosing among a few species/looks, with a tiny shiny chance; pairs with #49/#56 (idea added by cycle 97)
111. Document the ?q= convention in the API schema — a reusable OpenApiParameter on every q_fields viewset so MCP/scripts discover searchability from /api/docs/ (idea added by cycle 98)
112. CI audit artifacts — upload /tmp/server.log and the sweep output as workflow artifacts on failure so red audit jobs are debuggable without rerunning (idea added by cycle 99)
113. API timing smoke in CI — extend the audit job with a best-of-5 latency check on 3 hot endpoints against the 50ms bar, so regressions like the cycle-100 N+1 surface in PRs not audits (idea added by cycle 100)
114. ~~Vendor CodeMirror locally (the CM6 editor is bundled; no CDN reference remains in templates or the SPA; swept 2026-09-07)~~ — original: the editor dies without internet (cdnjs); pull the CM5 assets into static/vendor/ like tailwind/tectonic/piper, felt when the sandbox proxy broke CDN loads during cycle-101 verification (idea added by cycle 101, friction-sourced)
115. ~~Compile-queue dedupe (done 2026-09-07, #455: `source_hash`, deduped / unchanged answers, `force`)~~ — original: hash the source at queue time and skip the enqueue entirely when an identical-source compile is already running (the generation guard drops stale results; this would avoid the wasted compile too) (idea added by cycle 102)
116. ~~PDF text layer in the editor preview (done 2026-09-07, #452)~~ — original: add pdf.js TextLayer (the literature reader already does it) so preview text is selectable/copyable; prerequisite niceness for SyncTeX click-to-jump in slice 7 (idea added by cycle 103)
149. ~~Pet voice personality — mood layer (done 2026-06-13): MOOD_VOICES in core/tts.py sets loudness/liveliness from the pet's weekly mood (sleeping 0.6 → thriving 1.0 + extra noise_w) on top of the stage's pace/timbre (volume-only so they compose); read_aloud passes both stage+mood; real WAVs verified distinct per mood; 4 tests incl. MOODS↔MOOD_VOICES sync + compose.~~
142. ~~Pet voice personality (done 2026-06-12, cycle 138, Owner #29 follow-on): STAGE_VOICES in core/tts.py shapes Piper delivery per growth stage — egg murmurs slow+soft (length 1.25, noise 0.45), hatchling peeps fast (0.8, lively phoneme timing), scholar is the voice as trained, sage is slow+measured (1.18) — and read_aloud derives the stage server-side from pet_state(). Real-voice durations verified distinct (1.94s/2.25s/2.59s for the same sentence); live endpoint 200 audio/wav; 4 new tests incl. a STAGES↔STAGE_VOICES sync guard.~~
148. Icon sweep for the rest of the app — the editor chrome now speaks one stroke-SVG language; the classic sidebar/pages still mix glyphs (✨ Assistant, ⌘K, section headers); a templatetag or include for the icon set would let every surface share it (idea added by cycle 137)
146. ~~Inline-SVG icon sweep for the editor chrome (done 2026-06-12, cycle 137, UI/UX, parity plan cycle 6): Recompile ↻, zoom-fit ↔, upload ↑, File-menu ⬇, the three layout-preset glyphs, the PDF/research ⇄ toggles, and the 💬 comment gutter marker (now a .comment-dot stroke-SVG chat bubble in the CM6 island) all replaced with the rail's monochrome stroke-icon language. Ω stays — it labels the symbol palette semantically. 12-check battery + editor smoke ALL PASS, screenshot reviewed.~~
147. ~~Audit-sweep output as a CI artifact (done 2026-06-12, cycle 139, shipped with #144): make audit tees to /tmp/audit-output.txt under set -o pipefail (exit code preserved, verified locally) and the file joins the failure() artifact upload — completes #112.~~
143. ~~Smoke artifacts on CI failure (done 2026-06-12, cycle 136, tech improvement, shipped with #145): any failed check — or a crash before the checks even run (try/except around the whole battery) — writes editor-smoke.png (full page), the browser console log, and the failure list to SMOKE_ARTIFACT_DIR; ci.yml uploads them via actions/upload-artifact on failure() together with /tmp/server.log. Verified both paths live: green run leaves nothing, a forced bad-password run exits 1 with all three artifacts written.~~
141. ~~Editor-page Playwright smoke in CI (done 2026-06-12, cycle 132, tech improvement): scripts/editor_smoke.py — a 6-check headless battery (mount w/ zero CDN editor assets, autosave, multi-file switch preserving buffers, line comment + gutter dot, cite autocomplete, compile wiring incl. graceful no-tectonic failure) distilled from the cycle-126 cutover battery; self-seeding via X-API-Key on an empty DB; wired into the CI audit job (createsuperuser --noinput, playwright chromium, no Redis needed — dev huey is immediate). ALL PASS locally.~~
158. ~~Undo for inline triage (done 2026-09-07, #440: global UndoHost, six-second Undo on the Inbox and the dashboard row)~~ — original: a filed/dismissed attention row vanishes immediately; a 5-second "undo" toast (PATCH processed:false) would make the inline action worry-free (idea added by cycle 147)
157. ~~Inline triage from the attention lead (done 2026-06-12, cycle 147): SPA rows get a project select + file/dismiss buttons (react-query PATCH to /quick-capture/{id}/, dashboard query invalidated); classic rows get the same via a compact form POSTing to notes:triage, which now honors a safe `next` redirect (url_has_allowed_host_and_scheme, offsite rejected + tested) so it bounces back to /classic/. 9-check live battery across both shells ALL PASS; the 2 real inbox items untouched.~~
156. ~~Needs-attention in the SPA dashboard (done 2026-06-12, cycle 146): /api/v1/dashboard/ gained an `attention` block (overdue w/ plan URLs, deadlines w/ days_to_deadline, inbox texts — serialized in the existing endpoint, no second fetch) and Dashboard.tsx renders the same answer-first lead as the classic shell, "All clear" line included. Live-verified (overdue row + 2 triage links), API test added. Both shells now lead with the answer.~~
155. ~~card-title token sweep (done 2026-06-13): the standalone section-heading pattern (mb-2 + uppercase label classes) in literature/read + notes/note_detail (5 headings) converted to .card-title; a grep lint test (documents/tests/test_card_title_token.py) fails the build if it returns. Table headers + tight editor-rail labels with bespoke spacing intentionally exempt.~~
154. ~~Density lint (done 2026-06-12, cycle 144): core/tests/test_density_tokens.py fails the build on any template hand-rolling `rounded border border-stone-200 bg-white p-4/p-5` instead of class="card" (p-2/p-3/p-6 outliers stay legal) — and the sweep it forced converted all 33 offenders across 15 templates (dashboard, literature detail/report/read/import, notes, decisions, research ledger/experiments, pet, manuscript detail, editor research panel, comments, documents). All 8 affected pages browser-verified 200/no-errors/no-4xx.~~
153. ~~Shared density tokens (done 2026-06-12, cycle 143, shipped with the plan density pass): .card and .card-title component classes in app.css (@layer components, Tailwind v4 @apply) define the one card rhythm; project overview (4 cards) and the plan's phase cards converted as first consumers.~~
152. ~~Extend the escape guard to every raw-HTML sink (done 2026-09-07, #449: core/tests/test_html_sinks.py)~~ — original: extend the escape guard to the React islands' dangerouslySetInnerHTML (if any) and the classic templates' |safe filters — one grep-based "no unescaped sink" test covering every hand-built-HTML path, not just the editor glue (idea added by cycle 141)
151. ~~Central escape discipline for the glue (done 2026-06-12, cycle 141, tech improvement, from AUDIT #14): esc() hoisted to the top of latex-editor.js and applied to EVERY ${} inside an innerHTML template (the audit fixed the research panel; this swept the diagnostics list, hypotheses, and comment-date sites too — all now esc()'d even where the data is internal). A pytest guard (writing/tests/test_glue_escapes.py) greps the file and fails the build on any unescaped innerHTML interpolation — verified it catches a deliberately reverted escape. Immune by construction now, not by review.~~
150. ~~Editor 'Reset layout' (done 2026-06-13): a View-menu entry clears every atlas-editor-* localStorage key (split sizes, sidebar, preview, drawer, layout, zoom, settings) and reloads, restoring the default 3-pane layout; verified it wipes a custom arrangement back to defaults.~~
144. ~~Remember the last-picked layout name (done 2026-06-12, cycle 139, UI/UX, shipped with #147): atlas-editor-layout sticks on preset click and an indigo stroke-SVG check renders beside the active preset; ANY divergence — manual preview toggle, rail collapse, divider drag — clears it (applyingPreset flag keeps init restore + preset application from self-clearing). 9-check battery ALL PASS incl. reload persistence and drag-clears.~~
140. ~~Layout presets menu (done 2026-06-12, cycle 133, UI/UX): View menu gains a Layout section — ✍ Drafting (editor only, full width), ⇆ Reviewing (editor + PDF 50/50), ▦ Submitting (files + editor + PDF) — one-shot presets that seed the per-layout split keys and drive the same setSidebar/setPreview machinery as manual toggles. Fixed two latent bugs en route: the editor column never grew when it was the only pane (no flex-grow once Split.js is out of the picture), and a collapsed preview never survived reload (the init else-branch skipped hiding the pane). 8-check browser battery ALL PASS incl. reload persistence.~~
139. ~~Keyboard shortcuts in the menus (⌘↵ compiles since the studio; the ⌘⇧P palette shows every binding next to its action, 2026-09-07, #447)~~ — original: show the binding next to each menu item (Ctrl-F is there; add Ctrl-S save, Ctrl-Enter compile?) and actually bind compile to Ctrl-Enter like Overleaf (idea added by cycle 128)
138. ~~Click-collapse chevrons on the split gutters (done 2026-09-07, #458)~~ — original: Overleaf's thin-panel collapse/restore arrows on the Split.js dividers (Split.js .collapse(i) exists); pairs with the layout menu (idea added by cycle 127)
145. ~~Probe for 404s in the browser batteries (done 2026-06-12, cycle 136, shipped with #143): editor_smoke.py check 1 now fails on any >=400 response during mount (favicon tolerated) and prints the offending URLs — the class of bug that hid the Vite modulePreload 404 is now CI-visible.~~
137. ~~Slim the CM6 bundle (done 2026-06-12, cycle 134, tech improvement): the vim keymap is now a dynamic import — first-paint editor payload drops 208→172KB gz (-17%), with vim's 39KB gz fetched only when the keybinding is selected (named chunks: latex-editor-core-chunk/vim-keymap-chunk). Found and fixed a latent bug en route: Vite's modulePreload helper built URLs against the site base instead of /static/js/, firing a 404 per dynamic import — disabled the polyfill, native import() resolves module-relative. 9-check vim-lazy battery + SPA route check + editor smoke ALL PASS.~~
136. ~~Pet voice (the sidebar bubble's 🔊 speaks the line through /tts/; swept 2026-09-07)~~ — original (Owner idea #29): 🔊 on the pet speaks its line via the existing Piper /tts/ endpoint; optional spoken reaction in the hop moment behind a remembered mute toggle (idea added by cycle 122)
135. ~~CM6 migration sub-epic — execute docs/plans/2026-06-11-cm6-oss-migration.md slices A/B/C; closes #114 (offline editor) and deletes the hand-rolled snippet walker + hints (idea added by cycle 121, from the OSS plan)~~ (struck 2026-09-07, sweep #467: done — the editor is CodeMirror 6 (`frontend/src/editor`))
134. ~~OSS-replacement audit pass — a dedicated cycle that inventories Atlas's hand-rolled pieces (CM5 snippet walker, planned drag-resize, detex word count, difflib usage, the pet animation) and swaps in mature libraries where they're clearly better (Owner idea #28); pairs with the CM6 evaluation (idea added by cycle 120)~~ (struck 2026-09-07, sweep #467: closed — the CM6 migration (#135) removed the hand-rolled editor pieces; the rest are deliberate (detex count, difflib diffs, the pet))
133. ~~Sanitize zip member names centrally (done 2026-09-07, #453: `core/archives.py`)~~ — original: the submission-zip traversal guard is local to the view; a shared safe_archive_name() helper would cover any future zip/tar export (idea added by cycle 120, from AUDIT #12)
132. ~~Pet hatch animation (done 2026-09-07, #461)~~ — original: when the pet crosses a stage threshold (egg→hatchling etc.), play a one-time SVG transition (shell crack/burst) instead of just swapping the drawing (idea added by cycle 119)
131. ~~Include the .bbl in the submission zip (done 2026-09-07, #442: `--keep-intermediates`, `compiled_bbl`, `<main>.bbl` in submission.zip)~~ — original: persist the compiled .bbl (compile with --keep-intermediates and store it on the manuscript) so the arXiv package includes it for venues that don't run BibTeX (idea added by cycle 118)
130. ~~Resolve/strike line comments (done 2026-09-07, #439: `resolved_at`, PATCH, greyed rows, gutter marks only for open ones)~~ — original: let a line comment be marked resolved (greyed + dot hidden) so addressed feedback clears, like a review tool; the Comment model would need a resolved flag (idea added by cycle 117)
129. ~~Compile streak on the pet/timeline (done 2026-09-07, #460)~~ — original: a compiles-per-week sparkline (the data is now on the timeline) on the manuscript detail or as a Mochi reaction, turning the writing rhythm into a gentle signal (idea added by cycle 116)
128. ~~User-defined templates (done 2026-09-07, #446 as "Duplicate…": sources, assets, limits and bibliography links into a fresh manuscript; API + MCP)~~ — original: let the owner save any manuscript's current files AS a reusable template (a thin ManuscriptTemplate model or just "duplicate manuscript"), beyond the 6 built-ins (idea added by cycle 115)
127. ~~MCP figure upload (done 2026-09-07, #441: `attach_manuscript_figure`, multipart asset + includegraphics snippet)~~ — original: write_manuscript_file is text-only; add an MCP tool to attach a figure (multipart to manuscript-files asset) so Claude can complete a paper end-to-end incl. plots (idea added by cycle 114)
126. ~~Abstract peek in the panel (done 2026-09-07, #448)~~ — original: expand a bibliography row in the research rail to read the full abstract inline (the context endpoint already sends a 280-char snippet; show it on click) without opening the reference page (idea added by cycle 113)
125. ~~Cite-check across files (the cite checker reads every .tex file of the manuscript; swept 2026-09-07)~~ — original: the missing-citations check currently scans the active buffer only; aggregate unknown \cite keys across ALL tex files so a citation defined nowhere in a multi-file project is caught (idea added by cycle 112)
124. ~~Cite hint over MISSING papers (done 2026-09-07, #445: the completion's last row adds, links and cites by DOI / arXiv id)~~ — original: when \cite{} fragment matches nothing in the library, offer an "add by DOI…" inline action that reuses add_reference_by_doi, so writing never breaks to go hunt a paper (idea added by cycle 111, pairs with B2)
123. ~~Containerized Tectonic compile (escalated by AUDIT #11) — promote Backlog #36: now that multi-file \input exists, run the compile in a throwaway container/namespace; --untrusted + path validation cover single-user but a container boundary is the real fix before any multi-user use (idea escalated by cycle 110)~~ (struck 2026-09-07, sweep #467: closed with #36 — `--untrusted` + path validation; a container is out of scope for a single-user desktop app)
122. ~~Revision retention policy surfacing (done 2026-09-07, #456)~~ — original: show "kept: all labeled + last 50 auto" somewhere in the History panel and let the user bump the auto-cap, so the trim behavior isn't a surprise (idea added by cycle 109)
121. ~~Live word-count badge (the Studio status bar shows words and today's delta, #413; swept 2026-09-07)~~ — original: show the count passively in the status bar and refresh it on the autosave cycle (debounced) instead of only on button click, like Overleaf's always-visible count (idea added by cycle 108)
120. Classic-page density — the classic base.html still defaults to max-w-5xl; sweep the remaining classic-only pages (editor done) once the SPA density work lands, or accelerate their SPA migration (idea added by cycle 107)
119. ~~Editor command palette (done 2026-09-07, #447: ⌘⇧P actions palette with bindings)~~ — original: a small Ctrl/Cmd-P over editor actions (compile, find, toggle preview, new file, change keymap) so power users skip the mouse; pairs with the settings popover (idea added by cycle 106)
118. Density pass infrastructure — a shared dense-table CSS utility + tighter card padding tokens so the Owner-idea-#25 width/density work is consistent across pages instead of per-page tweaks (idea added by cycle 105)
117. ~~Context-aware completions (done 2026-09-07, #459: `editor/context.ts` scanner + boosts)~~ — original: rank \item first inside itemize/enumerate and \includegraphics inside figure (Overleaf's frequency data shows these dominate their environments); needs a tiny enclosing-environment scanner (idea added by cycle 104)
