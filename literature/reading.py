"""Reading layer for the Library workbench (Library v2 slice 7).

Highlights are structured rows (page, text, comment, colour) rather than lines appended to a
note, so the workbench can list, jump to, edit, and export them. When a project is given the
passage is also mirrored into that project's "Highlights — <key>" note (the older flow), keeping
highlights reachable from the note graph.
"""

from __future__ import annotations

from django.db import transaction

from .models import Highlight, ProjectReference, Reference

MAX_HIGHLIGHT_CHARS = 2000


class HighlightError(ValueError):
    """A highlight could not be saved (empty, too long, project not linked)."""


@transaction.atomic
def add_highlight(
    reference: Reference,
    text: str,
    *,
    page: int | None = None,
    project=None,
    comment: str = "",
    color: str = Highlight.Color.YELLOW,
    mirror_to_note: bool = True,
    rects: list | None = None,
) -> Highlight:
    """Save a highlight; optionally mirror it into the project's highlights note."""
    from notes.services import add_highlight_note

    text = text.strip()
    if not text:
        raise HighlightError("Empty selection.")
    if len(text) > MAX_HIGHLIGHT_CHARS:
        raise HighlightError(
            f"Selection too long — highlight at most {MAX_HIGHLIGHT_CHARS} characters."
        )
    if color not in Highlight.Color.values:
        color = Highlight.Color.YELLOW
    if (
        project is not None
        and not ProjectReference.objects.filter(project=project, reference=reference).exists()
    ):
        raise HighlightError("Link this reference to the project before saving highlights to it.")
    highlight = Highlight.objects.create(
        reference=reference,
        project=project,
        page=page,
        text=text,
        comment=comment.strip(),
        color=color,
        rects=rects or [],
    )
    if project is not None and mirror_to_note:
        add_highlight_note(reference, project, text, page)
    # a highlighted paper is at least skimmed everywhere it is filed (per-row saves so #523's
    # started_at stamp lands; a paper is filed in one or two projects, never hundreds)
    for link in ProjectReference.objects.filter(
        reference=reference, reading_status=ProjectReference.ReadingStatus.TO_READ
    ):
        link.reading_status = ProjectReference.ReadingStatus.SKIMMED
        link.save(update_fields=["reading_status", "updated_at"])
    return highlight


def highlights_markdown(reference: Reference) -> str:
    """All highlights of a paper as a Markdown block (for copy / export / MCP)."""
    lines = [f"## Highlights — {reference.title}", ""]
    for h in reference.highlights.select_related("project"):
        quoted = "\n".join(f"> {line}" for line in h.text.splitlines())
        where = f", p.{h.page}" if h.page else ""
        lines.append(f"{quoted}\n> — {reference.bibtex_key}{where}")
        if h.comment:
            lines.append(f"\n{h.comment}")
        lines.append("")
    if reference.highlights.count() == 0:
        lines.append("_No highlights yet._")
    return "\n".join(lines).strip() + "\n"


def reading_notes(reference: Reference) -> list[dict]:
    """Per-project reading notes for a paper (the ProjectReference.notes field)."""
    return [
        {
            "project_reference_id": link.pk,
            "project": link.project.slug,
            "project_name": link.project.name,
            "reading_status": link.reading_status,
            "notes": link.notes,
        }
        for link in reference.project_links.select_related("project").order_by("project__position")
    ]
