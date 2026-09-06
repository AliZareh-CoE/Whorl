.PHONY: css css-watch up migrate test lint tectonic doctor worker

TAILWIND := bin/tailwindcss

$(TAILWIND):
	mkdir -p bin
	curl -sL --fail -o $(TAILWIND) https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
	chmod +x $(TAILWIND)

css: $(TAILWIND)
	$(TAILWIND) -i assets/css/app.css -o static/css/app.css --minify

css-watch: $(TAILWIND)
	$(TAILWIND) -i assets/css/app.css -o static/css/app.css --watch

up:
	docker compose up -d

migrate:
	.venv/bin/python manage.py migrate

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

doctor:
	.venv/bin/python manage.py doctor

# The worker does NOT hot-reload: restart it after pulling or editing task code.
worker:
	-pkill -f "[m]anage.py run_huey"
	.venv/bin/python manage.py run_huey

TECTONIC := bin/tectonic

tectonic:
	curl -sL --fail -o /tmp/tectonic.tar.gz "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz"
	tar -xzf /tmp/tectonic.tar.gz -C bin/
	chmod +x $(TECTONIC)

js:  ## build the React islands (Node only needed for island development)
	cd frontend && npm install && node_modules/.bin/vite build

assets-check: css js  ## rebuild assets and fail if committed outputs are stale
	git diff --exit-code static/css/app.css static/js || \
	  (echo "✕ built assets differ from committed ones — commit the rebuilt files"; exit 1)

audit:  ## run the security probe sweep (every-10-cycles audit helper)
	@bash scripts/audit.sh

# Atlas desktop shell (Owner #30 slice 3) — requires Rust + tauri-cli (see desktop/README.md)
desktop:
	cd desktop && cargo tauri dev

desktop-build:
	cd desktop && cargo tauri build

# Freeze the Django server (atlas-server) and the MCP server (atlas-mcp) into
# desktop/server/dist/ — what the installer bundles; needs `uv sync --group build`.
# Run `make css` first so the server bundle carries the stylesheet.
desktop-server:
	uv run pyinstaller desktop/server/atlas_server.spec --noconfirm \
		--distpath desktop/server/dist --workpath /tmp/atlas-pyi
	uv run pyinstaller desktop/server/atlas_mcp.spec --noconfirm \
		--distpath desktop/server/dist --workpath /tmp/atlas-pyi-mcp
