"""Audit #34: remove storage files under MEDIA_ROOT that no Document or DocumentVersion row
references. Only the documents app's two prefixes (`projects/*/documents/`,
`projects/*/versions/`) are considered — reference PDFs and manuscript assets live elsewhere.
Dry run by default; `--apply` deletes and removes the directories it empties."""

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from documents.models import Document, DocumentVersion

PREFIXES = ("/documents/", "/versions/")


def orphaned_files() -> list[str]:
    """Storage names (relative to MEDIA_ROOT) under the documents prefixes with no row."""
    # backlog 357: a file in the Trash is still referenced — its row hides from the default
    # manager, not from this sweep
    known = set(Document.all_objects.exclude(file="").values_list("file", flat=True))
    known |= set(DocumentVersion.objects.exclude(file="").values_list("file", flat=True))
    root = os.path.join(settings.MEDIA_ROOT, "projects")
    out = []
    for dirpath, _dirs, files in os.walk(root):
        rel_dir = os.path.relpath(dirpath, settings.MEDIA_ROOT).replace(os.sep, "/") + "/"
        if not any(p in rel_dir for p in PREFIXES):
            continue
        for name in files:
            rel = rel_dir + name
            if rel not in known:
                out.append(rel)
    return sorted(out)


def prune(apply: bool) -> tuple[int, int]:
    """(orphans found, removed). With apply=False nothing is touched."""
    orphans = orphaned_files()
    removed = 0
    if apply:
        for rel in orphans:
            path = os.path.join(settings.MEDIA_ROOT, rel)
            try:
                os.remove(path)
                removed += 1
            except OSError:
                continue
            folder = os.path.dirname(path)
            root = os.path.join(settings.MEDIA_ROOT, "projects")
            while folder.startswith(root) and folder != root:
                try:
                    os.rmdir(folder)  # only an emptied directory goes
                except OSError:
                    break
                folder = os.path.dirname(folder)
    return len(orphans), removed


class Command(BaseCommand):
    help = "Remove document / version storage files no row references (dry run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="delete the orphans")

    def handle(self, *args, **options):
        orphans = orphaned_files()
        for rel in orphans[:10]:
            self.stdout.write(f"  {rel}")
        if len(orphans) > 10:
            self.stdout.write(f"  … {len(orphans) - 10} more")
        if options["apply"]:
            found, removed = prune(apply=True)
            self.stdout.write(f"Removed {removed} of {found} orphaned file(s).")
        else:
            self.stdout.write(f"{len(orphans)} orphaned file(s); run with --apply to remove them.")
