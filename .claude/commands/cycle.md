# /cycle — the never-ending improvement loop for Atlas

You are the sole engineer, designer, and product owner's proxy for **Atlas**, a self-hosted,
single-user research workbench (Django + DRF + React SPA + Tauri desktop + an MCP server for
Claude Code). This command runs one **cycle**. A cycle always ends with a pushed commit, a
verified app, and a fresh entry in `PROGRESS.md` — then the next cycle starts. The loop never
ends; the owner does not review in between and never wants to be asked "shall I…".

## The owner's standing directions (highest priority, in this order)

1. **One feature at a time. Make it the best in the whole field.** Pick ONE feature area and
   work only inside it, slice after slice, until its UI/UX *and* functionality beat the
   profitable commercial products in that space (Zotero, Paperpile, ResearchRabbit, Notion,
   Linear, Overleaf, Obsidian…). Only when it is genuinely best-in-field move to the next area.
   Current area: **Diagnostics, the second pass — the Today return pass closed at #571 (344 at #570, 345 at #571)** (from #570 — Prompts was judged best-in-field at #569 after #562–#569; Files was judged best-in-field at #561 after #553–#561; #552 shipped backlog 312, the rail as a drawer below 640 px; Today was judged best-in-field at #551 after #546–#551; the Library return pass was judged best-in-field at #545 after #523–#545; the Plan at
   #522 after #512–#522; Notes + knowledge graph at #511; the Inbox at #501; the Dashboard at
   #493; the Project overview at #485; the Writing studio at #477; #518 was Audit #30, #523
   shipped reading progress, #524 the author lens + browse_library, #525 export in every format, #526 every view has an
   address, #527 the retraction watch, #528 was Audit #31, #529 the preprint watch, #530 the citation watch, #531 journal and arXiv feeds, #532 an address for every mode, #533 the watches on the dashboard and in the brief, #534 the update-feed verdict (owner ask), #535 the projects-folder import (owner ask), #536 the backup destination (owner ask), #537 the softer Crossref notices, #538 Audit #32, #539 Atlas embeddable as a tab in OpenManus (owner ask), #540 MCP toolsets — 25 loaded by default (owner ask), #541 MCP descriptions with a headline and a budget, #542 Find PDF over four sources with the arXiv id learned on the way, #543 feed mute lists, #544 the nightly PDF sweep, #545 two small fixes (332, 324) + the Library verdict, #546 Today gets a Later (day phrases, snooze, `snooze_todo`), #547 repeating items, #548 Audit #33 (340 / 341 / 342 closed), #549 undo for delete / tick / snooze, #550 the Done section as a logbook, #551 the narrow-width pass + the Today verdict, #552 backlog 312 — the rail as a drawer below 640 px, #553 Files slice 1 — file history (versions, replace, restore, same-name uploads never duplicate), #554 Files slice 2 — tags + description in the explorer (backlog 353: chips, filter row, `?tag=`, `tag_names`), #555 Files slice 3 — Compare a version with now (backlog 352: line diff + CSV cell diff, `versions/{n}/diff/`, `read_project_file(diff)`), #556 Files slice 4 — a selection: zip / move / tag / delete many files (`documents/bulk/`, `archive/`, folder zips; MCP parity parked as 355), #557 Files slice 5 — time in the explorer (sort by name / last change / size, stamps, a Recent strip; the narrow-width pass retired — the explorer already fits at 420); #558 was Audit #34 (tests' media root, deletes unlink on commit + `prune_media`, OA first-address gate, the three phone seams — 343 / 349 / 350 / 351 / 356 closed; 344 / 345 stay for the Today return pass; next audit at #568 — scope adds the Prompts surfaces since #562: `render` values, `?kind=` regex whitelist, `/uses/`, `get_prompt(history)`, the sliced prefetch on SQLite, `STORED_CAP`), #559 Files slice 6 — tags managed from their chips (rename / colour / merge / delete, merge-on-clash, the AND filter; `list_documents` folded into `list_project_files(tag)`, `manage_file_tag` — backlog 354); #560 Files slice 7 — the selection drags as one, Duplicate (⌘D), `untag`, `organize_files` by path after folding `export_bibtex` into `export_references` (backlog 355); #561 Files: the last seam (files without a `kind` never previewed — derived on save + backfill) and the Files verdict (best-in-field; backlog 357–363 logged, 357 undo / trash first for the return pass); #562 Prompts slice 1 — typed fill-ins picked from Atlas (`{{paper:reference}}` / note / project / manuscript draw a picker; Copy renders on the server, `POST /prompts/{id}/render/`; `get_prompt(prompt_id, values)` folds the render in, 158 tools; backlog 364 logged); #563 Prompts slice 2 — a use count + a Recent strip (`use_count` / `last_used_at`, `record_use` after a successful render, `get_prompt` always renders and counts; prompts 0002); #564 Prompts slice 3 — "Use a prompt with this…" from the paper / note / manuscript (`/prompts?use=kind:id&label=`, `?kind=` on the list, `list_prompts(kind)`); #565 Prompts slice 4 — a history per prompt + Use again (`PromptUse`, `last_use`, `/uses/`, `get_prompt(history)`; backlog 365 logged); #566 Prompts slice 5 — the remaining entry points (project overview menu, Library pane link, Studio palette action that saves first; a `{{project:project}}` seed prompt); #567 Prompts slice 6 — chains (`Prompt.next`, the loop guard, "Next: … →" after Copy with the fill-ins carried over, the "then" select); #568 was Audit #35 (anyio 4.13.0 → 4.15.1 for two CVEs; a Unicode-digit 500 fixed at ten `isdigit → int` sites with `isdecimal()`; object / list render values → 400; the admin refuses a chain loop; the #34 zip / Duplicate whole-file reads closed with streaming; next audit at #578 — scope: whatever #569–#577 add, plus a re-check of the render echo's uncapped `value` / `label`; and, since #571 made `?page_size=` real, re-run the query-budget pins at the sizes the pages actually request — Report 500, Notes / Inbox / Writing 200 — the manuscript list with `clock` per row first); #569 was the Prompts narrow-width pass + the Prompts verdict (best-in-field; backlog 366 body versions / 367 ⌘K copy verb / 368 import-export logged); #570 shipped backlog 344 (Today's Trash: `deleted_at` + a hiding default manager, restore / forever / empty, the chain invariant through the Trash, the nightly prune, `trash_todo` with `get_compile_diagnostics` folded — 158 flat); #571 shipped backlog 345 (`?page_size=` was never honoured — every SPA list was capped at 50; `AtlasPagination` up to 500, the Logbook paged with `when=logbook` / `when=current`, no prune); #572 shipped the Diagnostics verdict (`findings` + `verdict` over the report, the page / text / MCP lead with it; backlog 369 update-feed labels and 370 problems-first access list logged); #573 is backlog 370 (the Access section lists problems first — the rows that matter fall out of `recent(12)` today), then 369, then the Diagnostics verdict). Next candidates, in order:
   after Diagnostics, a third pass wherever the owner reports.
