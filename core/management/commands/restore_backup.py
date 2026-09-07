"""Restore an Atlas backup zip: `manage.py restore_backup path/to/backup.zip`.

Stops nothing by itself — run it while Atlas is NOT serving (the desktop app applies staged
restores on its own at the next launch; this command is for servers and scripts). The
previous database and media are kept in `restore-backup-<timestamp>/` inside the data dir.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Restore a backup zip (database + media), keeping the previous data next to it."

    def add_arguments(self, parser):
        parser.add_argument("zip_path")
        parser.add_argument(
            "--stage-only",
            action="store_true",
            help="only stage it; the desktop app applies it at the next launch",
        )

    def handle(self, *args, **options):
        from core.backup import RestoreError, apply_pending_restore, stage_restore

        path = Path(options["zip_path"])
        if not path.is_file():
            raise CommandError(f"{path} does not exist")
        with open(path, "rb") as fh:
            try:
                manifest = stage_restore(fh)
            except RestoreError as exc:
                raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"Staged backup from {manifest.get('created_at')} ({manifest['media_files']} media files)."
        )
        if options["stage_only"]:
            return
        result = apply_pending_restore()
        if not result or not result["ok"]:
            raise CommandError((result or {}).get("detail", "nothing was staged"))
        self.stdout.write(
            self.style.SUCCESS(
                result["detail"] + f" Previous data kept in {result['kept_previous_in']}."
            )
        )
