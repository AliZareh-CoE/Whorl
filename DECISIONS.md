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
    ~~Comments on documents (2026-06-11, cycle 96): modal thread + live counts on every
    documents-table row, SPA and classic island both.~~ Remaining: comments on folders;
    selection-anchored PDF comments; LaTeX line-anchored comments in the editor.
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
    (Data / Pilot); 2 tests.~~ Remaining: drag rows between folders.
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
    real data-driven line.~~ Remaining: occasional blink/tilt, more habit signals (streak
    days, usual working hours), speech on hop.
17. **Professional tree illustration with more growth phases (owner, 2026-06-11; UI idea).**
    Redraw the project tree as a more polished, professional SVG illustration with more
    distinct phases than the current five — richer trunk/branch structure, layered foliage,
    smoother stage transitions; keep it server-rendered, deterministic, and accent-colored.
    ~~Slice 1 (2026-06-11, cycle 51): full redraw — 8 stages (seed→sprout→seedling→sapling→
    young→established→mature→bloom), filled tapered curved trunk with per-project lean,
    staggered tapered branches with foliage tufts at their tips, 3-depth-layer canopy
    (back/mid/front opacities) densifying with progress, soft ground mound + roots from 45%,
    white-and-gold blossoms at 100%; everything interpolates with percent; verified across
    all 8 stages in a rendered strip + on overview/grove.~~ Remaining: gentle CSS sway on
    bloom, seasonal variants (pairs with Backlog #50 grove seasons).

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
    milestone→"A milestone falls! *happy hop*", personality panel.~~ Remaining: species/
    hatching/rarity moment (idea #110).

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

## Loop rules (amendments to CLAUDE.md §5, owner-directed)

- **The backlog must never be empty.** Every loop cycle MUST append at least one new,
  concrete, valuable idea to the Backlog below before it ends — the loop runs forever.
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
266. ~~Desktop → SQLite (done 2026-06-17, owner-authorized: "if you see no fast solution then lets go sqlite!"). After a multi-day bundled-Postgres-on-Windows saga — each #265 diagnostic revealed a NEW Windows-specific Postgres bug (initdb exit 1, missing client tools, \\?\ prefix, console 0xC000013A crash loop, slow collectstatic, windowed stdin, psycopg connect hang, and finally a pg_ctl capture_output pipe-inheritance hang) — we switched the desktop app to SQLite, what every other single-user desktop app (Zotero, Obsidian, VS Code, Signal…) uses. config/settings/desktop.py now uses django.db.backends.sqlite3 (a file in the data dir, WAL mode); run_desktop dropped the ensure_postgres bring-up (migrate just creates the file → instant startup, no server/initdb/connection step). Postgres-only features degrade cleanly: the 4 trigram GinIndex migrations now use core.migration_ops.PostgresAddIndex (creates the index on Postgres, no-ops on SQLite — TrigramExtension already no-ops), and global search already falls back to icontains off Postgres (core/search.py). The web/server deployment keeps Postgres unchanged. Verified: fresh-SQLite migrate + check + run_desktop setup-only (195 static files, superuser, "Setup complete"); Postgres trigram search tests still pass. Parked #267 (strip the now-dead Postgres bundling — desktop_runtime.py + the pg binaries in the spec/CI + ATLAS_PG_BIN in the Rust shell — to shrink the installer).~~
265. ~~Owner desktop hang: instrument ensure_postgres (done 2026-06-17): the #263 diagnostic page worked — it showed Postgres UP/ready on 5433 but atlas-server.log EMPTY + 10-min timeout. Root cause: ensure_postgres was silent and wedged in the psycopg wait loop (libpq connect_timeout likely ignored on Windows → an unbounded silent block). Fix: flushed _log() at every step (never empty again) + a raw-socket _wait_for_tcp() precheck + a ThreadPoolExecutor-bounded psycopg connect (20s, shutdown(wait=False)) so a wedged connect RAISES (→ fast diagnostic) instead of hanging. Guard test. Remaining: confirm from the owner's NEXT diagnostic whether psycopg now connects (if it still times out at the bounded connect, the issue is libpq/psycopg in the frozen build — investigate the bundled libpq).~~
264. ~~AUDIT #24 (done 2026-06-16): full security+responsiveness pass — writable Protocol API is auth-gated/project-scoped/forge-proof; deps clean (starlette was a stale-venv false alarm, uv sync fixed); FIXED protocol_list O(n)→O(1) queries (load once + in-memory superseded set + lineage_cached, History gated on lineage_cached not the lazy .parent FK) + N+1 guard test. AUDITS.md #24 written.~~ Audit-cadence note: every ~10 slices → AUDITS.md; next ≈ AUDIT #25.
263. ~~Owner Windows desktop: show failures in-window (done 2026-06-16): the bundled-server launch failed silently behind WebView2's blank "can't reach this page", so we were debugging blind for many cycles. main.rs now opens a local splash, then a bg watcher navigates to the app on success or to a file:// diagnostic page (real atlas-server.log + postgres.log tails + data-dir + the VC++2013/MSVCR120 fix) on early child-exit or timeout. server.rs: tail_file + escape_html. cargo check clean; guard test. Build 0e012f2 green. Likely root cause surfaced by web search: missing Microsoft Visual C++ 2013 Redistributable (zonky pg binaries need MSVCR120.dll). Remaining: if the owner's diagnostic screenshot shows a different failure, fix that next.~~
262. Protocols on the SPA Research page (follow-on to #260): the React Research.tsx page lists hypotheses/experiments/datasets read-only (writes go to the classic pages); add a read-only "Protocols" section listing current protocols (GET /protocols/?project=) with their v{n} badge, mirroring the datasets section + the "add & edit on the classic page" affordance. ~~(Provenance half DONE 2026-06-16: ExperimentEntry.protocol FK (SET_NULL) → an entry records the exact protocol *version* it followed; scoped dropdown in the form, "Protocol: Title vN" link on the experiment log → #protocol-{pk}, protocol+protocol_label in the API, select_related to avoid N+1. Migration 0004; live-verified; 5 tests.)~~ Still open: the SPA read-only Protocols section.
261. ~~MCP tool-list drift (done 2026-06-16): the README "Tools:" list had drifted (missing all 11 manuscript/LaTeX tools + get_timeline) and the intro said "16 tools" when there are 37. Rewrote the README list (grouped by area) to cover every tool + fixed the count, and added mcp_server/tests/test_docs.py: it parses the @mcp.tool() function names from server.py and fails if any is undocumented or the count is wrong — so it can't silently drift again. 2 guard tests.~~ NOTE: there are 37 MCP tools but the spec §6 only mandated ~12; the tool set grew with the API (manuscripts, prompts, templates, file-workspace, figures-adjacent, protocols).
260. ~~Protocol library UI (done 2026-06-16): a classic Research-tab page (templates/research/protocols.html, mirroring datasets.html) reachable at /projects/{slug}/research/protocols/ — lists the current protocols (is_current head of each chain), each with a v{n} badge, markdown-rendered body, a "New version" link, and a History disclosure (Protocol.lineage walks the parent chain). research/views.protocol_list + ProtocolCreateView + protocol_new_version (GET prefills from the current version, POST appends a new version); ProtocolForm; 3 urls; a Protocols tab in research/_tabs.html. The research pages are the canonical create/edit surface (the SPA Research page links to them). 4 tests (lineage + list-shows-current + create + new-version). The SPA read-only section is parked as #262.~~
259. Richer commit linking (follow-on to #4): optionally fetch the commit's message/author/date from the GitHub/GitLab API (behind a huey task, cached on the entry) so the experiment log shows the commit subject, not just owner/repo@sha. Needs network + handling private repos/tokens — keep it opt-in and offline-tolerant. Also: a reverse "experiments touching this repo" view. Deferred — the pasted-URL link already covers the 80% (idea added during #4)
258. ~~Figure count on the project overview (done 2026-06-17): added "figures" to the overview API counts dict — one COUNT on documents with content_type in PREVIEWABLE_IMAGE_TYPES (the exact figures-feed whitelist, SVG excluded). The SPA overview already renders counts generically (Object.entries(data.counts)), so it appears automatically as a "figures N" stat; bumped the counts grid lg:grid-cols-7→8 so all 8 fit one row. Backend test asserts figures counts only images; live-verified; schema clean.~~
257. ~~Make the Figures page discoverable (done 2026-06-16): three entry points — (1) a "View as gallery →" link on the SPA Documents page header (where images are uploaded); (2) a page-aware "Figures" quick-action in the command bar / assistant context (core/assistant._actions, in-project), pointing at the SPA path /projects/{slug}/figures/; (3) registered `figures` in links.ts toSpaUrl so that action (and any classic link) navigates SPA-internally without a reload. Also fixed a latent UP017 lint in core/calendar.py (dt_timezone.utc → datetime.UTC) the newer ruff now flags. Assistant test asserts the Figures action + url; tsc clean, bundle rebuilt.~~
256. ~~Figure-gallery UI page (done 2026-06-16): app/pages/Figures.tsx — a calm React grid that fetches /projects/{slug}/figures/, groups thumbnails by folder, offers a tag-filter chip row, and opens a click-to-lightbox (full image + download/close) over each figure's nosniff'd raw_url. Empty state points to Documents. Wired the route in main.tsx + a Figures quick-link on ProjectOverview. tsc clean (0 errors; the 32 pre-existing src/editor errors were just an incomplete node_modules — npm ci fixed them), vite build regenerated spa.js + Figures-chunk.js, the route is in the bundle, and the /figures/ data was live-verified end-to-end in #8-data. Frontend slice; built artifacts committed.~~
255. The three inline/download file responses (document_download, document_preview, api raw) now all hand-set `Cache-Control: private, max-age=86400` + (where inline) nosniff. If a fourth file-serving path appears, a tiny `cacheable_file_response(handle, content_type, *, inline)` helper in documents/ would keep the immutability/cache/nosniff contract in one place (pairs with the #251 inline-safety helper idea). Low priority (idea added during #254)
254. ~~Cache-Control on the API raw inline endpoint (done 2026-06-16): DocumentViewSet.raw set nosniff but no Cache-Control, while document_download/document_preview both cache the same immutable files for a day — so the workspace PDF/image preview re-downloaded every view. Added `Cache-Control: private, max-age=86400` (uploads are immutable; edits create new files), matching the other two paths; extended the raw test to assert it. AUDIT #23 follow-on.~~
253. Subscribable calendar feed (follow-on to #9's calendar half): the .ics endpoint authes via the X-API-Key *header*, but real calendar apps (Google/Apple/Outlook) subscribe by URL and can't send custom headers. A read-only, revocable per-user feed token in the path (e.g. /calendar/{token}.ics, login_not_required, constant-time compared, scoped to deadlines only) would make it actually subscribable. Defer until after AUDIT #23 since it adds a URL-bearing credential — design the token rotation/scoping carefully (idea added during #9-calendar)
252. The doctor's worker/redis, static-css, optional-components (Tectonic/Piper), and media+api-key blocks are still inline in handle() like the desktop block was before #208. If handle() keeps growing, the same extract-to-_check_X() treatment (a small ordered list of self.* section methods) would keep it a readable table of contents. Low priority — only worth it if another section accretes sub-checks (idea added during #208)
251. Centralize the inline-preview safety contract: both paths (documents.views.document_preview #249 and api DocumentViewSet.raw #250) now independently (a) allowlist a content type and (b) confirm magic bytes before serving inline. A tiny shared helper — e.g. documents.preview.inline_response(file, declared_type) returning a nosniff FileResponse or None — would make the rule live in one place so a future third inline surface can't forget the byte check. Low priority; revisit if a third inline path appears (idea added during #250)
250. ~~Sniff bytes on the API raw inline endpoint too (done 2026-06-16): DocumentViewSet.raw picked its inline content_type purely from the file extension (.png → image/png) and never checked the bytes — the same mismatch class #249 closed for the document preview. It now reads the head, confirms it (sniff_image_type for rasters, a `%PDF-` check for PDFs), and 404s if the bytes don't match the extension-claimed type, so a mislabeled file (html named .png) can't reach the inline path. Reused documents.models.sniff_image_type; updated the existing raw test to a full PNG signature + added a mislabeled-extension 404 test.~~
224. ~~Windows desktop "127.0.0.1 refused to connect" (fixed 2026-06-14): the owner's install launched but the bundled server never served. Root cause: ensure_postgres passed `-k <socket_dir>` (a unix-socket path) inside pg_ctl's space-split `-o` string — Windows has no such socket and a username with a space splits the arg, so `pg_ctl start` failed, crashed run_desktop, and the window hit a blank ERR_CONNECTION_REFUSED. Fix: only pass `-k` on POSIX (the app connects over TCP loopback everywhere anyway); on a start failure raise a RuntimeError carrying postgres.log's tail; and tee the frozen server's stdout/stderr to <data-dir>/atlas-server.log (the windowed build has no console, so crashes were invisible — this also stops a stray print crashing on a None stdout). Pushing this rebuilds the installer for the owner to retry; 2 guard tests. (Can't run Windows here — fix is by code reasoning + the new log will confirm/deny if it persists.)~~
225. ~~Windows initdb.exe exits 1 (in progress 2026-06-14, #228): the atlas-server.log (the #224 logging worked!) showed initdb.exe runs but exits status 1 — so #224's socket fix was for a later step; the real failure is initdb itself, and my code didn't surface its stderr. #228 fixes three things: (1) _run now raises RuntimeError WITH stdout+stderr for EVERY pg helper, so the next log shows initdb's actual complaint; (2) a half-built pgdata (no PG_VERSION) from prior failed runs is rmtree'd before initdb (else "directory not empty" fails every retry); (3) the `\\?\` extended-length prefix Tauri puts on the binary path is stripped (initdb mis-resolves its share/ dir from it). Pushing rebuilds the installer. If still failing, the next atlas-server.log will name the exact initdb error.~~ Remaining for #225: main.rs should show a friendly in-app error page (with the log path) instead of the raw browser refused-to-connect.
229. ~~CI didn't rebuild on desktop server Python changes (fixed 2026-06-14): #228's fix lived in core/desktop_runtime.py, but desktop-release.yml's push paths were `desktop/**` + the workflow file only — so the installer never rebuilt and the owner would have re-tested an unchanged binary. The frozen server bundles core/desktop_runtime.py, run_desktop.py, config/settings/desktop.py and pyproject.toml, so those are now in the trigger paths (guard test added). I lack workflow_dispatch permission (403), so editing the workflow — which is in its own paths — is how I kick a build for a non-desktop/ change. (Broader app-model changes still won't auto-rebuild the desktop bundle; acceptable — those rarely need a desktop-only reship, and a version tag always rebuilds.)~~
231. ~~Windows: bundled Postgres has no client tools (fixed 2026-06-14, THE root cause): the owner's log proved #228's `\\?\` strip fixed initdb (it now succeeds) — the failure moved to `pg_isready not found`. The zonky windows-amd64 16.4.0 bundle ships ONLY initdb.exe/pg_ctl.exe/postgres.exe; NOT pg_isready/psql/createdb/createuser (verified by extracting the jar). ensure_postgres shelled out to pg_isready (wait), psql (db-exists), createdb (create) — all absent on Windows. Fix: do the readiness wait + `SELECT 1 FROM pg_database` + `CREATE DATABASE` through psycopg (already in the frozen server; migrate needs it) — no client-tool dependency, cross-platform (psycopg uses TCP loopback). Live-verified the wait+ensure logic end-to-end on the dev Postgres (create-if-missing + idempotent). Guard test forbids _pg_bin("pg_isready"/"psql"/"createdb"). The whole Windows saga was one onion: initdb-not-found(#210) → unix socket(#224) → \\?\ prefix(#228) → missing client tools(#231); no Windows machine needed — owner logs + jar inspection + live psycopg test diagnosed each.~~
211. (AUDIT #20) Tighten the bundled-Postgres auth — trust-auth on 127.0.0.1 lets any local process reach the desktop DB without a password (fine for single-user, matches file ownership). A unix-socket-only listener or a generated password would harden it; low priority (idea added by AUDIT #20)

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
185. Typeahead "no match" feedback — when the buffer matches nothing, the hint pill could flash red/shake briefly so it's clear the keystroke landed but found nothing, instead of silently holding focus (idea added during #168/#169)
184. Extend the typeahead hint pattern to the classic documents/folder tree (HTMX) — the React Files tree now has it; the server-rendered tree could get a small JS sprinkle for parity (idea added during #168/#169)
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
178. Documents-table empty/sparse state polish — with the wider layout a 3-row table leaves a lot of whitespace; a calmer empty-ish state or a max-height could tighten sparse projects (idea added during #171)
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
164. Audit-cadence note in PROGRESS — track 'milestones since last audit' explicitly so AUDIT #17 timing is unambiguous after the rollback-scrambled milestone numbering (idea added by AUDIT #16)
163. Reset-layout confirmation — Reset layout reloads immediately; a tiny inline confirm (or undo toast) would prevent an accidental wipe of a carefully-tuned arrangement (idea added during #150)
162. Pet speaks its mood+stage blurb on hover/click — the voice now varies by mood; let the pet optionally read its mood_blurb so you hear the personality, not just a fixed line (idea added during #149)
175. Editor chrome / writing board could reuse core/_nav_icon.html names where they overlap (writing, documents) so there's literally one icon source file, retiring any remaining bespoke inline SVGs (idea added during #173)
174. Persist + indicate keyboard focus across the subnav (roving tabindex / arrow-key tab traversal) now that it's a richer icon bar — small a11y win matching the Files-tree nav (idea added during #173)
173. ~~Lucide icons on the project context subnav (done 2026-06-13): all 11 tabs (Overview/Plan/Documents/Literature/Questions/Writing/Notes/Research/Graph/Decisions/Edit) now carry a calm Lucide glyph from core/_nav_icon.html (Literature reuses the library glyph); the bar wraps gracefully (flex-wrap) so the icons never overflow. 2 added guard tests (subnav↔partial lockstep). Screenshot reviewed: calm, Overview active.~~
172. Active-item icon tint — nav icons are uniformly stone-400; tinting the active item's icon with the accent (or stone-600) would reinforce "you are here" without extra chrome (idea added during #161)
161. ~~Lucide icons in the classic sidebar/nav (done 2026-06-13): a core/_nav_icon.html partial inlines the Lucide (MIT) stroke set so the classic Django sidebar shares the React workspace's icon language — Dashboard/Projects/Library/Writing/Prompts/Inbox/Assistant + the mobile menu button; ☰ and ✨ glyphs retired. 4 guard tests (base↔partial lockstep, no bare emoji, rendered). Screenshot reviewed: calm. Editor-chrome already done in #137; subnav split to #173.~~
159. ~~Vite 6→8 upgrade (done 2026-06-14): bumped vite ^6→^8 + @vitejs/plugin-react ^4→^6; npm audit --omit=dev now 0 vulns (esbuild advisory GHSA-gv7w-rqvm-qjhr closed). Vite 8 reshuffled chunk module-id matching so the chunkFileNames heuristics needed updating: the editor-core chunk is now the shared CodeMirror bundle (detect "codemirror", not just /src/editor/), and Vite 8's opaque "chunk"/"dist"/"index" fallback names map to a tidy "shared-chunk.js". Clean-rebuilt (rm islands/* first) so no stale orphans (removed client-chunk/index-chunk + the now-inlined TerminalPanel.css). tsc clean; all 5 key surfaces (SPA dashboard, Files, classic documents, library, latex editor) live-verified with zero JS errors / zero failed JS requests + screenshot.~~
160. ~~Harden the Tauri webview navigation allowlist (done 2026-06-13, from AUDIT #15): the desktop shell's WebviewWindowBuilder.on_navigation only permits the Atlas host (localhost), so a compromised loaded page can't steer the app window off-origin; cargo check passes, structural test asserts the guard.~~

(populated by phase gates; work top to bottom only after the Phase 6 gate passes)

1. In-browser PDF viewer with highlight-to-note
2. ~~Literature review matrix (papers × themes) (DEAD/already-done, swept 2026-06-16): the matrix exists — GET /api/v1/projects/{slug}/review-matrix/ ("which paper covers which theme") + a React review-matrix surface + seed_demo data. Nothing to build. Dead-idea sweep per #201.~~
3. Embedding-based related-paper suggestions
4. ~~GitHub commit ↔ experiment linking (done 2026-06-16): ExperimentEntry gained a commit_url URLField + a commit_label property that prettifies a GitHub/GitLab commit URL to owner/repo@shortsha (else the host). Wired through the form, admin list_display, the ExperimentEntrySerializer (read-only commit_label), the classic experiments.html (a ⎇ owner/repo@sha link), and the React Research experiment log. Pure pasted-URL link — no GitHub API call — so it's offline/host-agnostic. Migration 0002; live-verified the read path + label parse; 3 tests (label parsing across hosts, rendered link, form accepts url). The "fetch commit metadata" richer version stays parked as #259.~~
5. ~~Cmd+K command palette (DEAD/already-done, swept 2026-06-16): app/CommandBar.tsx is a complete Cmd/Ctrl+K palette — fuzzy jump-to-anything (subsequence scorer), real verbs (capture:, done:), page-aware quick actions from the assistant context endpoint, recents, and an "Ask Claude" MCP handoff. Bound to (metaKey||ctrlKey)+k in CommandBar. Already shipped back in cycle 65; nothing to build. Dead-idea sweep per #201.~~
6. ~~Auto-generated weekly review (DEAD/already-done, swept 2026-06-16): the weekly review exists — core/reviews.weekly_review() + WeeklyReviewAPIView (/api/v1/weekly-review/) + the React Review page (cross-project /review and scoped /projects/:slug/review, with week-back nav and a copyable digest). Nothing to build. Dead-idea sweep per #201.~~
7. ~~Protocol library with versioning — API-first slice done 2026-06-16: new research.Protocol model (project, title, body markdown, version, parent self-FK) — append-only, so editing means a new version: protocol.new_version(**overrides) clones with version+1 and parent set, and is_current = "no later version names me as parent" (head of the chain). Exposed as a WRITABLE DRF viewset /api/v1/protocols/ (the one research viewset that's writable — protocols are an MCP-managed, machine-friendly feature so Claude can author/revise them) with a POST {id}/new-version/ action; version+parent are read-only (the history chain can't be forged). Registered in admin + router; schema --fail-on-warn clean. Migration research/0003; live-verified create→new-version→list (v2 current, v1 superseded); 8 tests. Remaining: a classic/SPA project UI page (list current protocols + version history + edit-as-new-version) — parked as #260.~~
8. Results/figure gallery — ~~data layer done 2026-06-16 (API-first): GET /api/v1/projects/{slug}/figures/ returns every inline-previewable raster image in the project (newest first) — id, title, folder, tags, size, content_type, created_at + a `raw_url` that serves the image inline (reusing #250/#254). documents.selectors.project_figures is a pure, N+1-free selector (filter content_type startswith image/ in DB, exact preview_kind whitelist in Python, excludes SVG); API-key gated, project-scoped, schema-documented (--fail-on-warn clean). Live-verified end-to-end (uploaded a PNG → appeared in the feed → raw_url served image/png inline + nosniff + cache). 7 tests.~~ Remaining: the gallery UI page (#256) — a React grid of thumbnails linking to raw_url, grouped by folder, with a tag filter.
9. Email/calendar deadline reminders — ~~calendar half done 2026-06-16: GET /api/v1/projects/{slug}/calendar.ics/ exports the project's milestone due dates + manuscript deadlines as an iCalendar (RFC 5545) feed of all-day VEVENTs (core/calendar.py, a dependency-free generator with escape + 75-octet line folding; completed milestones marked ✓/CONFIRMED). Authed via the existing X-API-Key; schema validates with --fail-on-warn; live-verified (7 events on the demo project). 8 tests.~~ Still open: the email-reminder half (needs SMTP config) and a token-in-URL feed so a calendar app can subscribe without a header (see #253).
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
25. ~~Suggest keyboard nav (done 2026-06-11, cycle 45, UI/UX): ↑/↓ cycle a highlight through the sidebar suggestions (proper combobox/listbox roles + aria-activedescendant), Enter opens the active result, first Escape clears the list keeping focus, second blurs; browser-verified end to end. Recent-searches memory split out to Backlog #52.~~
26. ~~GIN trgm indexes (done 2026-06-11, cycle 46): GinIndex(gin_trgm_ops) on the five trigram-fallback columns (project.name, reference/note/document/decision title), migrations depend on core.0003_pg_trgm; fallback switched from `similarity()>0.25` (seq-scan only) to `__trigram_similar` (% operator, threshold 0.3) so the planner can use the indexes — EXPLAIN-verified Bitmap Index Scan; typo search re-verified live.~~
27. ~~MCP ETag cache (done 2026-06-11, cycle 47): the MCP client remembers ETag+body per GET (path, params), sends If-None-Match and reuses the cached body on 304 — verified [200, 304] live against the real API; client stays pure httpx (AST test green). Last-Modified on media split out to Backlog #54.~~
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
46. ~~Edge-swipe open (done 2026-06-11, cycle 48, UI/UX): touchstart within 24px of the left edge + >60px rightward swipe opens the drawer (window-level Alpine handlers); mid-screen swipes ignored — touch-verified at 420px.~~
47. ~~`make audit` (done 2026-06-11, cycle 91): scripts/audit.sh runs the anon-access + key-auth + #77-catch-all + open-redirect + pip/npm probes as one read-only command, exit-coded; every audit cycle starts here now.~~
48. Matrix gap column hints — show each theme's read-count in the review matrix header so gaps are visible there too, linking back to the gap-ordered queue (idea added by cycle 41)
49. More pet reactions — a sparkle on phase completion and a brief "om nom" when a reference is marked read, all through the same HX-Trigger pattern (idea added by cycle 42)
50. Grove seasons — paused projects show bare autumn trees and archived ones fade out, so the grove reflects the whole portfolio at a glance (idea added by cycle 43)
51. Template lint pass — a tiny pytest that walks every template and asserts title/breadcrumbs blocks contain no `<script>` (the cycle-44 corruption class), plus django-template syntax check via the loader (idea added by cycle 44)
52. ~~Recent searches (done 2026-06-11, cycle 48, UI/UX): submits store the query in localStorage (5 max, deduped); focusing the empty box lists them as a keyboard-navigable listbox (queries rendered via textContent), Enter re-runs the search — browser-verified.~~
53. Trigram index for the literature `?kw=` filter — reference.abstract icontains scans could use a GIN trgm index too once libraries grow past a few thousand rows (idea added by cycle 46)
54. Last-Modified/If-Modified-Since on media downloads (PDFs, documents) so re-reads are free (split from old #27) (idea added by cycle 47)
55. Pin a search — star a recent search to keep it permanently at the top of the recents dropdown (idea added by cycle 48)
56. Pet speech variety pack — seasonal/weekday lines and milestone-completion one-liners spoken in the hop moment via HX-Trigger payload (idea added by cycle 49)
57. Search page budget — /search/ sits exactly at the 50ms bar; profile the per-type rank queries and consider a single UNION query or smaller LIMIT_PER_TYPE (idea added by cycle 50, from AUDIT #5)
58. Tree tooltips — hovering a grove tree shows stage name + "n/m milestones" in a styled tooltip instead of the browser default (idea added by cycle 51)
59. ~~[REV] Atlas Assistant panel (done 2026-06-11, cycle 55 — the first revolutionary cycle): ✨ Assistant on every page — Cmd/Ctrl-K (or sidebar button) opens a calm slide-over React island; fuzzy jump-to-anything command bar (local subsequence scoring over a server-built index of projects/notes/references/prompts/manuscripts/pages, ≤400 entries, 5 queries); page-aware quick actions; 'Ask Claude about this' composes a context-rich MCP prompt (object + suggested atlas tools) with one-click copy; recent-activity feed for the current object. Backend: core/assistant.py + GET /assistant/context/ (session-gated). Built with parallel agent workflows per owner suggestion. NO paid APIs.~~ (idea added by cycle 52)
60. Bulk-bar keyboard shortcuts — x toggles selection on the focused row, shift-click selects ranges, Esc clears the selection (idea added by cycle 53)
61. Island dev-mode — `vite dev` proxy so island development gets HMR against the running Django server (idea added by cycle 54)
62. [REV] Synthesis studio — select N papers from the matrix and get a structured literature-synthesis scaffold (themes × claims × evidence table prefilled from reading notes + keywords, exportable to a manuscript section) — candidate for the next revolutionary cycle at 65 (idea added by cycle 55)
63. Assistant actions that act — POST quick actions in the panel (complete milestone, set reading status) with optimistic UI, reusing the bulk endpoints pattern (idea added by cycle 55)
63. SPA shell polish — pet widget, global search, and the assistant summon inside the React layout so /app/ feels complete while sections migrate (idea added by cycle 56)
64. SPA route prefetch — hovering a project card prefetches its overview query so navigation feels instant (idea added by cycle 57)
65. SPA plan editing — phase/milestone/task create+edit modals in React so the plan page reaches full parity and the classic page can retire (idea added by cycle 58)
66. CSS build gate — add `make css && git diff --exit-code static/css/app.css` to the cycle gate so Tailwind classes used by new TSX never ship missing (idea added by cycle 59, from the ml-56 bug)
67. SPA error toasts — surface failed optimistic mutations (e.g. PATCH rejected) with a calm inline toast + automatic state rollback instead of relying on the next refetch (idea added by cycle 60, from AUDIT #6 review of the optimistic-write path)
68. Server-side reference search — ?search= on /api/v1/references/ (title/key/venue/authors icontains) so the SPA library scales past one page (idea added by cycle 61)
69. Autosave for the SPA note editor — debounced PATCH 2s after typing stops, with the Saved indicator reflecting in-flight state (idea added by cycle 62)
70. Log submission events from the SPA — small add-event form on the manuscript timeline (kind, date, notes) via a SubmissionEvent API (idea added by cycle 63)
71. ~~Bulk milestone create (done 2026-06-11, cycle 71): POST /api/v1/milestones/ accepts a JSON list (many=True) and completed_at is settable at create — used immediately to plan future self-build cycles in one call. Friction-sourced from dogfood setup, now fixed.~~
72. ~~Milestone search (done 2026-06-11, cycle 71): ?q= filters milestones by title so scripts/SPA find one without fetching the whole plan. Friction-sourced from the first dogfood ship step.~~
73. ~~Command-index SWR cache (done 2026-06-11, cycle 77): the ⌘K bar's assistant-context (and plan) now load via React Query with staleTime — cached across opens, refreshed in the background. 3 opens → 1 fetch (was 3 fresh fetches); content paints instantly from cache. The plan query shares the Plan page's key so there's often zero extra fetch.~~
74. ~~[REV] Reading-flow mode (done 2026-06-11, cycle 75): /app/projects/:slug/read — keyboard-driven read-next session over the queue (1-4 reading status, n/p move, j quick-note, l listen TTS, Esc exit), one card at a time priority-ordered, progress bar, optimistic PATCH advancing on read/annotated; dedicated /reading-flow/ API. Flashcards for papers.~~
75. register_readonly API helper — one-liner read-only serializer+viewset+route for simple models; felt as boilerplate friction in cycle 66 (idea added by cycle 66, friction-sourced)
76. Route-level code splitting — React.lazy per SPA section so spa.js stays lean as pages accumulate; bundle grew 30→38KB gz in cycle 67 (idea added by cycle 67, friction-sourced)
77. ~~Shared route rule (done 2026-06-11, cycle 76): replaced the hand-mirrored SPA route list in core/urls.py with ONE catch-all — `^(?!api/|app/|static/|media/)(?!.*/$).+$` serves the shell for any slash-less path (classic keeps trailing-slash URLs). Adding a React page now needs zero Django changes; the cycle-74/75 drift class is gone. Tests cover unlisted pages served, classic intact, unknown /api/ still 404.~~
78. SPA decision detail — context/alternatives render in the timeline (saved now, shown truncated); felt while recording the cycle-69 decision (idea added by cycle 69)
79. ~~`make audit` (done 2026-06-11, cycle 91): scripts/audit.sh runs the anon-access + key-auth + #77-catch-all + open-redirect + pip/npm probes as one read-only command, exit-coded; every audit cycle starts here now.~~
80. ~~Bulk task create + search (done 2026-06-11, cycle 89): tasks endpoint mirrors milestones — POST a JSON list to create many (done settable at create), ?q= filters by title. The plan API is now uniform across milestones and tasks.~~
81. ~~SPA synthesis + coverage (done 2026-06-11, cycle 73): React literature page gets a Draft-synthesis button (X-SPA JSON → navigates to the note, no reload) and a coverage-gap nudge highlighting themes with ≤1 paper; closes Owner idea #11's active coverage-gap suggestion too.~~
82. ~~Coverage-gap → queue prefill (done 2026-06-11, cycle 94, UI/UX): thin themes in the nudge are clickable chips → `/queue?theme=X` shows unread candidates (theme words matched against title/abstract, already-marked excluded) via `theme_candidates` selector + `?theme=` on /api/v1/project-references/; quiet filter chip with Clear, NN/g-style filtered empty state; browser-verified.~~
83. PROMOTE #77 to next-priority — the shared route manifest; cycle 74 hit the exact predicted drift (React route added, Django pattern forgotten, 404). Do it before more routes accrue (idea escalated by cycle 74)
84. ~~Weekly research review (done 2026-06-11, cycles 84-85): data layer core/reviews.py + /api/v1/weekly-review/, then the SPA page at /review + /projects/:slug/review — a calm skimmable 'this week' digest (papers/notes/milestones/decisions/experiments, each linked), top-line summary, ◀▶ week-back nav, per-project + cross-project, sidebar 'Review' link. The self-build project's own review shows the loop's week.~~
85. Reading-flow for the whole library — a 'read flow' over any filtered reference set, not just one project's queue (idea added by cycle 75)
86. Promote the route rule to docs — note the slash-less=SPA / trailing-slash=classic invariant in CONTRIBUTING so external contributors don't re-add per-route Django patterns (idea added by cycle 76)
87. ~~Prefetch assistant index on mount (done 2026-06-11, cycle 78): Layout warms the ⌘K assistant-context query on app load, so even the very first ⌘K paints instantly.~~
88. ~~tl;dr in reading-flow (done 2026-06-11, cycle 79): 's' summarizes the current paper's abstract inline during a read session; resets on next/prev, in the key legend. The focused session is now Listen + tl;dr + note + status, fully keyboard.~~
89. ~~Seeded abstracts (done 2026-06-11, cycle 81): three demo references (incl. one to_read) now carry real abstracts, so tl;dr/Listen/reading-flow demo out of the box; closes the AUDIT #8 finding.~~
90. ~~Seeded abstracts (done 2026-06-11, cycle 81): three demo references (incl. one to_read) now carry real abstracts, so tl;dr/Listen/reading-flow demo out of the box; closes the AUDIT #8 finding.~~
91. Sample PDF for a to_read paper in seed_demo — so the PDF reader/iframe also demos in the reading-flow, not just the abstract (idea added by cycle 81)
92. Docs site (mkdocs-material) with the MCP setup guide front and center — next open-source slice after templates (idea added by cycle 82)
93. ~~Comments on documents (done 2026-06-11, cycle 96): document kind added to the comment allowlist (classic endpoint + /api/v1/comments/document/{id}/ both lit up); 💬 button with live count on every documents-table row opens a modal thread (ESC/backdrop/✕ dismissal, ⌘-Enter post) per owner modals rule + overlay-pattern research; counts piggyback on documents_table_props in one query; browser-verified post→persist→dismiss.~~
94. ~~Weekly-digest bot (done 2026-06-11, cycle 86): opt-in bot posts last week's summary (papers/notes/milestones/decisions/experiments counts) to the inbox via core/reviews.py; pairs the Review page with a Friday push. Quiet weeks post nothing.~~
95. ~~Research timeline (done 2026-06-11, cycle 95, [REV]): `core/timeline.py` aggregates 9 event kinds (milestones, papers added/read, notes, decisions, experiments, hypotheses, documents, manuscript events) into one stream; `GET /api/v1/projects/{slug}/timeline/` returns events + oldest-first markdown; MCP `get_timeline` tool; SPA `/projects/:slug/timeline` — vertical, color-coded, day/week/month zoom grouping, kind filter chips, copy-as-markdown; browser-verified with 41 live events.~~
96. ~~Review copy-as-markdown (done 2026-06-11, cycle 88): a 'Copy week' button on the Review page emits clean markdown (sectioned by papers/milestones/notes/decisions/experiments) for pasting into a lab journal or a Claude session.~~
97. ~~MCP weekly_review tool (done 2026-06-11, cycle 87): get_weekly_review(project, weeks_back) exposed over the MCP server (client fn + tool); Claude can pull 'what did I do this week' in chat. Verified live (30 milestones for self-build). Client stays pure httpx.~~
98. ~~MCP get_synthesis_scaffold (done 2026-06-11, cycle 93): read-only GET /projects/{slug}/synthesis/ (distinct from the note-creating POST) + MCP client fn + tool, so Claude can pull the theme-organized review scaffold to draft a section in chat — creates no note. Client stays pure httpx.~~
99. Per-section copy — small copy buttons on each Review section (e.g. just the milestones) for finer-grained pasting (idea added by cycle 88)
100. ~~Generic list-create+search mixin (done 2026-06-11, cycle 98, tech improvement): AtlasViewSet gains `q_fields` (?q= icontains-OR search) and `bulk_create` (JSON-list POST) knobs; milestones/tasks/prompts overrides collapsed to two-line declarations; notes, decisions, research questions, hypotheses, and datasets opted into ?q= for free; live-verified on notes and decisions; 3 new tests incl. ?q= no-op without q_fields.~~
101. ~~`make audit` (done 2026-06-11, cycle 91): scripts/audit.sh runs the anon-access + key-auth + #77-catch-all + open-redirect + pip/npm probes as one read-only command, exit-coded; every audit cycle starts here now.~~
102. ~~CI workflow (done 2026-06-11, cycle 92): .github/workflows/ci.yml runs ruff check+format, pytest (postgres service), frontend tsc, and a committed-assets-not-stale check on every push/PR — the loop's hand-run gate now guards contributions. README CI badge.~~
103. ~~CI make-audit job (done 2026-06-11, cycle 99, tech improvement): second CI job (postgres service, uv sync, migrate, runserver with a 30s readiness loop) runs `make audit` on every PR; audit.sh now prefers $ATLAS_API_KEY over .env so CI needs no dotfile; verified locally via the exact env-var-only path.~~
104. ~~Duplicate of #95 — shipped together in cycle 95.~~
105. Theme chips beyond the gap nudge — make every theme in the review matrix header link to its candidate queue, not just thin ones, so the prefilter is discoverable from the matrix too (idea added by cycle 94)
106. Design-notes file — a docs/DESIGN.md capturing the HIG-derived rules now binding (clarity/deference/depth, filtered-empty-state pattern, chip vocabulary) so every future UI slice starts from the same language (idea added by cycle 94, from the new owner design-research rule)
107. Timeline event detail expand — click a dot to expand the event in place (decision context, experiment body, note preview) without leaving the page (idea added by cycle 95)
108. Timeline on the overview — a 5-event mini-timeline strip on the project overview linking to the full page (idea added by cycle 95)
109. Comment threads from search — comments are invisible to global search; index comment bodies (FTS) so "where did I write that remark?" resolves (idea added by cycle 96)
110. Pet hatching & species — a one-time hatch moment (deterministic from the install, Buddy-style) choosing among a few species/looks, with a tiny shiny chance; pairs with #49/#56 (idea added by cycle 97)
111. Document the ?q= convention in the API schema — a reusable OpenApiParameter on every q_fields viewset so MCP/scripts discover searchability from /api/docs/ (idea added by cycle 98)
112. CI audit artifacts — upload /tmp/server.log and the sweep output as workflow artifacts on failure so red audit jobs are debuggable without rerunning (idea added by cycle 99)
113. API timing smoke in CI — extend the audit job with a best-of-5 latency check on 3 hot endpoints against the 50ms bar, so regressions like the cycle-100 N+1 surface in PRs not audits (idea added by cycle 100)
114. Vendor CodeMirror locally — the editor dies without internet (cdnjs); pull the CM5 assets into static/vendor/ like tailwind/tectonic/piper, felt when the sandbox proxy broke CDN loads during cycle-101 verification (idea added by cycle 101, friction-sourced)
115. Compile-queue dedupe — hash the source at queue time and skip the enqueue entirely when an identical-source compile is already running (the generation guard drops stale results; this would avoid the wasted compile too) (idea added by cycle 102)
116. PDF text layer in the editor preview — add pdf.js TextLayer (the literature reader already does it) so preview text is selectable/copyable; prerequisite niceness for SyncTeX click-to-jump in slice 7 (idea added by cycle 103)
149. ~~Pet voice personality — mood layer (done 2026-06-13): MOOD_VOICES in core/tts.py sets loudness/liveliness from the pet's weekly mood (sleeping 0.6 → thriving 1.0 + extra noise_w) on top of the stage's pace/timbre (volume-only so they compose); read_aloud passes both stage+mood; real WAVs verified distinct per mood; 4 tests incl. MOODS↔MOOD_VOICES sync + compose.~~
142. ~~Pet voice personality (done 2026-06-12, cycle 138, Owner #29 follow-on): STAGE_VOICES in core/tts.py shapes Piper delivery per growth stage — egg murmurs slow+soft (length 1.25, noise 0.45), hatchling peeps fast (0.8, lively phoneme timing), scholar is the voice as trained, sage is slow+measured (1.18) — and read_aloud derives the stage server-side from pet_state(). Real-voice durations verified distinct (1.94s/2.25s/2.59s for the same sentence); live endpoint 200 audio/wav; 4 new tests incl. a STAGES↔STAGE_VOICES sync guard.~~
148. Icon sweep for the rest of the app — the editor chrome now speaks one stroke-SVG language; the classic sidebar/pages still mix glyphs (✨ Assistant, ⌘K, section headers); a templatetag or include for the icon set would let every surface share it (idea added by cycle 137)
146. ~~Inline-SVG icon sweep for the editor chrome (done 2026-06-12, cycle 137, UI/UX, parity plan cycle 6): Recompile ↻, zoom-fit ↔, upload ↑, File-menu ⬇, the three layout-preset glyphs, the PDF/research ⇄ toggles, and the 💬 comment gutter marker (now a .comment-dot stroke-SVG chat bubble in the CM6 island) all replaced with the rail's monochrome stroke-icon language. Ω stays — it labels the symbol palette semantically. 12-check battery + editor smoke ALL PASS, screenshot reviewed.~~
147. ~~Audit-sweep output as a CI artifact (done 2026-06-12, cycle 139, shipped with #144): make audit tees to /tmp/audit-output.txt under set -o pipefail (exit code preserved, verified locally) and the file joins the failure() artifact upload — completes #112.~~
143. ~~Smoke artifacts on CI failure (done 2026-06-12, cycle 136, tech improvement, shipped with #145): any failed check — or a crash before the checks even run (try/except around the whole battery) — writes editor-smoke.png (full page), the browser console log, and the failure list to SMOKE_ARTIFACT_DIR; ci.yml uploads them via actions/upload-artifact on failure() together with /tmp/server.log. Verified both paths live: green run leaves nothing, a forced bad-password run exits 1 with all three artifacts written.~~
141. ~~Editor-page Playwright smoke in CI (done 2026-06-12, cycle 132, tech improvement): scripts/editor_smoke.py — a 6-check headless battery (mount w/ zero CDN editor assets, autosave, multi-file switch preserving buffers, line comment + gutter dot, cite autocomplete, compile wiring incl. graceful no-tectonic failure) distilled from the cycle-126 cutover battery; self-seeding via X-API-Key on an empty DB; wired into the CI audit job (createsuperuser --noinput, playwright chromium, no Redis needed — dev huey is immediate). ALL PASS locally.~~
158. Undo for inline triage — a filed/dismissed attention row vanishes immediately; a 5-second "undo" toast (PATCH processed:false) would make the inline action worry-free (idea added by cycle 147)
157. ~~Inline triage from the attention lead (done 2026-06-12, cycle 147): SPA rows get a project select + file/dismiss buttons (react-query PATCH to /quick-capture/{id}/, dashboard query invalidated); classic rows get the same via a compact form POSTing to notes:triage, which now honors a safe `next` redirect (url_has_allowed_host_and_scheme, offsite rejected + tested) so it bounces back to /classic/. 9-check live battery across both shells ALL PASS; the 2 real inbox items untouched.~~
156. ~~Needs-attention in the SPA dashboard (done 2026-06-12, cycle 146): /api/v1/dashboard/ gained an `attention` block (overdue w/ plan URLs, deadlines w/ days_to_deadline, inbox texts — serialized in the existing endpoint, no second fetch) and Dashboard.tsx renders the same answer-first lead as the classic shell, "All clear" line included. Live-verified (overdue row + 2 triage links), API test added. Both shells now lead with the answer.~~
155. ~~card-title token sweep (done 2026-06-13): the standalone section-heading pattern (mb-2 + uppercase label classes) in literature/read + notes/note_detail (5 headings) converted to .card-title; a grep lint test (documents/tests/test_card_title_token.py) fails the build if it returns. Table headers + tight editor-rail labels with bespoke spacing intentionally exempt.~~
154. ~~Density lint (done 2026-06-12, cycle 144): core/tests/test_density_tokens.py fails the build on any template hand-rolling `rounded border border-stone-200 bg-white p-4/p-5` instead of class="card" (p-2/p-3/p-6 outliers stay legal) — and the sweep it forced converted all 33 offenders across 15 templates (dashboard, literature detail/report/read/import, notes, decisions, research ledger/experiments, pet, manuscript detail, editor research panel, comments, documents). All 8 affected pages browser-verified 200/no-errors/no-4xx.~~
153. ~~Shared density tokens (done 2026-06-12, cycle 143, shipped with the plan density pass): .card and .card-title component classes in app.css (@layer components, Tailwind v4 @apply) define the one card rhythm; project overview (4 cards) and the plan's phase cards converted as first consumers.~~
152. Extend the escape guard to the React islands' dangerouslySetInnerHTML (if any) and the classic templates' |safe filters — one grep-based "no unescaped sink" test covering every hand-built-HTML path, not just the editor glue (idea added by cycle 141)
151. ~~Central escape discipline for the glue (done 2026-06-12, cycle 141, tech improvement, from AUDIT #14): esc() hoisted to the top of latex-editor.js and applied to EVERY ${} inside an innerHTML template (the audit fixed the research panel; this swept the diagnostics list, hypotheses, and comment-date sites too — all now esc()'d even where the data is internal). A pytest guard (writing/tests/test_glue_escapes.py) greps the file and fails the build on any unescaped innerHTML interpolation — verified it catches a deliberately reverted escape. Immune by construction now, not by review.~~
150. ~~Editor 'Reset layout' (done 2026-06-13): a View-menu entry clears every atlas-editor-* localStorage key (split sizes, sidebar, preview, drawer, layout, zoom, settings) and reloads, restoring the default 3-pane layout; verified it wipes a custom arrangement back to defaults.~~
144. ~~Remember the last-picked layout name (done 2026-06-12, cycle 139, UI/UX, shipped with #147): atlas-editor-layout sticks on preset click and an indigo stroke-SVG check renders beside the active preset; ANY divergence — manual preview toggle, rail collapse, divider drag — clears it (applyingPreset flag keeps init restore + preset application from self-clearing). 9-check battery ALL PASS incl. reload persistence and drag-clears.~~
140. ~~Layout presets menu (done 2026-06-12, cycle 133, UI/UX): View menu gains a Layout section — ✍ Drafting (editor only, full width), ⇆ Reviewing (editor + PDF 50/50), ▦ Submitting (files + editor + PDF) — one-shot presets that seed the per-layout split keys and drive the same setSidebar/setPreview machinery as manual toggles. Fixed two latent bugs en route: the editor column never grew when it was the only pane (no flex-grow once Split.js is out of the picture), and a collapsed preview never survived reload (the init else-branch skipped hiding the pane). 8-check browser battery ALL PASS incl. reload persistence.~~
139. Keyboard shortcuts in the menus — show the binding next to each menu item (Ctrl-F is there; add Ctrl-S save, Ctrl-Enter compile?) and actually bind compile to Ctrl-Enter like Overleaf (idea added by cycle 128)
138. Click-collapse chevrons on the split gutters — Overleaf's thin-panel collapse/restore arrows on the Split.js dividers (Split.js .collapse(i) exists); pairs with the layout menu (idea added by cycle 127)
145. ~~Probe for 404s in the browser batteries (done 2026-06-12, cycle 136, shipped with #143): editor_smoke.py check 1 now fails on any >=400 response during mount (favicon tolerated) and prints the offending URLs — the class of bug that hid the Vite modulePreload 404 is now CI-visible.~~
137. ~~Slim the CM6 bundle (done 2026-06-12, cycle 134, tech improvement): the vim keymap is now a dynamic import — first-paint editor payload drops 208→172KB gz (-17%), with vim's 39KB gz fetched only when the keybinding is selected (named chunks: latex-editor-core-chunk/vim-keymap-chunk). Found and fixed a latent bug en route: Vite's modulePreload helper built URLs against the site base instead of /static/js/, firing a 404 per dynamic import — disabled the polyfill, native import() resolves module-relative. 9-check vim-lazy battery + SPA route check + editor smoke ALL PASS.~~
136. Pet voice (Owner idea #29) — 🔊 on the pet speaks its line via the existing Piper /tts/ endpoint; optional spoken reaction in the hop moment behind a remembered mute toggle (idea added by cycle 122)
135. CM6 migration sub-epic — execute docs/plans/2026-06-11-cm6-oss-migration.md slices A/B/C; closes #114 (offline editor) and deletes the hand-rolled snippet walker + hints (idea added by cycle 121, from the OSS plan)
134. OSS-replacement audit pass — a dedicated cycle that inventories Atlas's hand-rolled pieces (CM5 snippet walker, planned drag-resize, detex word count, difflib usage, the pet animation) and swaps in mature libraries where they're clearly better (Owner idea #28); pairs with the CM6 evaluation (idea added by cycle 120)
133. Sanitize zip member names centrally — the submission-zip traversal guard is local to the view; a shared safe_archive_name() helper would cover any future zip/tar export (idea added by cycle 120, from AUDIT #12)
132. Pet hatch animation — when the pet crosses a stage threshold (egg→hatchling etc.), play a one-time SVG transition (shell crack/burst) instead of just swapping the drawing (idea added by cycle 119)
131. Include the .bbl in the submission zip — persist the compiled .bbl (compile with --keep-intermediates and store it on the manuscript) so the arXiv package includes it for venues that don't run BibTeX (idea added by cycle 118)
130. Resolve/strike line comments — let a line comment be marked resolved (greyed + dot hidden) so addressed feedback clears, like a review tool; the Comment model would need a resolved flag (idea added by cycle 117)
129. Compile streak on the pet/timeline — a compiles-per-week sparkline (the data is now on the timeline) on the manuscript detail or as a Mochi reaction, turning the writing rhythm into a gentle signal (idea added by cycle 116)
128. User-defined templates — let the owner save any manuscript's current files AS a reusable template (a thin ManuscriptTemplate model or just "duplicate manuscript"), beyond the 6 built-ins (idea added by cycle 115)
127. MCP figure upload — write_manuscript_file is text-only; add an MCP tool to attach a figure (multipart to manuscript-files asset) so Claude can complete a paper end-to-end incl. plots (idea added by cycle 114)
126. Abstract peek in the panel — expand a bibliography row in the research rail to read the full abstract inline (the context endpoint already sends a 280-char snippet; show it on click) without opening the reference page (idea added by cycle 113)
125. Cite-check across files — the missing-citations check currently scans the active buffer only; aggregate unknown \cite keys across ALL tex files so a citation defined nowhere in a multi-file project is caught (idea added by cycle 112)
124. Cite hint over MISSING papers — when \cite{} fragment matches nothing in the library, offer an "add by DOI…" inline action that reuses add_reference_by_doi, so writing never breaks to go hunt a paper (idea added by cycle 111, pairs with B2)
123. Containerized Tectonic compile (escalated by AUDIT #11) — promote Backlog #36: now that multi-file \input exists, run the compile in a throwaway container/namespace; --untrusted + path validation cover single-user but a container boundary is the real fix before any multi-user use (idea escalated by cycle 110)
122. Revision retention policy surfacing — show "kept: all labeled + last 50 auto" somewhere in the History panel and let the user bump the auto-cap, so the trim behavior isn't a surprise (idea added by cycle 109)
121. Live word-count badge — show the count passively in the status bar and refresh it on the autosave cycle (debounced) instead of only on button click, like Overleaf's always-visible count (idea added by cycle 108)
120. Classic-page density — the classic base.html still defaults to max-w-5xl; sweep the remaining classic-only pages (editor done) once the SPA density work lands, or accelerate their SPA migration (idea added by cycle 107)
119. Editor command palette — a small Ctrl/Cmd-P over editor actions (compile, find, toggle preview, new file, change keymap) so power users skip the mouse; pairs with the settings popover (idea added by cycle 106)
118. Density pass infrastructure — a shared dense-table CSS utility + tighter card padding tokens so the Owner-idea-#25 width/density work is consistent across pages instead of per-page tweaks (idea added by cycle 105)
117. Context-aware completions — rank \item first inside itemize/enumerate and \includegraphics inside figure (Overleaf's frequency data shows these dominate their environments); needs a tiny enclosing-environment scanner (idea added by cycle 104)