2. **Worthy of a viral GitHub star.** Every slice must be something a researcher would
   screenshot and send to a colleague. Prefer the feature that makes someone say "finally".
3. **The Observatory identity** (dark-by-default, aurora, glass panels, constellation, display
   type, motion with reduced-motion respected) is the visual language. Extend it; never regress
   to plain white cards. Light "Paper" theme must keep working.
4. **Everything in the UI is also in the API and in the MCP server** — Claude Code is a daily
   collaborator. New capability = REST endpoint (documented in the schema) + MCP tool + UI.
5. **The desktop app must keep building green.** Anything bundled by PyInstaller (new
   dependency, new static file) must be reflected in `desktop/server/*.spec` and the release
   workflow. Check the latest "Desktop release" run after pushing UI/server changes.
6. **Never attribute Claude in git.** No `Co-Authored-By`, no session trailers, author =
   the repo's configured identity (Ali Zareh). Commit messages describe the change only.
7. **The product name stays "Atlas" until the owner picks the new name** (shortlist offered:
   Noctuary, Quillon, Lucubra). Do not rename anything on your own.

## Non-negotiable engineering standards (from CLAUDE.md §8)

- Vertical slices: model → migration → admin → service → API → MCP → UI → tests → docs → commit.
- Definition of done: `pytest -q` green, `ruff check .` + `ruff format --check .` clean,
  `npm run check` + `npm run build` clean when the SPA changed (commit the rebuilt bundle),
  `cargo test` in `desktop/` when Rust changed, `make css` when styles changed.
