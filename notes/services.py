import re

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

    def replace(match):
        title = match.group(1).strip()
        target = by_title.get(title.lower())
        if target and target != note:
            return f"[{title}]({target.get_absolute_url()})"
        return f"*[[{title}]]*"

    return WIKI_LINK_RE.sub(replace, note.body or "")
