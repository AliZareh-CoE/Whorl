"""Run the feed sweep: `manage.py refresh_feeds [--hours 12] [--limit 50] [--all]`. A cron line
for a server without huey: `20 */6 * * * cd /srv/atlas && uv run python manage.py
refresh_feeds`. The desktop app runs the same sweep from its scheduler thread."""

from django.core.management.base import BaseCommand

from literature import feeds
from literature.models import Feed


class Command(BaseCommand):
    help = "Fetch the followed journal and arXiv feeds and store their new entries."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=feeds.STALE_HOURS)
        parser.add_argument("--limit", type=int, default=feeds.SWEEP_LIMIT)
        parser.add_argument(
            "--all", action="store_true", help="every feed, not only the stale ones"
        )

    def handle(self, *args, **options):
        if options["all"]:
            out = feeds.refresh(list(Feed.objects.order_by("pk")[: options["limit"]]))
        else:
            out = feeds.refresh_stale(options["hours"], options["limit"])
        for feed in Feed.objects.exclude(last_error=""):
            self.stdout.write(f"ERR  {feed.title or feed.url}: {feed.last_error}")
        self.stdout.write(
            f"feeds {out['feeds']} · new {out['new']} · seen again {out['seen']} · "
            f"unchanged {out['unchanged']} · errors {out['errors']}"
        )
