"""#502: link hygiene.

Two things every wiki-style tool needs and most research tools lack:

* ``rename_links`` — when a note is renamed, every ``[[Old title]]`` across the project is
  rewritten to ``[[New title]]`` (case-insensitively; an alias after ``|`` is kept), in notes
  and in the other markdown bodies that render mentions (#407): decisions, lab-notebook
  entries and inbox captures. Links stay alive instead of turning into "unwritten" stubs.
* ``link_mentions`` — a note whose title appears in another note's prose without a link gets
  linked with one click: the first plain mention in each mentioning note is wrapped in
  ``[[ ]]`` and that note's links are re-synced.
"""

from __future__ import annotations

import re

from django.db import transaction
from django.utils import timezone

from .models import Note
from .services import sync_note_links


def _link_re(title: str) -> re.Pattern:
    return re.compile(r"\[\[\s*" + re.escape(title) + r"\s*(\|[^\]\n]*)?\]\]", re.IGNORECASE)


def _mention_re(title: str) -> re.Pattern:
    # a plain mention: the title as words, not already inside [[ ]] and not glued to letters
    return re.compile(r"(?<![\[\w])" + re.escape(title) + r"(?![\]\w])", re.IGNORECASE)


def _rewrite(text: str, pattern: re.Pattern, new_title: str) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"[[{new_title}{m.group(1) or ''}]]"

    return pattern.sub(repl, text or ""), count


def _bodies(project):
    """(instance, [field, …]) for every markdown body in the project that can carry links."""
    from projects.models import DecisionRecord
    from research.models import ExperimentEntry

    from .models import QuickCapture

    yield from ((n, ["body"]) for n in project.notes.all())
    yield from (
        (d, ["context", "decision", "alternatives"])
        for d in DecisionRecord.objects.filter(project=project)
    )
    yield from ((e, ["body"]) for e in ExperimentEntry.objects.filter(project=project))
    yield from ((c, ["text"]) for c in QuickCapture.objects.filter(project=project))


@transaction.atomic
def rename_links(project, old_title: str, new_title: str) -> dict:
    """Rewrite [[old_title]] → [[new_title]] everywhere in the project. Returns
    {links, notes, decisions, experiments, captures} counts; nothing changes when the titles
    only differ in case."""
    old, new = (old_title or "").strip(), (new_title or "").strip()
    out = {"links": 0, "notes": 0, "decisions": 0, "experiments": 0, "captures": 0}
    if not old or not new or old.lower() == new.lower():
        return out
    pattern = _link_re(old)
    kinds = {
        "Note": "notes",
        "DecisionRecord": "decisions",
        "ExperimentEntry": "experiments",
        "QuickCapture": "captures",
    }
    for obj, fields in _bodies(project):
        changed = []
        for field in fields:
            text, n = _rewrite(getattr(obj, field), pattern, new)
            if n:
                setattr(obj, field, text)
                changed.append(field)
                out["links"] += n
        if changed:
            obj.updated_at = timezone.now()
            obj.save(update_fields=[*changed, "updated_at"])
            out[kinds[obj.__class__.__name__]] += 1
            if isinstance(obj, Note):
                sync_note_links(obj)
    return out


@transaction.atomic
def link_mentions(note: Note, source_ids: list[int] | None = None) -> dict:
    """Wrap the first plain mention of `note.title` in each mentioning note (all of them, or
    only `source_ids`) in [[ ]] and re-sync that note's links. Returns {linked: [{id, title}]}."""
    from .services import note_links

    mentions = note_links(note)["mentions"]
    wanted = {m["id"] for m in mentions}
    if source_ids is not None:
        wanted &= {int(i) for i in source_ids}
    pattern = _mention_re(note.title)
    linked = []
    for source in Note.objects.filter(pk__in=wanted).order_by("title"):
        body, n = pattern.subn(f"[[{note.title}]]", source.body or "", count=1)
        if not n:
            continue
        source.body = body
        source.save(update_fields=["body", "updated_at"])
        sync_note_links(source)
        linked.append({"id": source.pk, "title": source.title})
    return {"linked": linked}
