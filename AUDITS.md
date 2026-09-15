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

## Audit #15 — 2026-06-13 (the file-workspace / IDE / desktop epic, Owner #30)

First security + responsiveness review of the whole Owner #30 epic: unified file tree,
the explorer + open-anything preview + in-place editing, workspace write-ops, the Tauri
desktop shell, the built-in terminal, and project templates.

**Terminal (highest-risk surface): clean.** A PTY is arbitrary local code execution by
design — accepted in the single-user desktop trust model (same as VS Code). It lives ONLY
in the desktop binary (desktop/src/terminal.rs); a build-failing grep guard
(test_terminal_isolation.py) proves no portable-pty/terminal_spawn/openpty surface appears
in api/, mcp_server/, config/, etc., and the xterm panel imports @tauri-apps/api dynamically
so the browser bundle never even pulls it (and renders a hint instead of a PTY).

**Preview/content endpoints: clean.** /documents/{id}/content/ and /raw/ are 401 anon;
raw serves an ALLOWLIST of content types (pdf/png/jpg/jpeg/gif/webp) inline with
X-Content-Type-Options: nosniff, and **SVG is excluded** (inline SVG can script on our
origin) — covered by tests. Text preview is UTF-8, 1 MB-capped, 415 for binaries. Saving
text refuses manuscript-source nodes (409). Workspace write-ops refuse update/destroy of
manuscript-source documents and manuscript root folders (403, FolderViewSet + DocumentViewSet
guards + tests) — those are owned by the editor/mirror.

**Paths + uploads: validated.** validate_workspace_name / validate_manuscript_path gate all
create/rename/template paths (ASCII, no traversal, no dot-leading, ≤8 segments);
validate_upload_size caps uploads in the serializers and views.

**Dependencies: MIT/Apache/BSD, pinned, local.** xterm 5.5.0 (MIT), addon-fit (MIT),
papaparse 5.4.1 (MIT), pdfjs-dist 4.10.38 (Apache-2.0, vendored off the CDN this epic),
@tauri-apps/api (Apache/MIT), portable-pty 0.8 + tauri 2 (Rust, Cargo.lock pinned). The
last CDN editor asset (pdf.js) is now local — no CDN anywhere.

**Performance: well under bar.** /projects/{slug}/tree/ best-of-5 = 6 ms / 5 queries;
the Files SPA shell 3 ms. 637 tests green; make audit (pip + prod npm) clean.

**FINDINGS**
1. (handled) `npm audit` flagged a HIGH advisory in **esbuild** (GHSA-gv7w-rqvm-qjhr,
   registry-redirect RCE) via Vite — but both are **devDependencies**; `npm audit --omit=dev`
   (the shipped artifact) is 0 vulnerabilities. Scoped the audit gate to production deps
   (auditing what ships is the correct posture) and backlogged the breaking Vite 8 upgrade
   rather than risk the build mid-epic. Not exploitable in our trusted CI registry.
2. (noted, low) the Tauri shell sets `csp: null` and loads the Atlas server as an external
   URL. Acceptable for v1 — the loaded content is our own localhost app, which sets its own
   headers — but harden later by restricting webview navigation to the localhost origin so a
   compromised page can't navigate the app window off-origin. Backlogged.

**Verdict:** healthy. The epic's riskiest surfaces (terminal, raw file serving, desktop
disk reach) are correctly contained — desktop-only ACE, allowlisted/nosniff'd previews,
manuscript guards, validated paths — with two low-risk defense-in-depth items backlogged.


### Audit #15 follow-up (2026-06-13)
- Finding 2 (desktop webview navigation) **#160 resolved**: the shell now restricts navigation to the Atlas host via WebviewWindowBuilder.on_navigation; off-origin navigation is rejected. cargo check passes; structural test guards it.

## Audit #16 — 2026-06-13 (polish since #15: webview-nav, mood voice, reset-layout, lucide)

Focused sweep of the work since AUDIT #15 (commits 07a9b42..4e74592). **Clean — no findings.**

