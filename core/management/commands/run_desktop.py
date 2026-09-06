"""Self-contained desktop entrypoint (#210c).

The one command the bundled Tauri app launches: prepare the per-user SQLite database +
static files + a login, then serve Atlas locally with waitress (pure-Python, cross-platform,
PyInstaller-friendly — gunicorn is Unix-only so it can't ship to Windows). Run under the
desktop settings: `manage.py run_desktop --settings=config.settings.desktop`.
"""

import os

from django.core.management import call_command
from django.core.management.base import BaseCommand


def write_server_info(data_dir, host: str, port: int) -> dict:
    """Publish where this instance is serving so the bundled MCP server (and anything else on
    the machine) can find it without configuration: the desktop shell may pick a port other
    than 8000 when it is taken, and `atlas-mcp` reads the live URL from here."""
    import json

    reach_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    info = {
        "url": f"http://{reach_host}:{port}",
        "port": port,
        "data_dir": str(data_dir),
        "mcp_bin": os.environ.get("ATLAS_MCP_BIN") or None,
        "version": os.environ.get("ATLAS_VERSION", "dev"),
        "pid": os.getpid(),
    }
    (data_dir / "server.json").write_text(json.dumps(info, indent=2))
    return info


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
        import shutil

        from django.conf import settings
        from django.contrib.auth import get_user_model

        # SQLite (#266): no server to start — `migrate` just creates the file. This replaced the
        # bundled Postgres, which never started reliably on Windows.

        # Upgrading from the old bundled-Postgres build leaves its now-unused cluster + logs in
        # the data dir; drop them so the switch to SQLite is clean and reclaims space — the owner
        # doesn't have to wipe the data dir by hand. (No-op on a fresh SQLite install.)
        for stale in ("pgdata", "pgsock"):
            shutil.rmtree(settings.DATA_DIR / stale, ignore_errors=True)
        (settings.DATA_DIR / "postgres.log").unlink(missing_ok=True)

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
        write_server_info(settings.DATA_DIR, host, port)
        self.stdout.write(self.style.SUCCESS(f"Atlas is running → http://{host}:{port}"))
        serve(application, host=host, port=port, threads=4)
