"""Self-contained desktop entrypoint (#210c).

The one command the bundled Tauri app launches: prepare the per-user SQLite database +
static files + a login, then serve Atlas locally with waitress (pure-Python, cross-platform,
PyInstaller-friendly — gunicorn is Unix-only so it can't ship to Windows). Run under the
desktop settings: `manage.py run_desktop --settings=config.settings.desktop`.
"""

import os

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Prepare and serve the bundled single-user Atlas (SQLite, no Redis/Docker)."

    def add_arguments(self, parser):
        parser.add_argument("--host", default=os.environ.get("ATLAS_HOST", "127.0.0.1"))
        parser.add_argument("--port", type=int, default=int(os.environ.get("ATLAS_PORT", "8000")))
        parser.add_argument(
            "--setup-only",
            action="store_true",
            help="prepare the db/static/login but don't start the server (used by tests)",
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from django.contrib.auth import get_user_model

        # start the bundled Postgres (initdb on first run) before Django connects (#210g)
        from core.desktop_runtime import ensure_postgres

        data_dir = settings.DATA_DIR
        ensure_postgres(data_dir, settings.PG_PORT)
        self.stdout.write("Postgres is up.")

        # First-run prep. Use verbosity=1 so the log shows progress instead of looking like a
        # silent black box (#241), and skip the slow static re-collect on later launches of the
        # SAME build — keyed on ATLAS_VERSION (set by the Tauri shell from the app version), so an
        # app update still re-collects.
        self.stdout.write("Preparing the database…")
        call_command("migrate", "--no-input", verbosity=1)

        version = os.environ.get("ATLAS_VERSION", "dev")
        marker = settings.STATIC_ROOT / ".collected_version"
        if marker.exists() and marker.read_text(errors="ignore").strip() == version:
            self.stdout.write("Static assets already collected for this version.")
        else:
            self.stdout.write("Collecting static assets (first run for this version)…")
            call_command("collectstatic", "--no-input", verbosity=1)
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(version)

        User = get_user_model()
        username = os.environ.get("ATLAS_ADMIN_USER", "atlas")
        password = os.environ.get("ATLAS_ADMIN_PASSWORD", "atlas")
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username, "", password)
            self.stdout.write(f"Created the Atlas login '{username}'.")

        if options["setup_only"]:
            self.stdout.write("Setup complete.")
            return

        from waitress import serve

        from config.wsgi import application

        host, port = options["host"], options["port"]
        self.stdout.write(self.style.SUCCESS(f"Atlas is running → http://{host}:{port}"))
        serve(application, host=host, port=port, threads=4)
