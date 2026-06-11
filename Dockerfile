# Atlas — single-image build for web + worker (select the role with the command)
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# build CSS with the standalone Tailwind CLI, then collect static for whitenoise
RUN curl -sL --fail -o /tmp/tailwindcss \
      https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x /tmp/tailwindcss \
    && /tmp/tailwindcss -i assets/css/app.css -o static/css/app.css --minify \
    && DJANGO_SETTINGS_MODULE=config.settings.prod SECRET_KEY=build-only \
       .venv/bin/python manage.py collectstatic --noinput

EXPOSE 8000
CMD [".venv/bin/gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2"]
