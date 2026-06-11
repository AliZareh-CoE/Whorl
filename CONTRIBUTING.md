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
