"""#505: note history.

Autosave is a one-way door without this. Every save that changes a note's title or body first
files the state it is about to replace as a ``NoteRevision`` — unless the newest revision is
less than ``COALESCE_MINUTES`` old, in which case the burst of autosaves counts as one edit
and nothing new is filed. The last ``KEEP`` revisions per note are kept. A revision can be
read with a unified diff against the note as it is now, and restored (which files the
current state first, so a restore is itself undoable).
"""

from __future__ import annotations

import difflib
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Note, NoteRevision

COALESCE_MINUTES = 10
KEEP = 50


def _words(text: str) -> int:
    return len((text or "").split())


def snapshot(note: Note, *, force: bool = False) -> NoteRevision | None:
    """File the note's current title/body as a revision (the state a save is about to
    replace). Returns the revision, or None when the newest one is recent enough to absorb
    this edit (`force` files regardless)."""
    latest = note.revisions.order_by("-created_at", "-id").first()
    if (
        latest is not None
        and not force
        and latest.created_at >= timezone.now() - timedelta(minutes=COALESCE_MINUTES)
    ):
        return None
    if latest is not None and latest.title == note.title and latest.body == (note.body or ""):
        return None  # nothing changed since the last snapshot
    revision = NoteRevision.objects.create(
        note=note, title=note.title, body=note.body or "", words=_words(note.body)
    )
    stale = list(note.revisions.order_by("-created_at", "-id").values_list("pk", flat=True)[KEEP:])
    if stale:
        NoteRevision.objects.filter(pk__in=stale).delete()
    return revision


def revision_rows(note: Note) -> list[dict]:
    """Newest first: id, when, title, words, and the word delta against the next-newer state
    (the note itself for the newest)."""
    revisions = list(note.revisions.order_by("-created_at", "-id"))
    rows = []
    newer_words = _words(note.body)
    for r in revisions:
        rows.append(
            {
                "id": r.pk,
                "created_at": r.created_at.isoformat(),
                "title": r.title,
                "words": r.words,
                "delta_words": newer_words - r.words,
                "title_changed": r.title != note.title,
            }
        )
        newer_words = r.words
    return rows


def revision_diff(note: Note, revision: NoteRevision) -> dict:
    """The revision's text plus a unified diff from it to the note as it is now."""
    then = (revision.body or "").splitlines()
    now = (note.body or "").splitlines()
    diff = list(
        difflib.unified_diff(
            then,
            now,
            fromfile=f"{revision.title} (then)",
            tofile=f"{note.title} (now)",
            lineterm="",
            n=2,
        )
    )
    added = sum(1 for line in diff[2:] if line.startswith("+"))
    removed = sum(1 for line in diff[2:] if line.startswith("-"))
    return {
        "id": revision.pk,
        "created_at": revision.created_at.isoformat(),
        "title": revision.title,
        "body": revision.body,
        "words": revision.words,
        "diff": "\n".join(diff),
        "added": added,
        "removed": removed,
        "same": revision.body == (note.body or "") and revision.title == note.title,
    }


@transaction.atomic
def restore(note: Note, revision: NoteRevision) -> dict:
    """Put the revision's title and body back on the note — after filing the current state
    (forced), so the restore can itself be undone. Links, references and tags are re-synced
    by the caller's save path; returns {restored, filed}."""
    from .relink import rename_links
    from .services import sync_note_links, sync_note_references
    from .tags import sync_note_tags

    filed = snapshot(note, force=True)
    old_title = note.title
    note.title = revision.title
    note.body = revision.body
    note.save(update_fields=["title", "body", "updated_at"])
    if old_title.strip().lower() != note.title.strip().lower():
        rename_links(note.project, old_title, note.title)
    sync_note_links(note)
    sync_note_references(note)
    sync_note_tags(note)
    return {"restored": revision.pk, "filed": filed.pk if filed else None}
