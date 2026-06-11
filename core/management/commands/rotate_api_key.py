"""Rotate ATLAS_API_KEY: mint a strong key and rewrite it in .env (Owner idea #2)."""

import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Generate a new ATLAS_API_KEY and write it to the .env file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--env-file",
            default=str(Path(settings.BASE_DIR) / ".env"),
            help="Path to the .env file (default: <project root>/.env)",
        )

    def handle(self, *args, **options):
        env_path = Path(options["env_file"])
        if not env_path.exists():
            raise CommandError(f"{env_path} does not exist — create it from .env.example first.")

        new_key = secrets.token_urlsafe(32)
        lines = env_path.read_text().splitlines()
        replaced = False
        for i, line in enumerate(lines):
            if line.strip().startswith("ATLAS_API_KEY="):
                old = line.split("=", 1)[1]
                masked = f"{old[:4]}…{old[-4:]}" if len(old) > 8 else "(short key)"
                self.stdout.write(f"replacing previous key {masked}")
                lines[i] = f"ATLAS_API_KEY={new_key}"
                replaced = True
                break
        if not replaced:
            lines.append(f"ATLAS_API_KEY={new_key}")
        env_path.write_text("\n".join(lines) + "\n")

        self.stdout.write(self.style.SUCCESS(f"New API key written to {env_path}:"))
        self.stdout.write(f"  {new_key}")
        self.stdout.write(
            self.style.WARNING(
                "Now: restart the Django server, and update ATLAS_API_KEY anywhere it is "
                "registered (Claude MCP config, scripts, CI). The old key stops working "
                "on restart."
            )
        )
