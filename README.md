# Atlas

Self-hosted, single-user, research-oriented project management. Django, batteries included:
projects → phases → milestones, documents, literature, notes, manuscripts — everything in
exactly one obvious place.

## Quick start

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker with Compose, `make`, `curl`.

```bash
git clone <repo-url> atlas && cd atlas

cp .env.example .env          # edit SECRET_KEY / ATLAS_API_KEY if you like
uv venv --python 3.12 && uv sync

docker compose up -d          # Postgres 16 on localhost:5432
make css                      # downloads the Tailwind standalone CLI on first run

.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser   # you are the single user
.venv/bin/python manage.py seed_demo         # optional demo data
.venv/bin/python manage.py runserver
```

Open http://127.0.0.1:8000/ and log in. The Django admin lives at `/admin/`.

## API

Everything in the UI is also available under `/api/v1/` (interactive docs at `/api/docs/`).
Authenticate with the `X-API-Key` header, checked against `ATLAS_API_KEY` in your `.env`:

```bash
curl -H "X-API-Key: $ATLAS_API_KEY" http://127.0.0.1:8000/api/v1/projects/

# add a reference by DOI and link it to a project
curl -H "X-API-Key: $ATLAS_API_KEY" -H "Content-Type: application/json" \
     -d '{"doi": "10.1038/nature12373", "project": "my-project"}' \
     http://127.0.0.1:8000/api/v1/references/by-doi/
```

## Development

```bash
make test     # pytest -q
make lint     # ruff check + ruff format --check
make css-watch
```

State and conventions for the autonomous build live in `CLAUDE.md` (constitution),
`PROGRESS.md` (current status + phase gate reports), and `DECISIONS.md` (decision log + backlog).
