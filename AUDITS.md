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
