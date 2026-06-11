# AUDITS

Every 10th loop cycle is a full security + performance audit (owner rule). Reports newest first.

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
