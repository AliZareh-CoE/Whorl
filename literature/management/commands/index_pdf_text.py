"""Read every attached PDF into searchable text (backfill for Library v2 slice 8)."""

from django.core.management.base import BaseCommand

from literature.fulltext import index_missing
from literature.models import Reference


class Command(BaseCommand):
    help = "Extract searchable text from attached PDFs that have not been read yet."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all", action="store_true", help="Re-read every PDF, not just new ones"
        )

    def handle(self, *args, **options):
        if options["all"]:
            from literature.fulltext import extract_text

            done = 0
            for reference in Reference.objects.exclude(pdf="").exclude(pdf=None):
                extract_text(reference)
                done += 1
        else:
            done = index_missing()
        self.stdout.write(self.style.SUCCESS(f"Indexed {done} PDF(s)."))
