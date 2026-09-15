"""Run the PDF finder's sweep: `manage.py find_pdfs [--days 30] [--limit 25] [--budget 600]`
(#544). Papers without a PDF that carry a DOI or an arXiv id, never looked at first, then the
ones not asked about for `--days`; arXiv, Unpaywall, Semantic Scholar and OpenAlex in turn. A
cron line for a server without huey: `20 5 * * * cd /srv/atlas && uv run python manage.py
find_pdfs`. The desktop app runs a smaller sweep from its scheduler thread."""

from django.core.management.base import BaseCommand

from literature import oa


class Command(BaseCommand):
    help = "Look for free PDFs for the papers without one (stale ones by default)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=oa.STALE_DAYS)
        parser.add_argument("--limit", type=int, default=oa.SWEEP_LIMIT)
        parser.add_argument("--budget", type=int, default=oa.BUDGET_SECONDS, help="seconds")

    def handle(self, *args, **options):
        out = oa.sweep_missing(options["days"], options["limit"], options["budget"])
        for row in out["attached"]:
            self.stdout.write(
                f"ATTACHED  {row['bibtex_key']}  via {oa.SOURCE_LABELS[row['source']]}"
            )
        self.stdout.write(
            f"checked {out['checked']} · attached {len(out['attached'])} · "
            f"not found {out['not_found']} · errors {out['errors']}"
            + (f" · stopped ({out['stopped']})" if out["stopped"] else "")
        )
