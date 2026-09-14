"""#510: related notes — what else in the project this note is about.

Two notes are related when they cite the same papers, carry the same #tags, link to the
same notes, or share informative words. Notes already linked in either direction are the
known neighbourhood and are left out; the point is the link you have not made yet. Pure
Python over the project's notes (a few hundred at most), a handful of grouped queries.
"""

from __future__ import annotations

from collections import defaultdict

from core.keywords import ALL_STOPWORDS, WORD_RE
from notes.models import Note, NoteLink

REF_WEIGHT = 3.0
TAG_WEIGHT = 2.0
LINK_WEIGHT = 2.0
TERM_WEIGHT = 0.5
TERM_CAP = 6
MIN_SCORE = 1.0
DEFAULT_LIMIT = 5
MAX_LIMIT = 20


def terms(text: str) -> set[str]:
    """Informative words: four letters or more, not a stopword, lower-cased."""
    out = set()
    for word in WORD_RE.findall(text or ""):
        for part in (word, *word.split("-")):
            part = part.lower()
            if len(part) >= 4 and part not in ALL_STOPWORDS:
                out.add(part)
    return out


def related_notes(note: Note, limit: int = DEFAULT_LIMIT) -> list[dict]:
    """The strongest unlinked neighbours, best first: {id, title, score, reasons, url}."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    project = note.project
    others = list(project.notes.exclude(pk=note.pk).only("id", "title", "body", "tags"))
    if not others:
        return []
    linked = set(NoteLink.objects.filter(source=note).values_list("target_id", flat=True)) | set(
        NoteLink.objects.filter(target=note).values_list("source_id", flat=True)
    )
    ids = [n.pk for n in others] + [note.pk]
    refs: dict[int, set[int]] = defaultdict(set)
    for note_id, ref_id in Note.references.through.objects.filter(note_id__in=ids).values_list(
        "note_id", "reference_id"
    ):
        refs[note_id].add(ref_id)
    targets: dict[int, set[int]] = defaultdict(set)
    for source_id, target_id in NoteLink.objects.filter(source_id__in=ids).values_list(
        "source_id", "target_id"
    ):
        targets[source_id].add(target_id)
    titles = {n.pk: n.title for n in others}
    my_refs, my_tags = refs[note.pk], set(note.tags or [])
    my_targets = targets[note.pk] - {note.pk}
    my_terms = terms(f"{note.title} {note.body}")
    rows = []
    for other in others:
        if other.pk in linked:
            continue
        reasons, score = [], 0.0
        shared_refs = len(my_refs & refs[other.pk])
        if shared_refs:
            score += REF_WEIGHT * shared_refs
            reasons.append(f"cites {shared_refs} of the same paper{'s' if shared_refs > 1 else ''}")
        shared_tags = sorted(my_tags & set(other.tags or []))
        if shared_tags:
            score += TAG_WEIGHT * len(shared_tags)
            reasons.append(" ".join(f"#{t}" for t in shared_tags))
        shared_targets = (my_targets & targets[other.pk]) - {other.pk}
        if shared_targets:
            score += LINK_WEIGHT * len(shared_targets)
            names = ", ".join(sorted(titles.get(t, "?") for t in shared_targets)[:2])
            reasons.append(f"both link to {names}")
        shared_terms = sorted(my_terms & terms(f"{other.title} {other.body}"))
        if len(shared_terms) >= 2:
            score += TERM_WEIGHT * min(len(shared_terms), TERM_CAP)
            reasons.append(f"shares {len(shared_terms)} terms: {', '.join(shared_terms[:4])}")
        if score >= MIN_SCORE:
            rows.append(
                {
                    "id": other.pk,
                    "title": other.title,
                    "score": round(score, 1),
                    "reasons": reasons,
                    "url": f"/projects/{project.slug}/notes/{other.pk}",
                }
            )
    rows.sort(key=lambda r: (-r["score"], r["title"].lower()))
    return rows[:limit]
