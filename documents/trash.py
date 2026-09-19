"""A Trash for deleted files (backlog 357): a deleted general document waits TRASH_DAYS with its
row, its bytes and its version history intact, out of every list and count (the default
manager hides it), and comes back with one click — into the folder it left, or the project
root when that folder is gone, under a numbered name when a new file took its path. The
nightly sweep (huey, the desktop scheduler) removes what has waited long enough; that
delete cascades the versions and unlinks the bytes through documents/signals.py.

The same shape as the Today Trash (core/todos.py)."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db.models import QuerySet
from django.utils import timezone

from .models import Document

TRASH_DAYS = 30


def trash(doc: Document) -> Document:
    """Into the Trash — out of every list and count, back with ``restore`` for TRASH_DAYS.
    Already trashed: unchanged."""
    if doc.deleted_at is None:
        doc.deleted_at = timezone.now()
        doc.save(update_fields=["deleted_at", "updated_at"])
    return doc


def restore(doc: Document) -> Document:
    """Back from the Trash. Its folder may have been deleted meanwhile (the row's folder is
    then null: the project root) and a new file may sit at its path (``write_project_file``
    and an upload only see live rows) — the name is numbered then, the way a same-name upload
    is, and ``rel_path`` follows the folder it lands in. Already live: unchanged."""
    if doc.deleted_at is None:
        return doc
    from .bulk import available_name, sync_rel_path

    doc.deleted_at = None
    fields = ["deleted_at", "updated_at"]
    if doc.role == Document.Role.GENERAL:
        name = (doc.rel_path or doc.title or "file").rsplit("/", 1)[-1]
        free = available_name(doc.project, doc.folder, name)
        if free != name:
            doc.title = free
            doc.rel_path = (
                doc.rel_path.rsplit("/", 1)[0] + "/" + free if "/" in doc.rel_path else free
            )
            fields += ["title", "rel_path"]
    doc.save(update_fields=fields)
    sync_rel_path(doc)  # the folder may have gone: rel_path follows
    return doc


def trashed(project) -> QuerySet:
    """The project's Trash, newest deletion first."""
    return Document.all_objects.trashed().filter(project=project).order_by("-deleted_at", "-id")


def empty(project) -> int:
    """Delete the project's whole Trash for good (rows, versions, bytes). Returns how many
    documents went."""
    rows = list(trashed(project))
    for doc in rows:
        doc.delete()  # per instance: versions cascade and every file unlinks on commit
    return len(rows)


def prune_trash(now: datetime | None = None) -> int:
    """Remove what has waited in the Trash longer than TRASH_DAYS — the nightly sweep (huey)
    and the desktop scheduler both call this. Returns how many documents went."""
    cutoff = (now or timezone.now()) - timedelta(days=TRASH_DAYS)
    rows = list(Document.all_objects.trashed().filter(deleted_at__lt=cutoff))
    for doc in rows:
        doc.delete()
    return len(rows)
