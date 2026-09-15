"""Run the preprint watch's sweep: `manage.py check_preprints [--days 30] [--limit 200]
[--all]`. A cron line for a server without huey: `40 4 * * * cd /srv/atlas && uv run python
manage.py check_preprints`. The desktop app runs the same sweep from its scheduler thread."""

from django.core.management.base import BaseCommand

from literature import preprints


class Command(BaseCommand):
    help = "Ask arXiv / Semantic Scholar whether the library's preprints have a published version."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=preprints.STALE_DAYS)
        parser.add_argument("--limit", type=int, default=preprints.SWEEP_LIMIT)
        parser.add_argument(
            "--all", action="store_true", help="every preprint, not only the stale ones"
        )

    def handle(self, *args, **options):
        if options["all"]:
            refs = list(preprints.preprints().order_by("pk")[: options["limit"]])
            out = preprints.check_references(refs)
        else:
            out = preprints.check_stale(options["days"], options["limit"])
        for row in out["published"]:
            self.stdout.write(
                f"PUBLISHED  {row['bibtex_key']}  → {row['published_doi']}"
                f"{'  (' + row['published_venue'] + ')' if row['published_venue'] else ''}"
            )
        self.stdout.write(
            f"checked {out['checked']} · published {len(out['published'])} · "
            f"errors {out['errors']} · skipped {out['skipped']}"
        )
