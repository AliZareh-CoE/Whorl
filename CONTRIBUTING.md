# Contributing to Atlas

Thanks for your interest! Atlas is a self-hosted research workbench built with deliberately
boring technology: Django 5, PostgreSQL, HTMX — no SPA, no Node build.

## Development setup

Follow the Quick start in `README.md` (uv + docker compose; under 5 minutes). Then:

```bash
make test     # pytest — the suite must stay green
make lint     # ruff check + ruff format --check
make css      # rebuild Tailwind after template changes
```

## Ground rules

- **Architecture & conventions** live in `CLAUDE.md` — models per app, business logic in
  `services.py`, thin views, HTMX only where it removes a reload, everything in the admin.
- **Vertical slices**: model → migration → admin → view → template → tests, one slice per
  conventional commit (`feat(plans): …`, `fix(literature): …`).
- **Tests are non-negotiable**: every service function and computed property gets unit tests;
  every page gets a logged-in smoke test. Query budgets in `core/tests/test_query_budgets.py`
  guard against N+1 regressions — keep them green.
- **No new dependencies** without a written rationale in `DECISIONS.md` (see the Tectonic and
  Piper entries for the expected shape).
- **Security and performance are standing constraints** — see `AUDITS.md` for the bar.

## Decision history

`DECISIONS.md` records every non-obvious choice with rejected alternatives, and `PROGRESS.md`
tracks build state. Read them before proposing structural changes — the answer to "why is it
like this?" is usually there.

## Architecture invariants (read before touching routing or the frontend)

Atlas is a Django app with a React SPA grafted on by the "islands → full SPA" migration
(see `DECISIONS.md` Owner ideas #19–20). Two invariants keep the two halves from drifting:

- **Routing: slash-less = SPA, trailing-slash = classic.** A single catch-all in
  `core/urls.py` serves the React shell for *any* slash-less path (except `api/`, `static/`,
  `media/`); classic server-rendered pages keep their trailing-slash URLs, and the old
  dashboard lives at `/classic/`. **Adding a SPA page is a frontend-only change** — add the
  route in `frontend/src/app/main.tsx`; do **not** add a per-route Django pattern (that
  hand-mirroring caused real bugs — see `DECISIONS.md` #77). New classic pages keep using
  trailing-slash URLs as normal.
- **The frontend builds to committed artifacts.** The React workspace lives in `frontend/`
  (Vite + TypeScript). `make js` builds the islands and the SPA to `static/js/` and those
  outputs are **committed**, so running or self-hosting Atlas never needs Node — only
  *developing* the frontend does. `make assets-check` fails CI if the committed build is
  stale; run `make css && make js` before committing UI changes.

## No paid LLM APIs

Atlas's "AI collaborator" is the owner's Claude subscription via the MCP server, plus local
NLP (`core/keywords.py`, `core/summarize.py` — no models, no network). Do not add features
that call a paid LLM API. Smart features are either local heuristics or routed through MCP.
