"""Run the retraction watch's sweep: `manage.py check_retractions [--days 30] [--limit 200]
[--all]`. A cron line for a server without huey: `0 4 * * * cd /srv/atlas && uv run python
manage.py check_retractions`. The desktop app runs the same sweep from its scheduler thread."""

from django.core.management.base import BaseCommand

from literature import retractions
from literature.models import Reference


class Command(BaseCommand):
    help = "Check papers with a DOI against Crossref's retraction notices (stale ones by default)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=retractions.STALE_DAYS)
        parser.add_argument("--limit", type=int, default=retractions.SWEEP_LIMIT)
        parser.add_argument(
            "--all", action="store_true", help="every paper with a DOI, not only the stale ones"
        )

    def handle(self, *args, **options):
        if options["all"]:
            refs = list(
                Reference.objects.exclude(doi__isnull=True)
                .exclude(doi="")
                .order_by("pk")[: options["limit"]]
            )
            out = retractions.check_references(refs)
        else:
            out = retractions.check_stale(options["days"], options["limit"])
        for row in out["retracted"]:
            self.stdout.write(f"RETRACTED  {row['bibtex_key']}  ({row['kind']}, {row['notice']})")
        self.stdout.write(
            f"checked {out['checked']} · retracted {len(out['retracted'])} · "
            f"errors {out['errors']} · skipped {out['skipped']}"
        )
