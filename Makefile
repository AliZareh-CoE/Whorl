.PHONY: css css-watch up migrate test lint tectonic

TAILWIND := bin/tailwindcss

$(TAILWIND):
	mkdir -p bin
	curl -sL --fail -o $(TAILWIND) https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
	chmod +x $(TAILWIND)

css: $(TAILWIND)
	$(TAILWIND) -i static/src/app.css -o static/css/app.css --minify

css-watch: $(TAILWIND)
	$(TAILWIND) -i static/src/app.css -o static/css/app.css --watch

up:
	docker compose up -d

migrate:
	.venv/bin/python manage.py migrate

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

TECTONIC := bin/tectonic

tectonic:
	curl -sL --fail -o /tmp/tectonic.tar.gz "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-musl.tar.gz"
	tar -xzf /tmp/tectonic.tar.gz -C bin/
	chmod +x $(TECTONIC)
