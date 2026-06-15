import re
from urllib.parse import quote

from django.urls import reverse

from .models import Note, NoteLink

WIKI_LINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")


def parse_wiki_titles(body: str) -> list[str]:
    seen, titles = set(), []
    for match in WIKI_LINK_RE.finditer(body or ""):
        title = match.group(1).strip()
        key = title.lower()
        if title and key not in seen:
            seen.add(key)
            titles.append(title)
    return titles


def unwritten_note_titles(project) -> list[str]:
    """Titles referenced via [[wiki-links]] anywhere in the project's notes that don't yet
    exist as a note — the "stubs to write" list (Obsidian-style). One query; case-insensitive,
    keeping the first-seen casing. Sorted for a stable display."""
    notes = list(project.notes.all())
    existing = {n.title.lower() for n in notes}
    found: dict[str, str] = {}
    for note in notes:
        for title in parse_wiki_titles(note.body):
            key = title.lower()
            if key not in existing:
                found.setdefault(key, title)
    return sorted(found.values(), key=str.lower)


def sync_note_links(note: Note) -> list[str]:
    """Rebuild NoteLinks from [[wiki-links]] in the body. Returns unresolved titles."""
    titles = parse_wiki_titles(note.body)
    targets, unresolved = [], []
    for title in titles:
        target = Note.objects.filter(project=note.project, title__iexact=title).first()
        if target and target != note:
            targets.append(target)
        elif not target:
            unresolved.append(title)
    note.outgoing_links.all().delete()
    NoteLink.objects.bulk_create(NoteLink(source=note, target=t) for t in targets)
    return unresolved


def body_with_resolved_links(note: Note) -> str:
    """Replace [[Title]] with markdown links for notes that exist in the project."""
    by_title = {n.title.lower(): n for n in note.project.notes.all()}

    create_url = reverse("notes:create", kwargs={"slug": note.project.slug})

    def replace(match):
        title = match.group(1).strip()
        target = by_title.get(title.lower())
        if target and target != note:
            return f"[{title}]({target.get_absolute_url()})"
        # unresolved → a "+ Title" link that opens the create form pre-filled (Obsidian-style),
        # so a [[link]] to a not-yet-written note is one click from existing.
        return f"[+ {title}]({create_url}?title={quote(title)})"

    return WIKI_LINK_RE.sub(replace, note.body or "")


def add_highlight_note(reference, project, text: str, page: int | None = None) -> Note:
    """Append a PDF highlight to the reference's per-project highlights note."""
    title = f"Highlights — {reference.bibtex_key}"
    note = Note.objects.filter(project=project, title__iexact=title).first()
    if note is None:
        note = Note.objects.create(project=project, title=title, body="")
    quoted = "\n".join(f"> {line}" for line in text.strip().splitlines())
    page_part = f", p.{page}" if page else ""
    note.body = (note.body + f"\n\n{quoted}\n> — {reference.bibtex_key}{page_part}").strip()
    note.save()
    note.references.add(reference)
    sync_note_links(note)
    return note
