"""Write a backup snapshot into the backups folder: `manage.py snapshot [--if-due]`.

The desktop does this on its own once a day (#462). A server install runs it from cron:
`0 3 * * * cd /srv/atlas && uv run python manage.py snapshot --if-due`. The folder is
`<data dir>/backups` (override with ATLAS_SNAPSHOT_DIR); the last 7 are kept.
"""

from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Write a backup zip into the backups folder and rotate the old ones."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-due", action="store_true", help="only when the newest is a day old"
        )
        parser.add_argument(
            "--dir", default=None, help="folder to write into (default: data dir/backups)"
        )
        parser.add_argument("--keep", type=int, default=None, help="how many to keep (default 7)")

    def handle(self, *args, **options):
        from core import snapshots

        directory = Path(options["dir"]) if options["dir"] else None
        keep = options["keep"] if options["keep"] is not None else snapshots.KEEP
        if options["if_due"] and not snapshots.due(directory=directory):
            last = snapshots.last_snapshot(directory)
            self.stdout.write(
                "Not due — "
                + (f"newest snapshot {last['name']}" if last else "nothing to keep yet")
            )
            return
        result = snapshots.take_snapshot(directory, keep=keep)
        self.stdout.write(
            self.style.SUCCESS(f"Snapshot written: {result['path']} ({result['size_bytes']} bytes)")
        )
        if result["removed"]:
            self.stdout.write("Removed: " + ", ".join(result["removed"]))