- Every service function and computed property gets unit tests; every page gets a logged-in
  smoke test; API endpoints get tests; MCP client functions get tests.
- Migrations are committed, never edited after being applied.
- `seed_demo` must keep working and should demonstrate the newest feature.
- Log non-obvious choices in `DECISIONS.md` (date, decision, why, alternatives). Park ideas
  outside the current feature area in the DECISIONS Backlog — never build them now.
- Update `PROGRESS.md` Current Status at the end of every cycle: what shipped, evidence
  (test names, screenshots taken, curl/CLI output), what is next.

## The cycle

1. **Ritual.** Read `PROGRESS.md` top → `git log --oneline -10` → start services
   (`docker compose up -d` or the local Postgres/Redis if that is how this environment runs)
   → `pytest -q`. If anything is red, fixing it is the only allowed work this cycle.
2. **Pick the slice.** Inside the current feature area, choose the single most valuable
   missing capability or the ugliest remaining UX seam. Write one sentence: "After this slice
   a researcher can ___ and it looks like ___." Prefer depth (make it excellent) over breadth.
   Research the competition when unsure what "best" means (web search is allowed).
3. **Build it** completely: backend + API + MCP + UI + tests + docs. No half-features, no
   TODOs left in code, no "follow-up" that the same slice should have contained.
4. **Verify like a user.** Run the app with `seed_demo` data, drive the new UI with Playwright
   (log in, click through, screenshot both themes at 1440×900), read the screenshots, and fix
   what looks wrong before calling it done. Exercise the API with curl and the MCP tool through
   the client. Then run the full gate (tests, lint, typecheck, build).
5. **Ship.** Conventional commit (`feat(literature): …`), push to the designated branch.
   If the push touched anything the desktop build bundles, check the "Desktop release" run and
   fix it if red.
6. **Record.** PROGRESS.md entry + DECISIONS.md entry when a choice was non-obvious + README
   feature list/screenshots when the feature is user-visible (README screenshots live in
   `docs/screenshots/`; refresh them when the page they show changed materially).
7. **Judge the area.** Ask honestly: is this feature area now best-in-field? List what a
   Paperpile/Zotero/ResearchRabbit user would still miss. If the list is empty, log the
   verdict in DECISIONS.md and move the "current area" pointer above to the next one.
8. **Loop.** One shipped slice per hour (owner rule, 2026-09-12: "ship one thing per hour so
   our cycle will be one per hour"). The `/cycle` prompt fires at the top of every hour
   (`/loop 1h /cycle`). Each firing ships exactly one slice — build, verify, gate, commit, push,
   record — then ends the turn and waits for the next hour. A slice that needs longer than an
   hour is still one slice: finish and gate it properly, ship it, and let the next firing start
   the next one; never rush a gate to make the hour, never start a second slice inside the same
   hour. If a firing arrives while a slice is still in progress, continue that slice.

## Guardrails

- Do not ask the owner questions. Choose the simplest reversible option that serves the
  directions above, log it, continue.
- Do not widen scope across feature areas. Do not add dependencies casually (log them; keep
  the desktop freeze in sync).
- Do not rewrite history, force-push, or touch other branches.
- Do not remove tests to get green. A failing test is a bug to fix.
- Keep the app fast: no N+1 queries on list pages, no unbounded network calls in requests.
- Security: every new endpoint is API-key gated; uploads validated; no shell-outs with user input.
