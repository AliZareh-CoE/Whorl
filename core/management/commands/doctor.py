"""One-command health check for self-hosters (Backlog #16) — `manage.py doctor`."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check services, migrations, worker freshness, and optional components."

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))

    def warn(self, msg):
        self.stdout.write(self.style.WARNING(f"  ⚠ {msg}"))
        self.warnings += 1

    def fail(self, msg):
        self.stdout.write(self.style.ERROR(f"  ✕ {msg}"))
        self.failures += 1

    def handle(self, *args, **options):
        self.failures = self.warnings = 0
        base = Path(settings.BASE_DIR)
        self.stdout.write("Atlas doctor\n")

        # database + migrations
        try:
            from django.db import connection
            from django.db.migrations.executor import MigrationExecutor

            connection.ensure_connection()
            self.ok("database reachable")
            plan = MigrationExecutor(connection).migration_plan(
                MigrationExecutor(connection).loader.graph.leaf_nodes()
            )
            if plan:
                self.fail(f"{len(plan)} unapplied migration(s) — run `manage.py migrate`")
            else:
                self.ok("migrations up to date")
        except Exception as exc:
            self.fail(
                f"database unreachable ({exc.__class__.__name__}) — is `docker compose up -d` running?"
            )

        # redis + worker
        huey_conf = getattr(settings, "HUEY", {})
        if isinstance(huey_conf, dict) and huey_conf.get("immediate"):
            self.warn("huey immediate mode (test settings) — worker checks skipped")
        else:
            try:
                import redis

                redis.from_url(settings.REDIS_URL).ping()
                self.ok("redis reachable")
            except Exception as exc:
                self.fail(f"redis unreachable ({exc.__class__.__name__})")
            else:
                try:
                    from core.tasks import CODE_STAMP, doctor_ping

                    result = doctor_ping()
                    stamp = result.get(blocking=True, timeout=4)
                    if stamp == CODE_STAMP:
                        self.ok("worker alive and running current code")
                    else:
                        self.warn(
                            "worker alive but running STALE code — restart it: "
                            'pkill -f "[m]anage.py run_huey" && manage.py run_huey'
                        )
                except Exception:
                    self.warn(
                        "no worker responded in 4s — bots/citation-sync/PDF-fetch won't run "
                        "(start one: `manage.py run_huey`)"
                    )

        # static css
        css = base / "static" / "css" / "app.css"
        if css.exists():
            self.ok("Tailwind CSS built")
        else:
            self.fail("static/css/app.css missing — run `make css`")

        # optional components
        if (base / "bin" / "tectonic").exists():
            self.ok("Tectonic present (LaTeX compile enabled)")
        else:
            self.warn("Tectonic missing — `make tectonic` to enable PDF compilation")
        if (base / "tts_voices").glob("*.onnx") and list((base / "tts_voices").glob("*.onnx")):
            self.ok("Piper voice present (Read aloud enabled)")
        else:
            self.warn("Piper voice missing — `manage.py download_tts_voice` to enable Read aloud")

        # media writable + api key sanity
        try:
            media = Path(settings.MEDIA_ROOT)
            media.mkdir(exist_ok=True)
            probe = media / ".doctor-probe"
            probe.write_text("ok")
            probe.unlink()
            self.ok("MEDIA_ROOT writable")
        except Exception:
            self.fail(f"MEDIA_ROOT not writable: {settings.MEDIA_ROOT}")
        if not settings.ATLAS_API_KEY or "change-me" in settings.ATLAS_API_KEY:
            self.warn("ATLAS_API_KEY unset or default — run `manage.py rotate_api_key`")
        else:
            self.ok("ATLAS_API_KEY configured")

        self.stdout.write("")
        summary = f"{self.failures} problem(s), {self.warnings} warning(s)"
        if self.failures:
            self.stdout.write(self.style.ERROR(summary))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(summary))
