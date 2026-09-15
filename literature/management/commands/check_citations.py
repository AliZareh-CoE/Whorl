"""Run the citation watch's sweep: `manage.py check_citations [--days 7] [--limit 200] [--all]`.
A cron line for a server without huey: `0 5 * * * cd /srv/atlas && uv run python manage.py
check_citations`. The desktop app runs the same sweep from its scheduler thread."""

from django.core.management.base import BaseCommand

from literature import citing


class Command(BaseCommand):
    help = "Ask OpenAlex which new papers cite the library's papers."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=citing.STALE_DAYS)
        parser.add_argument("--limit", type=int, default=citing.SWEEP_LIMIT)
        parser.add_argument(
            "--all", action="store_true", help="every watched paper, not only the stale ones"
        )

    def handle(self, *args, **options):
        if options["all"]:
            refs = list(citing.watched().order_by("pk")[: options["limit"]])
            out = citing.check_references(refs)
        else:
            out = citing.check_stale(options["days"], options["limit"])
        for row in out["new"]:
            cites = ", ".join(c["bibtex_key"] for c in row["cites"])
            self.stdout.write(f"NEW  {row['title'][:80]}  ({row['year'] or '?'})  cites {cites}")
        self.stdout.write(
            f"checked {out['checked']} · new {len(out['new'])} · seen again {out['seen']} · "
            f"errors {out['errors']} · skipped {out['skipped']}"
        )
