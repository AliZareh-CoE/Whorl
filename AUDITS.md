# AUDITS

Every 10th loop cycle is a full security + performance audit (owner rule). Reports newest first.

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
