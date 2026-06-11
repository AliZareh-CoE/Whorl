#!/bin/sh
# Web entrypoint: migrate, then serve.
set -e
.venv/bin/python manage.py migrate --noinput
exec .venv/bin/gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 2
