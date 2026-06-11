# AUDITS

Every 10th loop cycle is a full security + performance audit (owner rule). Reports newest first.

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
