"""Note templates and Markdown export (Notes v2 slice 3).

Templates are plain Markdown with the project's data filled in: a literature note carries the
paper's metadata, its @key and every highlight already taken; a daily note starts with this
week's focus from the plan. Export renders a note as portable Markdown with a formatted
bibliography for every @key / attached reference.
"""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from .models import Note

TEMPLATES = {
    "blank": {"label": "Blank", "description": "An empty page."},
    "literature": {
        "label": "Literature note",
        "description": "One paper: claims, method, limitations, relevance — with its highlights.",
    },
    "daily": {"label": "Daily note", "description": "Today: this week's focus, a log, captures."},
    "meeting": {"label": "Meeting", "description": "Attendees, agenda, decisions, actions."},
    "experiment": {
        "label": "Experiment",
        "description": "Hypothesis, setup, observations, result, next step.",
    },
}


def _unique_title(project, title: str) -> str:
    base, n = title, 2
    while project.notes.filter(title__iexact=title).exists():
        title = f"{base} ({n})"
        n += 1
    return title


def _literature(reference, project) -> tuple[str, str]:
    from literature.models import Highlight

    first = (reference.authors or [{}])[0]
    family = first.get("family") or first.get("given") or "Anon"
    title = f"{family} {reference.year or 'n.d.'} — {reference.title[:70]}".strip()
    meta = " · ".join(
        str(x)
        for x in (reference.author_names or "Unknown authors", reference.year, reference.venue)
        if x
    )
    lines = [
        f"@{reference.bibtex_key}",
        "",
        f"*{meta}*" + (f" · [doi](https://doi.org/{reference.doi})" if reference.doi else ""),
        "",
        "## In one sentence",
        "",
        "",
        "## Claims",
        "",
        "- ",
        "",
        "## Method",
        "",
        "",
        "## Limitations",
        "",
        "",
        "## Why it matters for this project",
        "",
        "",
    ]
    highlights = list(
        Highlight.objects.filter(reference=reference)
        .filter(project=project)
        .order_by("page", "created_at")
    ) or list(Highlight.objects.filter(reference=reference).order_by("page", "created_at"))
    if highlights:
        lines += ["## Highlights", ""]
        for h in highlights:
            quoted = "\n".join(f"> {line}" for line in h.text.splitlines())
            where = f" (p.{h.page})" if h.page else ""
            lines.append(f"{quoted}\n> —{where}")
            if h.comment:
                lines.append(f"\n{h.comment}")
            lines.append("")
    hl_note = project.notes.filter(title__iexact=f"Highlights — {reference.bibtex_key}").first()
    if hl_note:
        lines += [f"See also [[{hl_note.title}]].", ""]
    return title, "\n".join(lines).rstrip() + "\n"


def _daily(project, today: date) -> tuple[str, str]:
    from plans.focus import week_focus

    focus = week_focus(project, today)
    lines = [f"# {today.strftime('%A, %d %B %Y')}", "", "## Focus", ""]
    items = focus["overdue"] + focus["due_this_week"] + focus["next_up"]
    if items:
        for i in items[:8]:
            when = ""
            if i["days"] is not None:
                when = (
                    f" — {-i['days']} d late"
                    if i["days"] < 0
                    else " — today"
                    if i["days"] == 0
                    else f" — in {i['days']} d"
                )
            lines.append(f"- [ ] {i['title']}{when}")
    else:
        lines.append("- [ ] ")
    lines += ["", "## Log", "", "- ", "", "## Captured", "", ""]
    return today.isoformat(), "\n".join(lines)


def render_template(
    kind: str, project, *, reference=None, today: date | None = None
) -> tuple[str, str]:
    """(title, body) for a template kind. Literature needs a reference."""
    today = today or timezone.localdate()
    if kind not in TEMPLATES:
        raise ValueError(f"unknown template '{kind}' (one of {', '.join(TEMPLATES)})")
    if kind == "literature":
        if reference is None:
            raise ValueError("a literature note needs a reference")
        return _literature(reference, project)
    if kind == "daily":
        return _daily(project, today)
    if kind == "meeting":
        return (
            f"Meeting — {today.isoformat()}",
            "## Attendees\n\n- \n\n## Agenda\n\n1. \n\n## Decisions\n\n- \n\n## Actions\n\n- [ ] \n",
        )
    if kind == "experiment":
        return (
            f"Experiment — {today.isoformat()}",
            "## Hypothesis\n\n\n## Setup\n\n\n## Observations\n\n- \n\n## Result\n\n\n## Next\n\n- [ ] \n",
        )
    return "Untitled", ""


def create_from_template(kind: str, project, *, reference=None, today: date | None = None) -> Note:
    """Create (or, for a daily note, return today's existing) note from a template."""
    from .services import sync_note_links, sync_note_references

    title, body = render_template(kind, project, reference=reference, today=today)
    if kind == "daily":
        existing = project.notes.filter(title=title).first()
        if existing:
            return existing
    note = Note.objects.create(project=project, title=_unique_title(project, title), body=body)
    sync_note_links(note)
    sync_note_references(note)
    if reference is not None:
        note.references.add(reference)
    return note


def export_note(note: Note, style: str = "apa") -> dict:
    """Portable Markdown: the body as written plus a formatted bibliography of its references."""
    from literature.citations import STYLES, bibliography

    if style not in STYLES:
        style = "apa"
    refs = list(note.references.order_by("bibtex_key"))
    out = [f"# {note.title}", "", note.body.rstrip(), ""]
    if refs:
        bib = bibliography(refs, style)
        out += ["", "## References", ""]
        for entry in bib["entries"]:
            text = entry["text"] if isinstance(entry, dict) else str(entry)
            out.append(f"- {text}")
        out.append("")
    return {"markdown": "\n".join(out).rstrip() + "\n", "style": style, "references": len(refs)}
