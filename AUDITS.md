# AUDITS

Every 10th loop cycle is a full security + performance audit (owner rule). Reports newest first.

## Audit #9 — cycle 90 (2026-06-11), covering loop cycles 81–89 (weekly review, comments, MCP)

**Clean again — no findings.** Second consecutive no-fix audit; the surface stayed tight.

**Security (verified live):**
- New endpoints — weekly-review, comments (GET/POST), reading-flow — all 401 anonymously.
- Comments API: session POST without CSRF → 403; unknown kind → 404; empty body → 400;
  5000-char cap (tested). Bots-action write still CSRF-gated.
- weekly_review's `weeks_back` is clamped 0–52 and tolerates garbage input (`?weeks_back=abc`
  → 200, defaults to 0) — no unbounded date math or 500s.
- **Bulk-create scoping checked:** the milestone/task list-POST goes through DRF's
  `PrimaryKeyRelatedField`, so a nonexistent phase/milestone FK → 400 (verified), not a
  silent attach or 500. Single-user means there is no cross-tenant phase to leak into.
- **#77 catch-all re-probed:** `/app//evil.com/x` stays local (open-redirect fix holds),
  `/api/v1/nonsense` 404s, static serves correctly. The route rule continues to hold.

**Dependencies:** `pip-audit` (frozen) + `npm audit` (prod+dev): **zero known vulnerabilities**.

**Performance:** SPA shell `/` and `/review` ~12 ms; weekly-review 22–24 ms (global and scoped);
comments 14 ms. All under the 50 ms bar. **weekly_review query cost: 5 queries global, 6 scoped**
— one per model plus the project lookup, no N+1 (select_related throughout); locked in with a
new `django_assert_max_num_queries(8)` budget test. Bundles: spa.js 29 KB gz, the Review page
chunk a tidy 1.8 KB gz.

**Verdict:** healthy. No fixes needed; the cycle-84 weekly-review data layer powers four surfaces
(page, bot, MCP, copy-export) without a perf or security cost. 431 tests green, lint + tsc +
assets-check clean.

## Audit #8 — cycle 80 (2026-06-11), covering loop cycles 71–79 (post-cutover features + dogfooding)

