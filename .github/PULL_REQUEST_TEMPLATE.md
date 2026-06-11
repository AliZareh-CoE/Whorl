## What & why

<!-- One or two sentences. Link the issue if there is one. -->

## Checklist

- [ ] `pytest -q`, `ruff check .`, `ruff format --check .` pass
- [ ] If TypeScript changed: `cd frontend && tsc --noEmit` passes and `make js` artifacts are committed
- [ ] If a page changed: `make css` rebuilt and committed (see `make assets-check`)
- [ ] Tests added/updated for new behavior
- [ ] No paid LLM API calls introduced (local NLP or MCP only)

## Architecture notes

<!-- Adding a SPA page? You only touch React — the Django catch-all serves any slash-less
     path (see CONTRIBUTING § Routing). Don't add per-route Django patterns. -->
