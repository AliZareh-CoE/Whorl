import re
from urllib.parse import quote

from django.urls import reverse

from .models import Note, NoteLink

# Audit #29: the title class excludes "[" as well, so a run of "[[" cannot make the engine
# re-scan the rest of the body from every bracket (50k "[[" took 64 s; now < 1 ms)
WIKI_LINK_RE = re.compile(r"\[\[([^\[\]\n]+)\]\]")
# Pandoc-style citation keys: "@lavie2010attention" (not inside emails/urls/handles)
CITE_RE = re.compile(r"(?<![\w@/.])@([A-Za-z][\w:.-]*\w)")


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


# --- Notes v2 slice 1: citations, link panel, suggestions ------------------------------


def parse_cite_keys(body: str) -> list[str]:
    """Distinct @cite-keys in order of first appearance."""
    seen, keys = set(), []
    for match in CITE_RE.finditer(body or ""):
        key = match.group(1).rstrip(".")
        if key.lower() not in seen:
            seen.add(key.lower())
            keys.append(key)
    return keys


def sync_note_references(note: Note) -> list[str]:
    """Attach every reference cited as @key in the body (additive). Returns unknown keys."""
    from literature.models import Reference

    keys = parse_cite_keys(note.body)
    if not keys:
        return []
    found = {r.bibtex_key.lower(): r for r in Reference.objects.filter(bibtex_key__in=keys)}
    if len(found) < len(keys):  # case-insensitive second pass for the rest
        for key in keys:
            if key.lower() not in found:
                ref = Reference.objects.filter(bibtex_key__iexact=key).first()
                if ref:
                    found[key.lower()] = ref
    note.references.add(*found.values())
    return [k for k in keys if k.lower() not in found]


def note_links(note: Note) -> dict:
    """Everything the link panel shows: outgoing, backlinks, references, unresolved, mentions."""
    outgoing = [
        {"id": link.target_id, "title": link.target.title}
        for link in note.outgoing_links.select_related("target").order_by("target__title")
    ]
    backlinks = [
        {"id": link.source_id, "title": link.source.title}
        for link in note.incoming_links.select_related("source").order_by("source__title")
    ]
    references = [
        {"id": r.pk, "bibtex_key": r.bibtex_key, "title": r.title, "year": r.year}
        for r in note.references.order_by("bibtex_key")
    ]
    existing = {n.title.lower(): n for n in note.project.notes.all()}
    unresolved = [t for t in parse_wiki_titles(note.body) if t.lower() not in existing]
    from literature.models import Reference

    known = {
        r.lower()
        for r in Reference.objects.filter(bibtex_key__in=parse_cite_keys(note.body)).values_list(
            "bibtex_key", flat=True
        )
    }
    unresolved_keys = [k for k in parse_cite_keys(note.body) if k.lower() not in known]
    linked_from = {b["id"] for b in backlinks}
    needle = note.title.lower()
    mentions = [
        {"id": n.pk, "title": n.title}
        for n in note.project.notes.exclude(pk=note.pk)
        if n.pk not in linked_from and needle and needle in (n.body or "").lower()
    ]
    return {
        "outgoing": outgoing,
        "backlinks": backlinks,
        "references": references,
        "unresolved": unresolved,
        "unresolved_keys": unresolved_keys,
        "mentions": mentions,
    }


def suggest(project, q: str, kind: str = "note", limit: int = 8) -> list[dict]:
    """Autocomplete rows for [[ (notes) and @ (references filed in the project)."""
    q = (q or "").strip()
    if kind == "tag":  # #504: the project's tags, most used first
        from notes.tags import project_tags

        rows = [t for t in project_tags(project) if q.lower().lstrip("#") in t["tag"]]
        rows.sort(key=lambda t: (not t["tag"].startswith(q.lower().lstrip("#")), -t["count"]))
        return [
            {
                "id": i,
                "label": t["tag"],
                "sublabel": f"{t['count']} note{'s' if t['count'] != 1 else ''}",
            }
            for i, t in enumerate(rows[:limit])
        ]
    if kind == "reference":
        from literature.models import Reference

        refs = Reference.objects.filter(project_links__project=project)
        if q:
            from django.db.models import Q

            refs = refs.filter(Q(bibtex_key__icontains=q) | Q(title__icontains=q))
        rows = list(refs.order_by("bibtex_key")[: limit * 3])
        rows.sort(key=lambda r: (not r.bibtex_key.lower().startswith(q.lower()), r.bibtex_key))
        return [{"id": r.pk, "label": r.bibtex_key, "sublabel": r.title[:90]} for r in rows[:limit]]
    notes = project.notes.all()
    if q:
        notes = notes.filter(title__icontains=q)
    rows = list(notes.order_by("title")[: limit * 3])
    rows.sort(key=lambda n: (not n.title.lower().startswith(q.lower()), n.title.lower()))
    return [
        {
            "id": n.pk,
            "label": n.title,
            "sublabel": (n.body or "").strip().splitlines()[0][:90] if n.body.strip() else "",
        }
        for n in rows[:limit]
    ]