**No findings — a clean audit.** The catch-all routing (#77) and the disciplined dogfood
workflow meant the surface was already tight; every probe came back as designed.

**Security (all verified live):**
- New API surfaces — manuscripts, hypotheses/experiments/datasets, bots, pet, reading-flow —
  all 401 anonymously. Research endpoints are read-only (POST blocked; the existing test
  asserts 405, and a session POST without CSRF 403s before even reaching the method check).
- Bots action endpoint (the only new *write* surface): session POST without a CSRF token → 403.
- **#77 route catch-all re-probed:** the cycle-70 open-redirect fix holds — `/app//evil.com/x`
  stays local (`→ /evil.com/x`); `/api/v1/nonsense` still 404s (the catch-all excludes `api/`);
  `/static/js/spa.js` serves as `text/javascript`; unknown slash-less paths serve the shell
  (React renders its own 404, no data leak); classic trailing-slash pages unaffected.
- X-SPA JSON branches (bulk docs/literature, synthesis, summarize) and command-bar verbs all
  route through the authenticated, CSRF'd `api()`/fetch path and are project-scoped by the same
  viewsets as the rest of the API.

**Dependencies:** `pip-audit` (frozen) + `npm audit` (prod+dev): **zero known vulnerabilities**.

**Performance:** SPA shell `/` 13 ms; new JSON endpoints 9–21 ms (dashboard 9, pet 12, bots 16,
reading-flow 16, hypotheses 18, manuscripts 21) — well under the 50 ms bar. **Bundles:** spa.js
29 KB gz + shared React chunk 46 KB gz (initial ~75 KB, cached); 21 lazy page chunks total 33 KB
gz, fetched 1–3 KB on first visit — the code-splitting (cycle 69) is holding the growth flat as
pages accumulated. Query budgets green.

**Process note:** three cycles (71, 74, 75) needed a follow-up commit because test/format steps
ran out of order; the pre-commit discipline (build + format + lint-fix BEFORE `git add`) and the
post-push sync check are now standing chain instructions and have held since.

**Verdict:** healthy. First no-fix audit — the route-rule refactor (#77) removed the bug class
that the prior two audits' findings traced back to. 411 tests green, lint + tsc + assets-check clean.

## Audit #7 — cycle 70 (2026-06-11), covering loop cycles 61–69 (SPA completion + cutover)

**Headline finding — open redirect (found + fixed):** the cutover's `/app/*` bookmark
redirect built its target as `f"/{rest}"`, so `/app//evil.com/x` produced `//evil.com/x` —
a protocol-relative URL that browsers follow OFF-SITE (confirmed: 302 → `http://evil.com/x`).
Fixed by collapsing leading slashes (`"/" + rest.lstrip("/")`), so it can only ever stay
local; regression test added. This is exactly the kind of bug the cutover introduced and
the reason every 10th cycle audits the new surface.

**Everything else on the cutover surface is clean:**
- Anon sweep: `/`, every slash-less SPA route, `/classic/`, `/automations`, and the `/app/*`
  redirects all 302 to login; all JSON endpoints (incl. new bots/pet/manuscripts/hypotheses)
  401 anonymously.
- Bots action endpoint: session POST without a CSRF token → 403 (SessionAuthentication +
  CSRF holds for the new write surface too).
- Link interceptor reviewed: only acts on same-origin `href` values starting with `/`
  (no `javascript:`/`data:`/absolute-URL vectors reach it); modified-click and target/download
  anchors are passed through untouched.
- Command-bar verbs (`capture:`/`done:`) go through the authenticated CSRF'd api() helper and
  are project-scoped by the same viewsets as the rest of the API.
- Lazy chunks served as `text/javascript`. Research/experiment/dataset endpoints are read-only
  (POST → 405, tested).

**Dependencies:** `pip-audit` (frozen) and `npm audit` (prod+dev): **zero known
vulnerabilities** in both ecosystems.

**Performance:** SPA shell `/` 13 ms; the JSON diet 13–26 ms (dashboard 26, plan 17,
documents-table 19, bots 14, pet 19, manuscripts 24, hypotheses 18); classic `/classic/`
38 ms. All under the 50 ms bar. **Bundles after code-splitting (cycle 69):** initial load is
spa.js 29 KB gz + shared React chunk 46 KB gz = ~75 KB; 19 page chunks total 60 KB gz,
fetched 1–3 KB at a time on first visit. Query budgets green.

**Verdict:** healthy. One real open-redirect found and closed same-cycle — the audit cadence
earned its keep. 398 tests green, lint + tsc + assets-check clean.

## Audit #6 — cycle 60 (2026-06-11), covering loop cycles 51–59 (the SPA era)

**The SPA auth surface (headline focus — all verified live with curl):**

- Auth matrix exactly as designed: anon → `/app/*` 302s to login, JSON endpoints 401;
  API key GET/POST work (CSRF-exempt by design — header auth, not cookies); session GET 200;
  **session POST without a CSRF token → 403**; anon X-SPA bulk POST → 403.
- The SPA shell sets the csrftoken cookie (`ensure_csrf_cookie`, regression-tested after the
  cycle-58 find); the `api()` helper redirects 401/403 to login rather than failing silently.
- Assistant context endpoint probed with hostile paths (`/../../etc/passwd`, `//evil.com/x`,
  encoded traversal, unknown routes): every probe returns the generic context — no leaks,
  no 500s, resolution is wrapped exactly as intended.
- Modal mixin HX-Redirect reviewed: success URLs are always server-built via reverse() —
  no user-controlled redirect target. X-SPA JSON path consumes the flash queue (tested),
  so no message leakage across UIs.

**Dependencies:** `pip-audit` (frozen env) and `npm audit` (prod AND dev deps): **zero known
vulnerabilities** in both ecosystems.

**Performance (warm, live):** classic pages 23–37 ms; SPA shell 11 ms; the SPA's JSON diet —
dashboard 27 ms, plan 18 ms, overview 29 ms, documents-table 20 ms, assistant context 29 ms.
All far under the 50 ms bar. Bundles (gzipped): spa.js 28.7 KB, shared React chunk 45.6 KB
(loaded once, cached), CSS 7.1 KB. Query budgets green.

**Process fix shipped with the audit:** `make assets-check` (Backlog #66) rebuilds CSS+JS and
fails if committed outputs are stale — the cycle-59 `ml-56` class of bug is now machine-caught.

**Verdict:** healthy. No findings requiring fixes — the cycle-58 CSRF-cookie and cycle-59
stale-CSS bugs were caught and fixed in their own cycles by live verification, and the
audit confirms the repairs hold. 382+ tests green, lint + tsc clean.

## Audit #5 — cycle 50 (2026-06-11), covering loop cycles 41–49

**Performance:** warm curl timings — dashboard 45 ms, projects 22 ms, overview 41 ms, plan 36 ms,
literature 34 ms, gap-ordered queue 37 ms, library 31 ms, prompts 20 ms, automations 26 ms,
pet 17 ms, full search 50 ms (right at the bar — watch it), trgm-backed suggest 43 ms.
Query budgets green; the GIN trgm indexes (cycle 46) keep typo search index-served.

**Security findings (both fixed same-cycle):**

- **`Project.color` had no format validation** — any ≤7-char string reached
  `style="background: …"` attributes (grove, progress bars). Autoescaping prevents attribute
  breakout and 7 chars of CSS is inert, but belt-and-braces: a `#rrggbb` RegexValidator now
  enforces the format at the model level, covering both the form and the API serializer
  (tests for both paths).
- **MCP ETag cache was unbounded** — one entry per distinct (path, params) could grow without
  limit in a long-lived MCP session. Now capped at 256 entries, oldest dropped.

**Reviewed clean:** pet speech (autoescaped everywhere incl. title attrs; phase names are the
only user-influenced content), recent searches (localStorage only, textContent rendering,
encodeURIComponent hrefs), edge-swipe (no injected state), queue gap badges (autoescaped),
GIN migrations (declarative, no raw SQL), ETag values (server-controlled, single client).
Anonymous sweep: every page 302s to login; API and schema 401; docs 302.
`pip-audit` (uvx, frozen env): **no known vulnerabilities**.

**Verdict:** healthy. Two hardening fixes, no exploitable findings. 349 tests green, lint clean.

## Audit #4 — cycle 40 (2026-06-11), covering loop cycles 31–39

**Performance:** warm timings measured live with curl on every hot page — dashboard 42 ms,
projects 21 ms, overview 39 ms, plan 33 ms, literature 33 ms, notes 27 ms, library 33 ms,
prompts 22 ms, automations 29 ms, inbox 27 ms. All under 50 ms (owner's lightning-fast bar).
API ETag round-trip re-verified live (`If-None-Match` → 304). Query-budget tests green;
keyword-cloud cache (cycle 35) keeps the literature page flat.

**Security findings:**

- **Schema/docs exposure (fixed — headline finding):** `/api/schema/` and `/api/docs/` were
  `login_not_required` since Phase 2 and served the full API description to anonymous users.
  Two layers fixed: the schema endpoint now requires a session **or** a valid `X-API-Key`
  (constant-time compare, 401 + `WWW-Authenticate` otherwise) so MCP tooling still works; the
  Swagger docs page is `login_required` — notably, **DRF APIViews opt out of Django's
  `LoginRequiredMiddleware`**, so the gate must be explicit. Live-verified all five
  combinations; regression tests added.
- **Mentions XSS probe (clean):** hostile note titles `x](javascript:alert(1))` and
  `"><img src=x onerror=alert(1)>` pushed through resolve_mentions → markdownify: nh3 strips
  the `javascript:` href and the `onerror` handler; nothing executes. The markdown-link
  construction cannot escape the sanitizer.
- Reviewed clean: prompt `{{variables}}` (client-side clipboard substitution only, no DOM
  writes); bot charts (autoescaped title attrs, server-side int heights); keyword-cloud `?kw=`
  (parameterized ORM, autoescaped reflection); TTS Listen (input capped at MAX_TTS_CHARS);
  swipe handlers (no injected state). Auth sweep: every page 302s to login anonymously.
- Low-risk note: OpenAlex discover interpolates DB-sourced DOIs/work-ids into the request
  path — host is pinned to api.openalex.org, worst case is a malformed GET there. Accepted.
- `pip-audit` (uvx, 63 pinned packages): **no known vulnerabilities**.

**Process finding:** the shared `client` fixture is mutated by `client_logged_in`
(force_login on the same instance) — tests needing both must construct a fresh `Client()`.

**Verdict:** healthy. One real auth gap found and closed same-cycle. 327 tests green, lint clean.

## Audit #3 — cycle 30 (2026-06-11), covering loop cycles 21–29

**Performance:** query counts stable across every page (originals unchanged; reader 5q,
matrix 6q, prompts/automations 4q, pet 2q, suggest 9q cold). No regressions; budget tests green.

**Security review of cycles 21–29:**

- ETags (21): weak, derived from count+max(updated_at)+path — no data leakage, vary correctly
  with query params (tested). OK.
- `rotate_api_key` (22): local CLI, no web surface. OK.
- Bots (23): registry allowlist + crash-safe runner re-verified; `run_now` for network bots is
  synchronous in-request — accepted for single-user, noted for a future task offload.
- **Tectonic compile (24): threat model documented.** Subprocess uses list args (no shell),
  temp-dir cwd, 180 s timeout; Tectonic runs without shell-escape. Residual accepted risk:
  LaTeX `\input` of absolute paths could read host files readable by the app user — irrelevant
  while the only author is the owner, revisit if Atlas ever becomes multi-user (noted in
  Backlog as a containerized-compile hardening idea).
- Page comments (25): open-redirect guard re-verified by tests; page parses via isdigit. OK.
- Summarize (26): login-gated, POST-only, 50 k cap. OK.
- Compile-status endpoint (27): session-gated, project-scoped. OK.
- **Docker packaging (29): image hygiene verified live** — no `.env`, `media/`, or
  `tts_voices/` baked into the image; container venv intact (`.dockerignore` doing its job);
  build-time SECRET_KEY used only for collectstatic. `ATLAS_BEHIND_TLS` documented as
  localhost-only relaxation.
- `pip-audit` (now incl. gunicorn, whitenoise): **no known vulnerabilities**.

**Process finding:** cycle 29 briefly pushed a lint-red commit because the verify chain didn't
gate the commit command; fixed within minutes. Loop rule reinforced: commit only after an
explicit green echo from the full verify chain.

**Verdict:** healthy. 297 tests green, lint clean.

## Audit #2 — cycle 20 (2026-06-11), covering loop cycles 11–19

**Performance:** all original pages within budget (library 6q, plan 7q, overview 13q — unchanged);
new pages cheap: prompts 4q, automations 3q, pet page 2q, suggest endpoint 9q cold. Dashboard is
53q cold (pet + heatmap caches empty in the audit harness) but steady-state-cached and guarded by
budget tests. All hot pages remain <100 ms warm.

**Security findings:**

- **XSS (fixed):** the LaTeX editor injected cite keys via `json.dumps` + `|safe`; a hostile
  `cite_key_override` containing `</script>` could escape the script block. Replaced with
  Django's `json_script` (HTML-safe escaping) + a regression test asserting the payload stays
  inert. This is the audit's headline catch.
- Reviewed clean: prompts CRUD (login+throttle), bots (POST-only, slug allowlist, crash-safe
  runner), comments (nh3-sanitized markdown, kind allowlist, 5 000-char cap), pet rename (40-char
  cap, exception-safe context processor), tree (percent clamped, color attribute auto-escaped),
  bulk upload (per-file size validation, folder scoping), rename/move (project-scoped, 404s
  verified), search suggest (auto-escaped reflection, length-gated).
- `pip-audit`: **no known vulnerabilities** across the full environment.

**Notes carried forward:** trigram fallback runs unindexed (fine at single-user scale; add GIN
trgm indexes if the library passes ~50k rows); `run_now` on retraction-watch is synchronous
network in-request (acceptable single-user; move to task if it ever feels slow).

**Verdict:** healthy. 265 tests green, lint clean.

## Audit #1 — cycle 10 (2026-06-11), covering loop cycles 1–9

**Performance (re-run of the cycle-4 query audit + timings, seeded data, warm):**

| Page | Queries | Time | Weight |
|---|---|---|---|
| Dashboard `/` | 40 (28 = heatmap aggregates, 10-min cached in practice) | 99 ms | 37 KB |
| Library | 6 | 38 ms | 21 KB |
| Project overview | 13 | 70 ms | 11 KB |
| Plan | 7 | 58 ms | 22 KB |
| Review matrix | 6 | 61 ms | 61 KB |

No query-count regressions vs the cycle-4 baselines; all hot pages < 100 ms server-side.
Query-budget regression tests still guard the worst N+1 candidates.

**Security review of surfaces added in cycles 1–9:**

- PDF reader highlight endpoint: project-link scoping verified by tests; **finding:** highlight
  text length was uncapped → **fixed**: 2000-char limit (400 otherwise) + regression test.
- OA auto-download: fetches only arXiv direct URLs or Unpaywall-returned locations; **finding:**
  Unpaywall URL scheme unchecked → **fixed**: https-only + regression test. `%PDF` magic check
  and 50 MB cap were already in place.
- TTS endpoint: login-required, POST-only, 5000-char cap — OK.
- Suggested tags: POST-only, project-scoped, 60-char cap — OK.
- Review matrix toggles: project-scoped (404 cross-project, tested) — OK.
- Login throttle re-verified live in cycle 5 (5 fails → 429, correct password refused during
  lockout). DRF throttles active (3000/h keyed, 30/h anon).
- Dependency CVEs: `pip-audit` over the full environment → **no known vulnerabilities**.

**Carried forward:** Backlog #11 (ETags/conditional GETs), #16 (audit log page), responsive
sidebar (#15). Dashboard heatmap query count is structural (14 models × 2 fields) and cached;
revisit only if the dashboard ever feels slow.

**Verdict:** healthy. 212 tests green, lint clean.

## Audit #10 — cycle 100 (2026-06-11)

Scope: everything since audit #9 (cycles 91–99): `make audit` script + CI job, research
timeline endpoint + MCP tool, `?theme=` candidate filter, AtlasViewSet `q_fields`/
`bulk_create` knobs (5 newly searchable resources), comments on documents, Buddy-style
pet payload.

**Probe sweep (`make audit`): clean.** Anonymous 401 on all new API surfaces (timeline,
synthesis, themed project-references, document comments, ?q= resources); keyed access 200;
catch-all and static MIME intact; `/app//evil.com/x` stays on-origin; pip-audit and
npm audit both zero known vulnerabilities. The sweep now also runs in CI on every PR
(cycle 99), so drift between audits gets caught at review time.

**Edge inputs:** 5000-char `?theme=` (capped 120) and SQL-ish metacharacters → 200, no
errors (ORM-parameterized icontains). Bogus comment kinds and missing object ids → 404.

**Findings & fixes (2):**
- `/api/v1/project-references/` ran **48 queries** for a 22-paper project (N+1: nested
  reference serializer + project slug field) and clocked 58 ms — over the 50 ms bar →
  **fixed**: `select_related("reference", "project")` → 4 queries, 23 ms. Regression
  budget test added (≤8 queries).
- `?q=` accepted unbounded input (the older `?theme=` was capped) → **fixed**: stripped
  and capped at 200 chars in `AtlasViewSet.get_queryset`; cap test added.

**Performance spot-checks (best of 5, dev server):** SPA shell 1 ms · overview 31 ms ·
timeline 31 ms (10 queries / 41 events, budget test added at ≤14) · project-references
23 ms (post-fix) · pet 14 ms (cached). All under the 50 ms bar.

**Carried forward:** #57 (search page at the 50 ms boundary), #53 (trgm index when
libraries grow), #36 (containerized Tectonic if multi-user ever happens).

**Verdict:** healthy — two real findings, both fixed and regression-guarded in-cycle.
457 tests green, lint clean.

## Audit #11 — cycle 110 (2026-06-11)

Scope: everything since audit #10 (cycles 101–109) — the entire LaTeX workbench
(compile diagnostics + log parser, autosave/in-place compile + compile_generation guard,
pdf.js preview, autocomplete/snippets, find/replace + keymaps + settings, the multi-file
workbench, word count, version history) and the Owner-idea-#25 density/full-width changes.

**Probe sweep (`make audit`): clean.** pip-audit and npm audit both zero known
vulnerabilities; anonymous/keyed/catch-all/open-redirect/static-MIME all intact.

**Workbench endpoint authz:** every classic file/word-count/revisions view 302s to login
for anonymous users; the DRF manuscript-files viewset 401s. All file/revision views are
scoped through `project.manuscripts` → `manuscript.files`/`manuscript.revisions`, so a
bogus or cross-manuscript id 404s (verified: revision diff on id 999999 → 404).

**Path traversal (the highest-risk surface):** `../evil.tex`, `/etc/passwd`, and
`..\evil` are rejected 400 by both the DRF serializer and the classic create endpoint
(validate_manuscript_path: ASCII-only, no dotfiles/.., depth-capped). Defense in depth:
compile's `_write_tree` resolve()-guard refuses any row that escapes the build dir even if
it bypassed validation (tested: bulk_created hostile row → compile FAILED, nothing
written). Compile runs Tectonic with `--untrusted`. Uploads are size-capped (50 MB,
shared validate_upload_size) and extension-whitelisted; disallowed types (.exe/.html) 400.

**Performance (best of 5, dev server, all under the 50 ms bar):** editor page 25 ms ·
dashboard 15 ms · word-count 21 ms. Query-budget regression tests (7) green; no new N+1s
(the project-references select_related from audit #10 holds).

**Findings & fixes:** none — clean audit (first since audit #9's pair of no-fix audits).

**Carried forward:** Backlog #36 (containerized/namespaced Tectonic) rises in priority now
that multi-file `\input` exists — `--untrusted` + path validation are solid for single-user,
but a container boundary is the right answer if Atlas ever goes multi-user. Revision JSON
storage is bounded per-manuscript by the keep-50-auto trim; revisit only if it grows.

**Verdict:** healthy. The workbench's security-sensitive surfaces (path handling, upload,
sandboxed compile) are guarded in depth and tested. 522 tests green, lint clean.

## Audit #12 — cycle 120 (2026-06-11)

Scope: everything since audit #11 (cycles 111–119) — library cite-autocomplete
(cite-library), live cite-check, research side panel (context), MCP LaTeX tools
(client + server + word-count @action), timeline compiles, line-anchored comments
(manuscript_file in the Comment allowlist), arXiv submission zip, templates gallery,
and the inline-SVG pet.

**Probe sweep (`make audit`): clean.** pip-audit + npm audit zero CVEs.

**Authz:** every new classic surface (cite-library, context, submission.zip) 302s to login
for anonymous users; the new DRF surfaces (comments/manuscript_file, manuscripts/word-count,
manuscript-files) 401 without a key and 200 with one. All scoped through
project→manuscript→file, so cross-manuscript/cross-project ids 404 (cite-library link of a
Reference outside the project 404s — tested cycle 111).

**MCP LaTeX tools:** the AST import-constraint test still passes — client.py imports remain
⊆ {os, datetime, httpx} (compile_and_wait polls via a datetime deadline, no time import).
The tools wrap existing key-authed DRF endpoints; no new auth surface. The compile loop
writes only through manuscript-files (path-validated) and reads source_text()/diagnostics —
no shell/injection path.

**Edge inputs:** context `?q=<script>` → 200, ORM-parameterized icontains (no injection);
cite-library cross-project link → 404; comment line accepts only digits (else null).

**Finding & fix (1):** the submission-zip builder emitted entry names straight from
ManuscriptFile.path. Those are validated on create, but a row injected past validation
(admin/bulk_create) could place a `..`/absolute name in the archive (an extraction-time
traversal risk for whoever unzips). **Fixed:** the zip now skips any entry whose path is
absolute or contains a `..` segment, with a regression test (hostile bulk_created row →
excluded, main.tex still present).

**Performance (best of 5, all under the 50 ms bar):** cite-library 24 ms · context 24 ms ·
submission.zip 24 ms · /pet/ 19 ms. Query budgets + MCP client tests green (26).

**Pet SVG:** static template markup; the only interpolated value is the pet name in an
aria-label (auto-escaped by Django). No XSS surface.

**Verdict:** healthy — one defense-in-depth fix (zip traversal guard), everything else
clean. 545 tests green, lint clean.

## Audit #13 — cycle 130 (2026-06-12)

Scope: everything since audit #12 (cycles 121–129) — the error-log relocation, the entire
CodeMirror 6 migration (island + glue rewrite + cutover), the new npm dependencies, Split.js
panels with collapse chevrons, the File/Edit/Insert/View toolbar, the Ctrl-Enter binding,
and the container-snapshot-rollback recovery.

**Probe sweep (`make audit`): clean.** pip-audit + npm audit zero known vulnerabilities —
including an explicit npm audit after adding the editor dependencies.

**New dependencies (Owner rule #28):** codemirror/@codemirror/*, @replit/codemirror-vim,
codemirror-lang-latex, split.js — **all MIT**, all pinned via package-lock, all bundled
locally by the existing Vite pipeline (no new build infrastructure, no CDN). Net effect of
the migration: ~250 lines of hand-rolled editor code deleted, 15 CDN tags removed, and the
offline-editor availability bug (#114) closed.

**Authz unchanged and verified:** the editor page and its endpoints (cite-library, files,
manuscript_file comments) still 302/401 anonymously; the cutover touched no backend auth.

**CSRF:** the island's only mutating fetch (the cite auto-link POST) carries X-CSRFToken
from config; all nine mutating fetches in the glue carry it. `window.editor` exposes only
read/write of the current document to same-origin scripts — no new surface.

**Performance:** authenticated editor page 21 ms server-side (dashboard 13 ms) — well under
the 50 ms bar. The CM6 bundle is 203 KB gzipped (the Lezer LaTeX grammar dominates); accepted
as a one-time cached cost for the editor page, with #137 (manualChunks / lazy vim) open if it
ever matters. Query-budget + MCP AST-constraint tests green (26).

**Resilience note:** this stretch survived a container snapshot rollback that reverted the
workdir and DB ~20 cycles; recovery was a fetch + hard-reset because every cycle had been
pushed. The watchdog and chain prompts now carry the recovery rule (check git log first,
reset to origin, npm install, revive services).

**Findings & fixes:** none — clean audit.

**Verdict:** healthy. The CM6 migration shipped with authz, CSRF, and performance intact,
and the dependency posture is exactly what rule #28 wants: pinned, MIT, locally bundled.
545 tests green, lint clean.

## Audit #14 — 2026-06-12, cycle 140 (covers cycles 131–139, commits 2f61908..2503e1b)

**Scope:** pet voice (TTS endpoint + stage-shaped delivery), CI editor smoke + failure
artifacts + 4xx/5xx probe, layout presets + active-layout check, vim lazy chunk +
modulePreload:false, the left icon rail, and the stroke-SVG icon sweep.

**TTS surface (`POST /tts/`):** anonymous → 403 (LoginRequiredMiddleware + CSRF), text capped
at MAX_TTS_CHARS=5000 before synthesis, response is `Cache-Control: no-store`. The growth
stage is derived server-side from `pet_state()` — the client cannot select a voice shape.
Piper is a library call on plain text; no shell, no injection vector.

**CI artifacts carry no secrets:** `audit.sh` uses `$KEY` only in request headers and never
echoes it; the smoke's console log captures browser console output (no key logging exists in
the editor JS); `server.log` is runserver request lines (keys travel in headers, not URLs).
The seeded CI credentials (`ci-smoke-pass`, `ci-audit-key`) are job-local throwaways.

**FINDING (fixed in-cycle): stored XSS via external metadata in the research panel.**
`renderContext`/`renderNotes` interpolated reference titles, authors, bibtex keys, hypothesis
statements, and note titles into `innerHTML` unescaped. Titles arrive from Crossref/OpenAlex
and BibTeX imports — external data. Proven live: a reference titled
`<img src=x onerror=window.__xss=1>` would have executed (single-user session, so
self-XSS-by-upstream — low severity, real bug). Fixed with an `esc()` helper on every
interpolation; re-tested live with the hostile title — renders literally, nothing executes.
Everything else on the page already used `textContent` (comments, diagnostics messages, file
tree), and manuscript file paths are constrained to `[A-Za-z0-9._-]` by the model validator,
so the diagnostics `d.file` interpolation cannot carry HTML.

**Icon rail / presets / icon sweep:** pure client-side UI on existing authz'd pages; the
CommentMarker `innerHTML` is a static SVG constant; new localStorage keys are all
`atlas-editor-*` namespaced.

**Dependencies (rule #28):** 145 packages locked; codemirror-lang-latex 0.4.1, 
@replit/codemirror-vim 6.3.0, split.js 1.6.5 — MIT. `pip-audit` and `npm audit` clean
(via `make audit`, which also re-verified anon-401/302, key auth, the #77 catch-all, and
the open-redirect guard — all green). vim-keymap-chunk and the core chunk are local files;
the smoke's 4xx/5xx probe now guards the loading topology that modulePreload:false fixed.

**Performance:** in-process best-of-5 — project overview 18 ms / 13 queries, editor page
9 ms / 7 queries, `/api/v1/projects/` 5 ms / 5 queries — all well under the 50 ms bar.
(Through runserver on this loaded container the same pages read 60–76 ms; the delta is WSGI
+ container noise, not query work — verified by the in-process numbers.)

**Gates:** 549 tests green, ruff check/format clean, tsc clean, editor smoke 6/6, SPA route
check green.

**Verdict:** healthy, one real find fixed and proven inert. The stretch's CI work (smoke,
artifacts, 4xx/5xx probe) has already paid for itself twice — it caught the modulePreload
404 class and forced this audit's escaping fix to be verifiable end-to-end.