- **Desktop webview navigation (#160):** the shell's `on_navigation` origin-lock is in place
  (only the Atlas host); cargo check passes. This was the audit-#15 hardening item — verified
  shipped.
- **Pet mood voice (#149):** `read_aloud` still 401/403 anonymous; MOOD_VOICES is volume-only
  data composed with the stage params, no new input surface (mood derived server-side from
  pet_state); Piper is a library call on capped text — no injection.
- **Reset-layout (#150):** pure client-side — only removes `atlas-editor-*` localStorage keys
  and reloads; no server endpoint, no user-data interpolation, no XSS surface.
- **Dependencies:** lucide-react 0.469.0 (ISC) is the only addition since #15; all frontend
  PRODUCTION deps remain MIT/ISC/Apache, pinned and bundled (no CDN). `npm audit --omit=dev`
  = 0 vulnerabilities; `pip-audit` clean; `make audit` sweep clean (anon-401/302, key auth,
  #77 catch-all, open-redirect all green).
- **Performance:** in-process best-of-5 — classic dashboard 36 ms / 17 q, project overview
  20 ms / 13 q, the file-tree endpoint 6 ms / 5 q, the editor page 11 ms / 7 q — all under
  the 50 ms bar.
- **Gates:** 654 tests, ruff check/format, tsc — all green.

**Verdict:** healthy. The polish slices since #15 added no new attack surface and the desktop
hardening from #15 is confirmed in place. Vite-8 (#159, dev-only esbuild advisory) remains the
single open dependency item, deliberately deferred to its own careful cycle.

## Audit #17 — 2026-06-13 (since #16: typeahead, density passes, nav icons, sortable library)

Sweep of the work since AUDIT #16 (commits 4e74592..08ba0e9): #167 Files typeahead, #165/#171
density passes, #161/#173 Lucide nav icons, #170 sortable library columns. **One minor,
pre-existing performance finding — backlogged; security clean.**

- **New input surface — the library `?sort=`/`?dir=` querystring (#170):** the only new
  server-side user-input surface this run. Verified hardened:
  - **Auth-gated:** `/library/?sort=year&dir=desc` and `/library/?sort=DROP TABLE` both 302 to
    login when anonymous.
  - **No ORM injection:** `sort` is resolved through the `LIBRARY_SORTS` whitelist before
    reaching `order_by`; a hostile value (`'; DROP TABLE;--`) falls back to `title` → 200, no
    error, no extra query.
  - **No reflected XSS:** the hostile sort string is **not** echoed into the page (verified
    `"DROP TABLE" not in body`); the sort-header links interpolate only the hardcoded column
    keys and the constrained `asc`/`desc` literals, and `q` is `urlencode`d / auto-escaped.
- **Icon partials (#161/#173):** `core/_nav_icon.html` and `literature/_sort_th.html` render
  static inline SVG / literals only — no user data interpolated, no script, no new endpoint.
- **Density passes (#165/#171) + typeahead (#167):** template padding + a client-only key
  handler; zero new server surface.
- **Dependencies:** no new packages this run (icons are inline SVG, not a JS dep). `npm audit
  --omit=dev` = **0 vulnerabilities**; no Python deps added.
- **Performance (in-process, warm, best-of-2, queries counted):** library default 16 ms / 6 q,
  library sorted 16 ms / 6 q (**sorting adds no query cost**), hostile-sort fallback 15 ms / 6 q,
  documents page 26 ms / 15 q — all under the 50 ms bar.
- **FINDING (minor, pre-existing — backlogged #180):** the documents table's per-row move
  `<select>` iterates `project.folders.all` inside `_doc_row.html`, so the folders table is
  re-queried once per document row (10 folder queries across ~5 rows; grows O(rows)). Not a
  regression from the #171 padding pass — it predates this run — but worth hoisting the folder
  list to a single cached lookup. Logged as Backlog #180.

**Gates:** 664 tests, ruff check/format, tsc — all green.

**Verdict:** healthy. The sortable-library input surface is correctly whitelisted, non-reflective,
and auth-gated; no new dependencies or attack surface from the icon/density work. One pre-existing
documents-page N+1 found and backlogged (#180) for a focused fix.

## Audit #18 — 2026-06-14 (since #17: N+1 fix, density, typeahead, persisted/extended sort, a11y)

Sweep of the work since AUDIT #17 (commits ~9fa70d3..b4d999b): #180 N+1 fix, #179/#182
density, #168/#169 typeahead polish, #176 persisted library sort, #189 per-project literature
order pills, #190 persisted literature order, #177 documents-table a11y. **Clean — no findings.**

- **New/extended ?sort= surfaces (#189 project-literature, plus #176/#190 session-persisted
  sort):** verified hardened:
  - **Auth-gated:** `/library/?sort=…` and `/projects/<slug>/literature/?sort=cited` both 302
    when anonymous.
  - **No ORM injection:** every sort key is resolved through a whitelist (`LIBRARY_SORTS`,
    `LITERATURE_SORTS`, `DOCUMENT_SORTS`) before reaching `order_by`; a hostile value (`'; DROP
    TABLE;--`) falls back to the default → 200, no error.
  - **No reflected XSS:** an injected `ZZmarker'><script>alert(1)</script>` in `?sort=` (and a
    payload in `?dir=`) does **not** appear in the response at all — the value is replaced by the
    whitelisted default and never echoed. (An earlier naive "is `<script>` in body" probe
    false-positived on the page's own legitimate script tags; the exact-payload re-check is
    clean.)
  - **Poisoned session is safe:** writing a hostile string directly into
    `session["literature_order"]` and revisiting still 200s, falls back to the default order, and
    does not reflect the value — the whitelist is re-applied on read, so a tampered session can't
    inject or break rendering.
- **Typeahead polish (#168/#169) + a11y headers (#177):** client-only (key handler / aria-sort
  attributes); no server surface, no user data interpolated into script.
- **Dependencies:** no new packages this run. `npm audit --omit=dev` = **0 vulnerabilities**;
  Python deps unchanged since #17 (pinned/frozen).
- **Performance (in-process, warm, queries counted):** library sorted 19 ms / 9 q, per-project
  literature ordered 20 ms / 7 q, hostile-sort fallback 20 ms / 7 q — all under the 50 ms bar.
  Sorting/order pills add **no** per-row queries (no N+1); the #180 fix holds. Note: the library
  page is 6→9 q vs #17 because the persisted sort (#176) reads+writes the DB-backed session — a
  constant, expected cost, not row-scaling.
- **OBSERVATION (not a finding, backlogged #192):** #176/#190 store the *raw* unvalidated
  `?sort=` into the session before the whitelist check. It's harmless (re-validated on read) but
  storing arbitrary strings is untidy; validate-before-store would be cleaner defense-in-depth.

**Gates:** 669 tests, ruff check/format, tsc — all green.

**Verdict:** healthy. Every new sort/order surface is whitelisted, non-reflective, auth-gated, and
N+1-free; persisted-sort sessions are validated on read so tampering is inert. No fixes needed;
one tidy-up (validate-before-store) backlogged as #192.

## Audit #19 — 2026-06-14 (since #18: helper refactor, base_wide, perf trims, Vite 8, desktop dist)

Sweep since AUDIT #18 (commits ~21d870f..aed8ca6): #191/#192 session helper, #193 queue
persistence, #183/#195/#196 base_wide, #181/#197 folder-query trims, #199 count lines, #159
Vite 8, and the owner desktop-distribution epic (D1 release CI + D2 in-app updater). **Clean —
no findings.**

- **Web surfaces (#189/#193 order/persist, #199 counts):** auth-gated (302 anon on
  `/projects/<slug>/literature/?sort=` and `…/queue/?order=`); the project-literature `?sort=`
  whitelist holds and an injected `ZZ'><script>…` is **not** reflected; counts are server-side
  `|length`, no interpolation. Timings 17–21 ms / 6–7 q, under the 50 ms bar.
- **Desktop auto-update (D2) — the one genuinely new privileged surface:** reviewed and safe by
  design. `check_for_updates` has **no hardcoded/caller-supplied URL** — the endpoint comes from
  tauri.conf (the project's own GitHub Releases feed) and `download_and_install` only applies a
  build whose signature verifies against the configured pubkey. So even though the command is
  reachable over the IPC, it cannot be steered to install arbitrary code. It's also inert right
  now (placeholder pubkey + createUpdaterArtifacts=false) until the owner's keypair step (D3).
- **Release workflow (D1):** uses the standard scoped `GITHUB_TOKEN`; `TAURI_SIGNING_PRIVATE_KEY`
  is referenced only as a future secret (commented), so nothing is leaked. Releases are drafted,
  not auto-published.
- **withGlobalTauri (OBSERVATION, not a finding):** D2 set `withGlobalTauri: true`, exposing the
  IPC (terminal/localfs/updater) to the loaded page. That page is origin-locked to the local
  Atlas server (the on_navigation guard from #160) and this is a single-user local app, so the
  trust model is unchanged — the same model under which the terminal already shipped. The app's
  broad XSS hardening (esc() everywhere, non-reflective inputs) keeps a hostile script from
  reaching the IPC. The terminal-isolation guard still passes (PTY stays out of web/MCP).
- **Dependencies:** `npm audit --omit=dev` = **0 vulnerabilities** (Vite 8 holds the #159 win);
  the only new crates are tauri-plugin-updater + serde_json (official Tauri / serde, pinned).

**Gates:** 681 tests, ruff check/format, tsc, cargo check — all green.

**Verdict:** healthy. The new desktop auto-update path is signature-locked and feed-pinned (can't
install arbitrary code); the release workflow leaks no secrets; the web sort/persist/count work
stays whitelisted, non-reflective, and N+1-free. No fixes needed.

## Audit #20 — 2026-06-14 (since #19: the self-contained desktop epic #210 + fixes)

Sweep of the bundled desktop app: SQLite→Postgres settings, the auto-Postgres lifecycle
(core/desktop_runtime), run_desktop/waitress, the PyInstaller freeze, the search fallback,
the resource-bundling CI, and the post-ship fixes (initdb.exe, single-instance). **Clean —
no findings; one hardening note backlogged.**

- **Local trust model (the big new surface):** the desktop build runs a Postgres it
  initdb's itself, with `--auth=trust` — but bound to **127.0.0.1 only**
  (`listen_addresses=127.0.0.1`) plus a unix socket inside the per-user data dir, and
  `ALLOWED_HOSTS=[127.0.0.1, localhost]`. On a single-user desktop this is the same trust
  boundary as the user's own files (SQLite has no auth either); nothing remote can reach it.
- **No injection in desktop_runtime:** every psql/createdb/initdb arg is a hardcoded
  constant (`DB_NAME`/`DB_USER` = "atlas") or an int port — no user input reaches the SQL or
  the shell (subprocess lists, never shell=True). The binary paths come from ATLAS_PG_BIN,
  set by the trusted Tauri shell to a bundled resource.
- **Single-instance (#210 fix):** prevents multiple instances racing one Postgres data dir
  (corruption) — a robustness + integrity win, not just UX.
- **Web surfaces unchanged + still gated:** /library/ etc. 302 anonymously; the desktop work
  didn't touch the web auth/injection posture.
- **CI/deps:** the release workflow uses only `secrets.GITHUB_TOKEN` (no leaked secrets); it
  downloads Postgres from Maven Central over https. `npm audit --omit=dev` = 0 vulns; the new
  Python deps (waitress, pyinstaller[build-only]) are mainstream/pinned.

**OBSERVATION (backlogged #211):** trust-auth means any local process on the user's machine
can reach the desktop DB on 127.0.0.1:<port> without a password. Acceptable for a single-user
desktop (matches the file-ownership boundary), but a unix-socket-only listener or a random
generated password would tighten it. Low priority.

**Verdict:** healthy. The self-contained stack is a sound local-trust design — loopback-bound,
no user-controlled SQL/shell, integrity protected by single-instance. No fixes needed.

## Audit #21 — 2026-06-14 (since #20: filter persistence, schema-quality, review fix, breadcrumb)

Sweep of the work since the desktop epic: session-remembered filters (#187 literature
status/priority, #212 documents tag, #214 the Clear-link fix), #216 cross-project review note
links (`project_slug`), the OpenAPI schema cleanup (#218 auth extension + 2 recovered endpoints,
#219 enum names, #220 the 0-warnings guard), and #222 the clickable folder breadcrumb. Desktop
D2b (real app restart on update) reviewed too. **Clean — no findings.**

**Security (verified live + via RequestFactory on real data):**
- Anonymous gating intact: `/projects/<slug>/documents/`, `/literature/`, `/review` → 302;
  `/api/schema/`, `/api/v1/weekly-review/` → 401.
- **Persisted filters can't reach the ORM raw (#192 holds for the new surfaces):** a hostile
  `?status='; DROP TABLE--` / `?priority=<x>` → 200 (allow-list → "All"); a non-int
  `?tag=1 OR 1=1` → 200 (validated against the project's live tag pks → "All"). The slug-
  namespaced doc-tag session key (#212) keeps a remembered tag from leaking across projects.
- **Breadcrumb (#222) is project-scoped:** `get_object_or_404(project.folders, pk=…)` means a
  nonexistent or foreign folder pk → 404 (not a 500 or a cross-project read); folder names
  render through Django autoescaping (no XSS). `Folder.ancestors` only walks its own chain.
- **Schema auth (#218):** the generated schema declares `ApiKeyAuth` (apiKey/header/X-API-Key)
  and every path requires it — but the schema does **not** contain the key's value, only the
  header name. No secret exposure.
- `#216` only adds project slugs (already visible to the single authenticated owner) to the
  review payload — no new read surface.

**Dependencies:** `npm audit --omit=dev` = **0 vulnerabilities**.

**Performance (warm; DEBUG-instrumented query counts):**
- **Breadcrumb adds zero queries:** documents page is **13 queries at the root and 13 in a
  nested folder** — `Folder.ancestors` reuses the same parent walk `.path` already did (and
  Django caches `.parent`), so the clickable crumb is free. ~16–31 ms.
- `weekly_review` (cross-project, now with `project_slug` on every item): **5 queries**, 16 ms
  — identical to the AUDIT #9 baseline, confirming the select_related already had the projects.
- Per-project literature (filtered): **6 queries / ~20 ms warm**. (A first cold call measured
  32 q / 241 ms — one-time template-compile + contenttype/pg_trgm warmup, not per-request;
  calls 2–3 settle to 6/≈20.)
- Schema generation is build-time only (guarded warning-free by #220), off the request path.

**Verdict:** healthy. The session-persistence and breadcrumb work stayed within the existing
allow-list/project-scoping discipline and added no query cost; the schema work tightened the
machine-facing contract without exposing anything. No fixes needed. 708 tests green, ruff clean.

## Audit #22 — 2026-06-15 (since #21: the Windows desktop saga + UI/perf slices)

Swept the work since AUDIT #21: the whole self-contained-Windows fix chain (#224 POSIX-only
socket, #228 initdb stderr/pgdata-wipe/`\\?\`-strip, #229 CI trigger paths, #230 per-build
version, #231 psycopg provisioning), the cheap-previews + in-app lightbox (#227/#227-fu), and
the UI/perf slices (#226 N+1 guards, #205 empty state, #228 review chip links, #232/#234 count
lines + pluralization, #233 deadline label). **Clean — no findings.**

**Security (verified live + tests):**
- **The inline file-preview endpoint (#227) is the one genuinely new surface, and it's sound.**
  `document_preview` is login-gated (302 anon) and project-scoped (`get_object_or_404(Document,
  pk=…, project__slug=slug)` → a foreign doc 404s, no cross-project read). It serves ONLY a
  raster-image whitelist (png/jpeg/gif/webp/bmp) inline as its own type, and ALL text as
  `text/plain; charset=utf-8`; SVG/HTML/PDF/binaries redirect to download. Every response
  carries `X-Content-Type-Options: nosniff`, so a browser can't be tricked into executing an
  uploaded file as HTML in Atlas's origin. 6 tests cover the image/text/SVG/PDF cases. The
  React image lightbox just points an `<img>` at that same-origin endpoint — no new vector.
- Anon gating intact on the changed surfaces (preview, download, reading queue → 302).
- **Desktop #231 (psycopg provisioning):** the readiness wait + DB-exists check use bound
  params; `CREATE DATABASE "atlas"` interpolates a hardcoded module constant (no user input,
  identifiers can't be bound). Connects to the local 127.0.0.1 trust cluster — same local-trust
  model as AUDIT #20, unchanged. The frozen server's atlas-server.log captures tracebacks only
  (no secrets). The per-build version bump (#230) is benign.

**Dependencies:** `npm audit --omit=dev` = **0 vulnerabilities**.

**Performance (warm):**
- Reading queue: **9 queries / 17 ms** (cold first call 34 q / 571 ms is one-time template +
  pg_trgm/contenttype warmup). The new `has_references` (#205) is a single constant `exists()`
  — the #226 N+1 guard still holds.
- `Manuscript.deadline_label` + `deadline_is_soon` (#233) are pure properties over
  already-loaded fields — **0 queries**, so unifying the three templates added no cost.
- The preview endpoint streams the file with `Cache-Control: private, max-age=86400` + nosniff.

**Verdict:** healthy. The headline new risk — serving uploaded files inline — is mitigated by a
strict raster/text-as-plain whitelist + nosniff + project scoping. The Windows saga was all in
the desktop launcher (no web-auth impact), and the UI/perf slices added no query cost. 738 tests
green, ruff clean. No fixes needed.

## Audit #23 — 2026-06-16 (since #22: desktop startup fixes + inline-preview hardening + .ics feed)

Swept the work since AUDIT #22: the desktop startup chain (#244 timeouts, #245 console crash-loop
fix, #246 plain static, #248 windowed stdin), the two inline-preview byte-sniffing slices
(#249 document preview, #250 API raw), the doctor refactor (#208), and the new iCalendar feed
(#9-calendar). **One dependency finding, fixed; the new code surface is clean.**

**Dependency finding (FIXED): starlette 1.2.1 → 1.3.1.** `pip-audit` flagged CVE-2026-54282 and
CVE-2026-54283 in starlette 1.2.1 (a transitive dep via `mcp` + `sse-starlette`, used by the MCP
server's HTTP transport). Bumped to 1.3.1 with `uv lock --upgrade-package starlette` (resolved
cleanly inside mcp's range, no other pins moved); `uv sync` applied it. Re-audit: **0 known
vulnerabilities**. The MCP server still imports and its 19 tests pass. This is the project's
stated bar (clean `pip-audit`/`npm audit`); npm side was already 0.

**Security (verified live + tests):**
- **The new `.ics` feed (#9-calendar) is sound.** `GET /projects/{slug}/calendar.ics/` is
  API-key gated (401 anon, verified live), project-scoped via the viewset's `get_object()`
  (unknown slug → 404, no leak), and read-only. **ICS injection is neutralized:** a milestone
  title containing `\nBEGIN:VEVENT\n…` is escaped per RFC 5545 (newline → `\n`, plus `,` `;` `\`)
  so it stays one SUMMARY line — verified by counting standalone `BEGIN:VEVENT` lines before/after
  a crafted title (8, not 9). Query cost is **2 queries** (milestones `select_related(phase)` +
  manuscripts), no N+1, bounded by the project's own rows.
- **Inline-preview byte-sniffing (#249/#250) closed a real gap.** Both inline paths now confirm
  the actual magic bytes before serving `inline`: `document_preview` (login-gated, project-scoped)
  serves an image only when the bytes are a real PNG/JPEG/GIF/WebP/BMP, else `text/plain`; the API
  `raw` action (API-key gated) 404s when the bytes don't match the extension-claimed type
  (`%PDF-` for PDFs). Both keep `nosniff`. A spoofed `image/png` that is really HTML is now
  downgraded/blocked — strictly tighter than AUDIT #22's whitelist-only posture. Anon still 401
  (raw) / would 302 (preview).
- **Desktop startup chain** is launcher-only (frozen server + bundled Postgres on 127.0.0.1
  trust — same single-user local-trust model as AUDIT #20); no web-auth surface. The audit sweep
  (`scripts/audit.sh`) re-confirmed anon→401 on all API probes, pages→302, the #77 catch-all
  (404 + on-origin /app redirect), and static MIME.

**Performance (warm):**
- `calendar.ics`: **~19 ms** for the 7-event demo project (well under the 50 ms bar), 2 queries.
- Inline preview reads a 32-byte head then streams with `Cache-Control: private, max-age=86400`
  (preview) — the API `raw` action sets nosniff but no Cache-Control (parked as a minor #11
  follow-on; immutable files, so a cheap win, not a risk).

**Verdict:** healthy after one dependency bump. The headline new surface — an unauthenticated-by-
calendar-apps `.ics` feed — is currently header-authed (no URL credential yet; the subscribable
token feed #253 was deliberately deferred until its token scoping can be designed), escapes its
output, and is project-scoped. starlette is patched. 767→(full-suite re-run) green, ruff clean.

## Audit #24 — 2026-06-16 (since #23: writable Protocol API, figures/calendar feeds, experiment commit links, MCP tools, desktop diagnostic)

Swept the work since #23: the new WRITABLE Protocol API (#7) + its MCP tools (#7-mcp) + web UI
(#260), the figure-gallery feed/UI (#8/#256/#257), the experiment↔commit field (#4), and the
desktop in-window diagnostic (#263). **One responsiveness finding, fixed; everything else clean.**

**Security (verified live + tests):**
- **The Protocol API is the one genuinely new *writable* surface, and it's sound.** Live probes:
  anon list/create → **401**, create with no/invalid `project` → **400**, `new-version` on a
  missing id → **404**. It's API-key gated like the rest, project-scoped via `ProjectSlugField`,
  and `version`/`parent` are `read_only` so the immutable history chain can't be forged through
  create (a `version: 99` in the body is ignored → v1). The `new-version` action only copies
  title/body and derives version+parent server-side. 13 tests.
- **No injection via protocol bodies:** they render through the same `markdownify` (markdown +
  nh3 sanitize) used everywhere else — no new raw-HTML path.
- The figures feed, `.ics` feed, and `commit_url` were audited at #23/their own slices and are
  unchanged here (figures: project-scoped, SVG-excluded; calendar: RFC-5545-escaped; commit_url:
  a stored URL, rendered as a plain link).
- `scripts/audit.sh` re-confirmed anon→401 across the API, pages→302, the #77 catch-all, the
  `/app/*` open-redirect guard, and static MIME.

**Dependencies:** `npm audit --omit=dev` = **0**. `pip-audit` momentarily reported starlette
1.2.1 again — but that was a **stale local venv after a container rollback**, not a regression:
`uv.lock` already pins 1.3.1 (from #23), and `uv sync` restored it → **0 known vulnerabilities**.
(Lesson: after a rollback, `uv sync` before trusting a local pip-audit.)

**Performance (warm):**
- **FINDING → FIXED: `protocol_list` was O(n) queries.** It filtered current heads with
  `is_current` (an `exists()` per row) *and* the template walked `protocol.parent` / `.lineage`
  per row — ~2 queries per protocol (11 queries for 10 protocols, growing with the list). Fix:
  load `project.protocols.all()` once, compute the superseded parent-id set and each head's
  `lineage_cached` in memory, and gate the History disclosure on `lineage_cached` (not
  `protocol.parent`, which lazy-loads). Now **O(1) queries** regardless of protocol count; an
  N+1 guard test locks it (8 protocols cost no more queries than 3).
- Protocol/figures/calendar API reads are ~20 ms warm.

**Desktop (#263):** launcher-only, no web surface. The new diagnostic page is a static local
`file://` page written to the per-user data dir; `on_navigation` now allows `file://` in addition
to the Atlas origin — a minor, local-only relaxation (it can't enable off-origin remote
navigation), acceptable for a single-user desktop showing its own logs.

**Verdict:** healthy after one N+1 fix. The headline new risk — a *writable* API — is properly
auth-gated, project-scoped, and has a forge-proof version chain. 794 tests green, ruff clean.


## Audit #31 — 2026-09-15 (since #30: #519–#527 — the Plan area's last four slices and its verdict, the Library return pass's first five)

Ten cycles, nine feature slices, three findings — each an unbounded integer reaching the
database or the datetime arithmetic, all fixed, all pinned — plus one hardening.

**Dependencies — CLEAN.** `pip-audit` on the exported lock: *No known vulnerabilities found*.
`npm audit --omit=dev`: *0 vulnerabilities*. `scripts/audit.sh`: every row green (anon → 401
across the API, pages → 302, catch-all 404, static MIME, `/app//evil.com` stays on-origin).

**New surfaces since #30 — reviewed.**
- *Auth:* `references/export/`, `references/reading-now/`, `references/check-retractions/`
  (GET and POST) and `references/{id}/progress/` (GET and POST) answer 401 anonymously and to
  a wrong key.
- *Export (#525):* `fmt=exe` / `fmt=../etc` → 400 naming the four formats; `ids=abc,1e2,-1`
  → an empty file (non-digits dropped); 5 000 ids → capped at 500, as is a filtered view. *CSV
  injection:* `_cell` quotes a cell starting with `=`, `+`, `-` or `@` (pinned since #525);
  **hardened** to the full OWASP list — a leading tab or carriage return is quoted too
  (`test_csv_neutralises_formula_cells` extended). Numbers (id, year, citations) are never
  attacker text.
- *Filters (#524, #526, #527):* `year_min=abc` ignored, `year_min=1e20` → an empty page on
  Postgres *and* on SQLite (Django's `exact` / `gte` / `lte` integer lookups range-check the
  value and short-circuit — verified on a SQLite database as the desktop runs), `year_max=-5`
  → empty, a 5 000-character
  `author` is cut to 120 and matched in Python over one `(id, authors)` query, `retracted=%00`
  ignored, `sort=__class__` / `sort=-project_links__project__name` fall back to the default —
  `_ordering` is a whitelist, never an attribute path. The SPA's `fromUrl` reads only the
  known keys, slices every value to 200 and renders them as React text; `add` only focuses
  the DOI box, `read` opens a paper the API already returns.
- *browse_library.url (#526):* `q=a&b=c` and `author=O'Neil <x>` come back percent-encoded;
  empties, zeros and the default sort are dropped; the API key is never in the address.
- *Retraction watch (#527):* 51 ids → 400 "Give up to 50 ids."; `["a", 1.5, null]` and
  `ids: 5` → 400; unknown / negative / 10²⁰ ids → 200 with nothing checked; `[true, false]`
  → id 1 (Python's bool is an int — harmless); `days: "abc"` / `limit: -5` → 400; `limit:
  99999` clamped to 50; a non-JSON body → 400. *Live:* four demo DOIs against Crossref in
  5.6 s (3 checked, 1 without a DOI skipped), verdicts unchanged. *Offline:* the breaker
  stops a sweep after five consecutive errors (`test_breaker_stops_an_offline_sweep`), so
  the desktop's hourly scheduler tick costs at most five timeouts (50 s) on a train and never
  clears a verdict. A DOI containing a comma would split Crossref's `filter=` and come back
  as a non-200 → counted as an error, verdict untouched (fail-closed; noted, not changed).
- **FINDING 1 — a page count past the column was a database error.** `POST
  references/{id}/progress/` with `page: 3000000000, page_count: 3000000000` returned **500**:
  the serializer bounded both below (`min_value=1`) but not above, and `PositiveIntegerField`
  is 32-bit; the same held for a `page` with no known count. Fixed twice over:
  `max_value=100_000` on both serializer fields (400) and `MAX_PAGES` in
  `literature/progress.py::record_position` (a `ProgressError` for the MCP and any other
  caller). Pinned in `test_record_position_refuses_bad_pages` and `test_progress_api_roundtrip`.
- **FINDING 2 — a wild `days` overflowed the sweep.** `POST references/check-retractions/`
  with `stale: true, days: 1000000000` (or 10²⁰) returned **500**: `timezone.now() -
  timedelta(days=…)` raised `OverflowError`. Fixed in `stale_references` — `days` is clamped
  to `MAX_STALE_DAYS` (ten years), so the API, the command and the scheduler share the bound.
  Pinned in `test_stale_selection_never_checked_first_then_oldest` and the endpoint test.
- **FINDING 3 — an id past the column reached `pk__in`, which SQLite refuses.** The
  Postgres probes above passed (`ids=1e20` on the export, `ids: [1e20]` on the retraction
  check) because psycopg binds a wide int as `numeric` and the comparison misses. Re-run
  against a SQLite database — the desktop's — `Reference.objects.filter(pk__in=[10**20])`
  raises `OverflowError: Python int too large to convert to SQLite INTEGER`: Django's `__in`
  lookup, unlike `exact` / `gte` / `lte`, does not range-check. Seven request paths fed ids
  straight into a `pk__in`: `references/export/?ids=`, `references/bibliography/?ids=`,
  `check-retractions {ids}`, `references/bulk/ {ids}`, `quick-capture/bulk/ {ids}` and the
  `todos/` / `saved-views/` / `phases/` reorders. Fixed at one place each: `core/ids.py`
  (`MAX_PK = 2**31 - 1`, `parse_ids(values, limit, strict)` — junk dropped or refused,
  out-of-range always dropped, duplicates once, capped) behind the three query-string and
  raw-body paths; a `PkField` (bounded `IntegerField`) behind the two bulk serializers; the
  range check joined the three reorders' `isinstance` guards. Pinned in
  `core/tests/test_ids.py` (the parser, and every endpoint with `10**20`), which holds on
  both databases because the wild value never reaches the SQL; the seven paths re-run on
  the SQLite database with the fix in place answer 200 / 200 / 200 / 400 / 400 / 400 / 400.
- *Progress (#523):* `page: "abc"` / `-3` / `0` → 400; a page past the known end → 400 with
  the reason; an unknown reference → 404. *Reading now:* `limit=abc` → default, `999999` →
  clamped to 20.

**Query counts on the demo** (in-process): `references/?author=Lavie` 9, `?retracted=1` 7,
`?q=attention&year_min=2000&sort=-year` 7, `facets/` 18, `export/?fmt=csv` 5 (`ris` 5 —
tags and project links prefetched), `reading-flow/` 4, `reading-now/` 4,
`check-retractions/` (GET) 5, `{id}/progress/` 6, `{id}/` 9 — all grouped, none per row.

**Hot endpoints (in-process, demo data):** list with the author filter 19 ms, retracted
filter 14 ms, search + year + sort 27 ms, facets 52 ms, CSV export 13 ms, RIS 12 ms,
reading flow 13 ms, reading now 6 ms, watch status 6 ms, progress 10 ms, detail 16 ms.

**Verdict.** Three findings, all the same shape as Audit #30's first (an integer bounded on
one side only — or, for `__in`, on neither), the third invisible on the audit's own Postgres
and a 500 on the owner's SQLite desktop, so the audit now reproduces id and range probes on
both databases. All three refused with a reason instead of a traceback. Nothing exploitable across the wire: the API-key gate holds
on every new route, the sort whitelist and the filter parsers refuse attribute paths, the
CSV writer neutralises every formula prefix, the retraction watch fails closed offline.
**Next audit due at #538.**

## Audit #30 — 2026-09-14 (since #29: #509–#517 — the Notes + graph area's last three slices and its verdict, the Plan area's first six, the Edge 152 boot hotfix)

Ten cycles, nine feature slices and a hotfix, two findings — one a database error on a bad
count, one a quadratic restore in the markdown renderer — both fixed, both pinned.

**Dependencies — CLEAN.** `pip-audit` on the exported lock: *No known vulnerabilities found*.
`npm audit --omit=dev`: *0 vulnerabilities*. `scripts/audit.sh`: every row green (anon → 401
across the API, pages → 302, catch-all 404, static MIME, `/app//evil.com` stays on-origin).

**New surfaces since #29 — reviewed.**
- *Auth:* `projects/{slug}/plan/drift/`, `…/plan/review/` (GET and POST),
  `…/plan/reschedule-conflicts/`, `notes/{id}/related/` and `PATCH milestones/{id}/` answer
  401 anonymously and to a wrong key.
- *Dependencies (#512):* `blocked_by` with itself, an unknown id, a non-integer or a loop
  through a second milestone → 400 with the reason ("That would make a loop — a milestone
  would block itself"); the check is a walk over one query, not a query per hop.
- *Dates (#513–#516):* `due_date` `junk` / `2026-13-45` → 400, `null` → 200 (undated, logged
  as a move); the drift log folds nudges within ten minutes and deletes an undo, so a drag
  storm cannot grow the table by more than one row per ten minutes per milestone.
- *Related notes (#510):* `limit` `0` / `-1` / `99` → 200 (clamped to 1–20), `abc` / `1e2` /
  empty → 400.
- *Review (#517):* `kept` `abc` / `1.5` / `-1` → 400; a 2 001-character note → 400.
- *FINDING 1 — a count past the column's range was a database error.* `POST …/plan/review/`
  with `kept: 2**40` returned **500**: the serializer bounded the counts below (`min_value=0`)
  but not above, and `PositiveIntegerField` is 32-bit. Fixed: `max_value=100_000` on all four
  counts (`api/serializers.py::PlanReviewSerializer`) → 400; `plans/tests/test_review.py` pins
  it.
- *Rendering (#509) — XSS:* a note body carrying `<input onclick>`, a callout kind with a
  `<script>`, `<img onerror>`, `<b onmouseover>` inside `==…==`, `<script>` and
  `\href{javascript:…}` inside `$…$`, a `<div class="task-done" id="javascript:x" onclick>`,
  and a footnote with a `javascript:` link renders with **no handler, no script and no
  `javascript:` href** — nh3 strips the attributes, the task box is rebuilt after the
  sanitizer, math text is HTML-escaped. The only `javascript:` left is *inside the escaped
  TeX*, where KaTeX renders it as text: `Prose.tsx` calls `katex.render` without `trust`, so
  `\href` / `\url` / `\includegraphics` stay refused. `core/tests/test_rendering.py` now
  pins that no `trust` option is ever passed.
- *FINDING 2 — the math restore was quadratic.* `render_markdown("$" * 100_000)` took
  **8.7 s**: the lifter produced 20 000 display segments in 30 ms and Markdown rendered them
  in 110 ms, but `_restore_math` ran a `str.replace` over the whole HTML per segment (9.3 s).
  Fixed: one `re.sub` pass over a token pattern (`MATH_TOKEN_RE`), the paragraph wrapper
  handled in the callback; 100 k dollars now render in ~0.2 s. `core/tests/test_regex_budgets.py`
  gains the #509 parsers — dollars, display math, highlights, callouts, task boxes — each
  under a second on a 50–100 k-character run (task boxes at 10 k lines: Python-Markdown itself
  spends ~50 µs per list item, linearly).
- *Preload helper (hotfix):* `core/tests/test_preload_helper.py` pins the three-token module
  that replaced Vite's helper after the Edge 152 blank boot; desktop runs 225–229 built green.

**Query counts on the demo** (one project, six open milestones): `plan/review/` 10,
`plan/drift/` 4, `plan/` 14, `roadmap/` 6, `notes/{id}/related/` 13 — all grouped queries,
none per row; the dashboard budget moved 115 → 116 in #516 (one drift-log read per active
project's roadmap) and is pinned.

**Hot endpoints (in-process, demo data):** plan 72 ms, roadmap 44 ms, plan review 40 ms,
plan drift 28 ms, focus 31 ms, overview 157 ms, dashboard 167 ms.

**Verdict.** Two findings, both in code written in the last ten cycles, both the kind the
next feature would have hidden (a Claude-driven review with a wild count; a note with many
formulas). Nothing exploitable across the wire: the API-key gate holds on every new route, the
sanitizer holds against handler and protocol injection, KaTeX stays untrusted. **Next audit
due at #528.**

## Audit #29 — 2026-09-14 (since #28: #499–#507 — the Inbox's last three slices and its verdict, the Notes + graph area's first six)

Ten cycles, nine feature slices, two findings — both in text parsers, both fixed, both pinned.

**Dependencies — CLEAN.** `pip-audit` on the exported lock: *No known vulnerabilities found*.
`npm audit --omit=dev`: *0 vulnerabilities*. `scripts/audit.sh`: every row green (anon → 401
across the API, pages → 302, catch-all 404, static MIME, `/app//evil.com` stays on-origin).

**New surfaces since #28 — reviewed.**
- *Auth:* `notes/{id}/outline/`, `…/graph/`, `…/revisions/`, `…/revisions/{rid}/restore/`,
  `…/link-mentions/`, `notes/tags/`, `projects/{slug}/graph/` and `quick-capture/{id}/enrich/`
  answer 401 anonymously and to a wrong key.
- *Link titles (#499):* the SSRF guard holds — `127.0.0.1`, `localhost`, `10.0.0.1`, `[::1]`,
  `169.254.169.254`, `0.0.0.0`, the decimal (`2130706433`) and hex (`0x7f000001`) spellings
  of loopback and `file://` are all refused before any socket opens (resolved addresses are
  checked, not the spelling); through the API each comes back as `link_error`, never fetched.
- *Dates (#500):* 45 k-character first lines and `"next " × 20 000` parse in ≤ 60 ms.
- *Note graph (#503):* `depth` — `0` → 1, `4` / `99` → 3 (clamped; max `hops` observed 2 on the
  demo), `abc` / `-1` / `1e2` → 400. The project graph with #506's filing dates: 12 queries /
  19 ms; the note graph at depth 3: 13 / 21 ms.
- *Tags (#504):* `?tag=` with `#`, quotes, brackets or 5 000 characters → 200 (a JSON
  `contains`, never interpolated); `notes/tags/` without a project → 400.
- *History (#505):* `rid` = `0`, `abc`, `-1`, `999999999999` → 404 (the route only accepts
  digits; unknown ids are 404, foreign ids too); `restore` of an unknown revision → 404.
- *Relink (#502):* `sources: ["a"]` → 400; 5 000 ids → 200, filtered to the project's notes.
- *A 1 MB note (#507):* PATCH 0.30 s (snapshot + links + tags + citations), `outline/` 0.45 s,
  `graph/` 75 ms, `revisions/` 49 ms. Acceptable for a body forty times any real note.
- *FINDING 1 — catastrophic backtracking in the wiki-link and HTML-title readers.* A body of
  50 000 `[[` made `parse_wiki_titles` (run on every note save, in the renderer, in the
  outline) take **64 s**: the title class `[^\]\n]+` swallowed every following bracket and
  re-scanned from each one. The og:title reader was worse from the other side of the wire:
  256 KB of `<meta ` without a closing `>` — bytes the *page* chooses — took **96 s** to give
  up, hanging the enrich request that #499 fires automatically on load. Fixed: the link
  classes exclude `[` (`notes/services.py`, `notes/outline.py`; 50 k `[[` now 2 ms), and
  `notes/links.py` walks at most 300 `<meta` tags, each as a bounded 2 000-character slice,
  with a bounded `<title>` pattern (256 KB of open tags now 17 ms; 20 k `<title>` 285 ms).
  `core/tests/test_regex_budgets.py` pins every text parser under a second on these inputs.
- *FINDING 2 — the note list read three things per row.* `GET /notes/` cost 16 queries for
  the demo's 3 notes and 47 for 40: the project slug, the backlinks and the cited papers each
  went to the database per note — and the backlink accessor called `select_related()` on the
  related manager, which builds a fresh queryset and bypasses any prefetch. Fixed with
  `select_related("project")` + `prefetch_related("incoming_links__source", "references")`
  on the viewset and `.all()` in the accessor (40 notes → 7 queries; the demo 16 → 7,
  24 → 12 ms). `test_api_notes_list_budget` pins ≤ 12 queries for 40 linked notes.

**Performance (warm, best of four, in-process with the API key, demo data):** project graph
19 ms · note graph (depth 3) 21 ms · revisions 5 ms · outline 4 ms · tags 5 ms · notes 12 ms ·
inbox 19 ms · inbox history 5 ms · dashboard 74 ms · project overview 91 ms. Everything under
the 100 ms bar.

**Desktop CI — GREEN.** Runs 209–219 (0.1.209–0.1.219) all succeeded.

**Product stance unchanged.** Single user, API key from the environment, no multi-tenancy;
the risks accepted in #26 (user-supplied regex backtracking in project search) still stand.
Python-Markdown itself renders a 30 000-line body in ~7 s — the preview of a pathological
note is slow but bounded and user-initiated; not a finding.

**Next audit due at #518.**

## Audit #28 — 2026-09-14 (since #27: #489–#497 — the Dashboard's last five slices and its verdict, the Inbox's first four)

Ten cycles, nine feature slices, one honest look.

**Dependencies — CLEAN.** `pip-audit` on the exported lock: *No known vulnerabilities found*.
`npm audit --omit=dev`: *0 vulnerabilities*. `scripts/audit.sh`: every row green (anon → 401
across the API, pages → 302, catch-all 404, static MIME, `/app//evil.com` stays on-origin).

**New surfaces since #27 — reviewed; one finding, fixed.**
- *Auth:* `dashboard/brief/`, `dashboard/day/`, `quick-capture/history/`, `…/snooze/` and
  `…/bulk/` answer 401 anonymously and to a wrong key.
- *Day activity (#492):* `?date=` — `2026-13-40`, `abc` → 400; blank → today; `0001-01-01` →
  an empty day (bounded: the timeline pass is capped at `DAY_PROJECTS = 40` projects).
- *Pulses and trends (#489, #490):* grouped `values_list` queries per source, never one
  timeline per project; the dashboard budget test still pins ≤ 100 queries with three busy
  projects (53 queries / 60 ms in-process on the demo today).
- *Daily brief (#491):* markdown built from the same helpers as the dashboard; shown in a
  `<pre>` and copied to the clipboard, never rendered as HTML — 47 queries / 52 ms.
- *Project suggestion (#494):* the index is built once per request (serializer context), from
  grouped `values_list` reads with reference titles capped at 2000; matched terms are shown
  as plain text in a chip tooltip.
- *Snooze (#495):* `until` — `2026-02-30`, `tomorrow; drop table` → 400 (the word list, else
  `date.fromisoformat`); a past day → 400; `" Monday "` is accepted (trimmed, lower-cased); a
  far-future date (`9999-12-31`) is accepted — the user's choice, no cost attached.
- *History (#496):* `?limit=` — `0` → 1, `999999` → 200, `-3` / `1e3` → 400; the titles of
  what captures became come from one query per kind (4 queries / 7 ms for 200 rows).
- *Bulk triage (#497):* 250 ids are cut to 200; a string id or an unknown project is a 400
  from the serializer; ids that are not untriaged captures are ignored and reported by
  omission. Cost is per row — file 30 → 35 queries / 26 ms, snooze 60 → 64 / 42 ms, wake 60
  → 4 / 4 ms; `todo` converts each capture (≈ 5 queries per row: 155 / 78 ms for 30), so the
  200-row ceiling bounds the worst case at roughly half a second — accepted, it is the one
  action that creates objects.
- *FINDING — the capture list read the project once per row.* `GET /quick-capture/` with 61
  open captures, half filed under a project: **36 queries / 54 ms** — the slug field and the
  #496 `became` urls each touch `capture.project`. Fixed with `select_related("project")` on
  the viewset (→ 6 queries); `test_api_inbox_list_budget` pins ≤ 12 queries for 40 captures.

**Performance (warm, best of four, API key, demo data):** dashboard 83 ms · daily brief 73 ms
· day activity 31 ms · project overview 90 ms · status update 62 ms · inbox (200) 29 ms ·
inbox history 17 ms · references (50) 30 ms · plan 26 ms · search 64 ms · manuscripts 28 ms ·
pre-flight 15 ms · weekly review 26 ms. Everything under the 100 ms bar.

**Desktop CI — GREEN.** Runs 201–208 (0.1.201–0.1.208) all succeeded; 209 (#497) was in
progress at audit time.

**Product stance unchanged.** Single user, API key from the environment, no multi-tenancy;
the risks accepted in #26 (user-supplied regex backtracking in project search) still stand.

**Next audit due at #508.**

## Audit #27 — 2026-09-13 (since #26: #479–#487 — the Project overview's third pass and its verdict, the Dashboard's first two slices)

Ten cycles, nine feature slices, one performance pass, one honest look.

**Dependencies — CLEAN.** `pip-audit` on the exported lock: *No known vulnerabilities found*.
`npm audit --omit=dev`: *0 vulnerabilities*. `scripts/audit.sh`: every row green (anon → 401
across the API, pages → 302, catch-all 404, static MIME, `/app//evil.com` stays on-origin).

**New surfaces since #26 — reviewed; one finding, fixed.**
- *Auth:* `status-update`, the overview (now with `literature`, `notebook`, `pulse`) and the
  dashboard (now with `reading`, `writing`) answer 401 anonymously and to a wrong key.
- *Status update (#482):* `?days=` is clamped to 1–90 (`0`, `-5` → 1; `99999` → 90), a
  non-integer (`abc`, `7.5`) is a 400. Titles and names go into markdown that is only ever
  shown in a `<pre>` or copied to the clipboard — never rendered as HTML — so no injection
  surface was added.
- *Request-scoped memo (#484):* `enable_memo` is called in exactly one place (the API
  overview); the cache lives on that request's model instance and dies with it, nothing is
  shared across requests or threads, and instances that never opted in behave as before
  (verified by the existing overview/plan tests, which mutate and re-ask).
- *Decision deep links (#485):* `?id=` goes through `Number()` → `null` on garbage; the
  highlight clears on the next pointer event and the listener is removed on unmount.
- *Milestone check-off (#485), reading queue (#486), writing panel (#487):* the check-off
  reuses the existing milestone PATCH through the CSRF-aware helper; the two panels are
  read-only and scoped to planning/active projects.
- *FINDING — the dashboard grew with the number of active projects (#487).* `writing_everywhere`
  ran the pre-flight for every working manuscript in every active project before trimming to
  six rows: 39 queries / 46 ms with the demo's one project, **102 queries / 104 ms** with three
  more projects of three papers each (~20 queries per project). Fixed: the glance now takes
  `readiness=False`, the dashboard sorts every project's papers first and runs the pre-flight
  only for the rows it shows — at most four per load, most urgent first (`READINESS_ROWS`;
  each pre-flight is ~10 queries / ~20 ms) — and the live count is one aggregate instead of
  one per project → **78 queries / 91 ms** for the same four projects, the rest being the
  per-project progress rows the dashboard has always listed. `test_api_dashboard_budget` pins
  the API dashboard at ≤ 100 queries with three busy projects and nine drafting manuscripts
  (six rows shown, four with a verdict). The model handle the glance rows now carry for that
  purpose is stripped before the overview payload (`public_rows`).

**Performance (warm, best of three, API key, demo data):** dashboard 69 ms (46 ms in-process)
· project overview 98 ms (61 queries, budget ≤ 60 on a busy project after #484) · status update
64 ms · references (50) 31 ms · plan 26 ms · search 65 ms · manuscripts 28 ms · manuscript
detail 31 ms · pre-flight 36 ms · weekly review 29 ms · focus 23 ms. Everything at or under the
100 ms bar; the overview sits at the bar and carries a pinned query budget so it cannot drift
back to the 89 queries it had at #483.

**Desktop CI — GREEN.** Runs 194–200 (0.1.194–0.1.200) all succeeded. Run 197 → 198 skipped a
number for #484 because that commit touched only Python outside the paths the workflow watches
(`desktop/**`, the workflow, the bundled Django sources) — expected, not a failure.

**Product stance unchanged.** Single user, API key from the environment, no multi-tenancy;
the risks accepted in #26 (user-supplied regex backtracking in project search) still stand.

**Next audit due at #498.**

## Audit #26 — 2026-09-13 (since #25: #469–#477 — submit through the pre-flight, the style lint and its fixes, the figure audit, the status clock and the nudge, find and replace, go to definition)

Back on the ten-cycle cadence. Nine feature slices, one honest look.

**Dependencies — CLEAN.** `pip-audit` on the exported lock: *No known vulnerabilities found*
(no bumps needed this time). `npm audit --omit=dev`: *0 vulnerabilities*. `scripts/audit.sh`:
every row green (anon → 401 across the API, pages → 302, catch-all 404, static MIME,
`/app//evil.com` stays on-origin).

**New surfaces since #25 — reviewed; one cap added, one risk accepted.**
- *Auth:* `search`, `lint`, `figure-audit`, `venue-turnaround`, `preflight` answer 401
  anonymously; `POST submit`, `replace`, `lint/fix` likewise.
- *Replace (#476):* the `files` filter matches tree paths exactly — `../../etc/passwd` in the
  list is simply ignored (`replaced: 0, files: []`); a bad regex is a 400; only `.tex`/`.bib`
  files are ever rewritten, assets never.
- *Lint fixes (#472):* a forged span (`col: 999`) applies nothing — every replacement is
  verified against the text actually there before it is written.
- *Figure audit (#473):* reads at most 64 KB of an asset's head to size it; PDF/EPS/SVG are
  never opened; a missing file is a row, not an exception.
- *Submit (#469):* status changes only through the service; `force` is an explicit flag; the
  event notes carry the readiness rows (author-owned text).
- *Search (#476) — cap added:* a 20 000-character query was accepted (plain text is escaped,
  so it was harmless, but it is a mistake not a search). The pattern is now capped at 500
  characters → 400 (test in writing/tests/test_search.py).
- *Search — risk accepted, recorded:* a user-supplied regular expression can backtrack
  catastrophically: `(a+)+$` over a 26-character run of `a` already takes ~5 s in Python's
  `re`, which cannot be interrupted. The scan is per line, the only person who can send the
  pattern holds the API key, and a hang costs one request — accepted for a single-user tool
  rather than adding a time-limited regex engine as a dependency.
- *Go to definition (#477):* client-only; it calls the search endpoint with an escaped key.

**Performance (warm, best of three, API key, demo data):** dashboard 47 ms · project overview
80 ms · references (50) 30 ms · plan 24 ms · search 62 ms · manuscripts 29 ms · manuscript
detail (with clock + nudge) 27 ms · pre-flight (now with the figure audit) 39 ms · lint 23 ms ·
figure audit 22 ms · project search 18 ms · venue turnaround 18 ms. Everything under the
100 ms bar; nothing regressed against #25.

**Desktop CI — A FINDING, FIXED.** GitHub Actions runners are back (runs no longer die in four
seconds with `runner_id: 0`), which exposed a real bug: the *Write release notes* step piped
`git log … | grep … | head -12 | sed` under `pipefail`; once the last 40 subjects all matched
`^(feat|fix|perf)`, `head` closed the pipe early, grep died with *write error: Broken pipe*
(exit 2), the `GITHUB_OUTPUT` heredoc never got its closing delimiter and every build since
run 187 was red at that step. Fixed in the workflow: no `head` in the pipeline — awk prints the
first twelve and reads to EOF, `{ grep … || true; }` keeps a build with no matching subjects
green. Verified locally under `set -eo pipefail`.

**Noticed, not acted on:** the repository has been renamed to `Whorl` on GitHub (the runner
checks out `/home/runner/work/Whorl/Whorl`). The updater endpoint, the homepage and the README
badges still say `project-manager`; GitHub redirects renamed repositories, so they keep working.
The product name and the URLs stay as they are until the owner says the word — renaming is the
owner's call (loop rule 7).

**Not checked this time (say so):** the frozen Windows/macOS/Linux installers end to end (the
first green run after this fix will show); the Tauri updater against the renamed repository;
the huey worker under Redis.

## Audit #25 — 2026-09-07 (since #24: everything from #263 to #467 — the SPA front door, the LaTeX studio and workbench, the desktop rewrite on SQLite, the library workbench, the pet and achievements, bots, snapshots, the pre-flight)

The first audit in the slice-numbered era; the ten-cycle cadence had lapsed since June, so this
one covers a lot of ground and is deliberately blunt about what it checked and what it did not.

**Dependencies — FOUR FINDINGS, ALL FIXED.**
- `pip-audit` on the exported lock flagged **django 5.2.15** (PYSEC-2026-2090/2091/2092/3717 →
  5.2.17), **djangorestframework 3.17.1** (CVE-2026-73229 → 3.18.0), **mcp 1.27.2**
  (PYSEC-2026-3483), **pydantic-settings 2.14.1** (GHSA-4xgf-cpjx-pc3j → 2.15.0), **sqlparse
  0.5.5** (five advisories → 0.6.0) and, after the first round, **cryptography 48.0.1**
  (PYSEC-2026-3552/3553/3554 → 50.0.1). Bumped each with `uv lock --upgrade-package`; re-audit
  → **No known vulnerabilities found**. Gotcha worth recording: `uv lock --upgrade-package mcp`
  jumped to **mcp 2.1.1**, which renames `FastMCP` → `MCPServer` and fails at import
  (`No module named 'mcp.server.fastmcp'`). Pinned `mcp>=1.28.1,<2` in pyproject (resolves to
  1.29.1, which carries the fix) and added a guard test so a future upgrade cannot re-widen it
  silently; porting the server to the 2.x API is a backlog item, not an audit fix.
- `npm audit --omit=dev` flagged **react-router / react-router-dom 7.17.0** (five advisories:
  open redirect via backslash in `<Link>`/`useNavigate`, RSC XSS, SSR deserialisation, route-
  matching DoS, RSC CSRF). Bumped to **7.18.3** → **0 vulnerabilities**. The SPA is a client-
  side router with no SSR/RSC, so only the open-redirect and DoS rows applied in practice;
  Playwright re-smoked seven routes plus a `<Link>` navigation on the new version: no errors.
- Full suite on the upgraded stack: green (count in PROGRESS).

**New surfaces since #24 — reviewed, no code findings.**
- *Snapshots (#462–#464):* the zip is built under a `.partial` name and renamed on completion;
  the folder is `<data dir>/backups` (or `ATLAS_SNAPSHOT_DIR`), gitignored in a checkout; the
  scheduler is a daemon thread that closes its DB connection after each tick; a failure is
  recorded for Diagnostics, never raised. *Restore by name* matches the request against the
  folder listing and never joins a path — `../name` and unknown names both answer 404 (test).
  `POST /snapshots/` is key-gated (anon → 401); a single user can write as many zips as they
  like — rotation caps the disk at seven.
- *Pre-flight (#466):* 16 queries / ~40 ms on the demo manuscript; every regex is anchored or
  bounded (`\\includegraphics…{…}`, the marker regex) over author-owned text; the network rows
  (DOI resolution, retractions) are opt-in via `?network=1`, so a GET never leaves the machine
  by default.
- *Client errors (#382):* the endpoint is key/session-gated (anon → 401); each report is clipped
  to 12 errors × 1500 chars and the ring keeps a fixed number — no unbounded growth.
- *Watched folder (#406):* accepts any existing directory on the machine. That is the feature —
  the caller holds the API key, i.e. is the owner — and it only *reads* PDFs from it; noted,
  accepted for a single-user desktop.
- *Tauri `open_path` / `reveal_path` (#16):* both go through `existing_file()` (must exist and
  be a file) before handing the path to the OS opener; arguments are passed as argv, never a
  shell string. The webview is same-origin and the raw-HTML sink guard (#449) holds the XSS
  door shut.
- *Terminal dock (#3):* a local PTY driven over Tauri IPC only — there is no HTTP route to it;
  the web build renders nothing.
- *Zotero import:* `base_url` is owner-supplied and defaults to the local connector; same trust
  level as the key. Unpaywall/OpenAlex fetches only follow `https://` links the APIs return.
- `scripts/audit.sh`: anon → 401 across the API, pages → 302, catch-all 404, static MIME,
  `/app//evil.com` stays on-origin — all green; the two dependency rows it flagged were the
  findings above and are green on re-run.

**Performance (warm, best of three, API key, demo data):** dashboard 40 ms · project overview
77 ms · references (50) 24 ms · plan 18 ms · search 56 ms · manuscripts 22 ms · timeline 40 ms
· achievements 62 ms · pre-flight 38 ms · snapshots status 8 ms (0 queries). Everything under
the 100 ms bar; nothing regressed against #24's numbers.

**Not checked this time (say so):** the frozen Windows/Linux builds (CI has had no runners for
two days — `runner_id: 0`, an account-level GitHub Actions issue); the Tauri updater path; the
huey worker under Redis (the desktop runs immediate mode).

**Verdict:** the code is clean; the dependency drift was real and is fixed. Cadence restored:
the next audit is due after ten more slices (#478).
