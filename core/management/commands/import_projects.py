"""Bulk-import a folder of existing projects (#535): `manage.py import_projects <folder>`.

Dry run by default — add `--apply` to bring them in. `--only "Name A" "Name B"` limits the
run to a few subfolders; `--pdfs documents` keeps PDFs as files instead of library papers;
`--markdown documents` keeps Markdown as files instead of notes.
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Turn every subfolder of a folder into an Atlas project (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("path", help="the folder that contains one subfolder per project")
        parser.add_argument("--apply", action="store_true", help="import (default: only look)")
        parser.add_argument("--only", nargs="*", default=None, help="subfolder names to import")
        parser.add_argument("--pdfs", choices=["library", "documents"], default="library")
        parser.add_argument("--markdown", choices=["notes", "documents"], default="notes")

    def handle(self, *args, **options):
        from projects import importer

        try:
            root = importer.resolve_root(options["path"])
            if options["apply"]:
                rows = importer.import_folder(
                    root, options["only"], options["pdfs"], options["markdown"]
                )
            else:
                rows = [
                    p.as_dict()
                    for p in importer.plan(
                        root, options["only"], options["pdfs"], options["markdown"]
                    )
                ]
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if not rows:
            self.stdout.write(f"No project folders under {root}.")
            return
        for row in rows:
            state = "exists" if row["exists"] else "new"
            if options["apply"]:
                state = "created" if row.get("created") else "updated"
            self.stdout.write(
                f"{row['folder']:<32} {row['name']:<32} {state:<8} "
                f"{row['pdfs']:>4} pdfs {row['notes']:>4} notes {row['files']:>5} files"
                + (
                    f"  → {row['documents']} documents, {row['notes']} notes, "
                    f"{row['references']} papers"
                    if options["apply"]
                    else ""
                )
            )
            for s in row["skipped"]:
                self.stdout.write(f"    skipped {s['path']}: {s['reason']}")
            for e in row.get("errors", []):
                self.stdout.write(self.style.WARNING(f"    error {e['path']}: {e['reason']}"))
        if not options["apply"]:
            self.stdout.write("Dry run — add --apply to import.")
