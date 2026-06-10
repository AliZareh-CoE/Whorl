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

## Development

```bash
make test     # pytest -q
make lint     # ruff check + ruff format --check
make css-watch
```

State and conventions for the autonomous build live in `CLAUDE.md` (constitution),
`PROGRESS.md` (current status + phase gate reports), and `DECISIONS.md` (decision log + backlog).
