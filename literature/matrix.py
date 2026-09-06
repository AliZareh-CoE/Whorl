"""Literature review matrix v2 (Elicit-style extraction table).

Rows are the project's papers, columns its review themes; a cell is a `ReviewMark` (present =
covered, with an optional short note — the extracted finding). Claude fills cells through the
same functions via MCP, so a matrix can be drafted from the PDFs and corrected by hand.
"""

from __future__ import annotations

from .models import ProjectReference, Reference, ReviewMark, ReviewTheme

NOTE_MAX = 300


def add_theme(project, name: str, order: int | None = None) -> ReviewTheme:
    name = " ".join((name or "").split())[:120]
    if not name:
        raise ValueError("a theme needs a name")
    existing = project.review_themes.filter(name__iexact=name).first()
    if existing:
        return existing
    if order is None:
        last = project.review_themes.order_by("-order").values_list("order", flat=True).first()
        order = (last or 0) + 1
    return ReviewTheme.objects.create(project=project, name=name, order=order)


def resolve_theme(project, theme) -> ReviewTheme:
    """A theme by id, name (created when missing), or instance."""
    if isinstance(theme, ReviewTheme):
        return theme
    if isinstance(theme, int) or (isinstance(theme, str) and theme.isdigit()):
        found = project.review_themes.filter(pk=int(theme)).first()
        if found:
            return found
    return add_theme(project, str(theme))


def set_mark(project, reference, theme, *, marked: bool = True, note: str | None = None) -> dict:
    """Create / update / remove one cell. `reference` is a Reference, id, or bibtex key."""
    if isinstance(reference, Reference):
        ref = reference
    elif isinstance(reference, int) or (isinstance(reference, str) and reference.isdigit()):
        ref = Reference.objects.filter(pk=int(reference)).first()
    else:
        ref = Reference.objects.filter(bibtex_key__iexact=str(reference)).first()
    if ref is None:
        raise ValueError("unknown reference")
    link = ProjectReference.objects.filter(project=project, reference=ref).first()
    if link is None:
        raise ValueError("that paper is not filed in this project")
    theme_obj = resolve_theme(project, theme)
    if not marked:
        ReviewMark.objects.filter(theme=theme_obj, project_reference=link).delete()
        return {"reference_id": ref.pk, "theme_id": theme_obj.pk, "marked": False, "note": ""}
    mark, _ = ReviewMark.objects.get_or_create(theme=theme_obj, project_reference=link)
    if note is not None:
        mark.note = note.strip()[:NOTE_MAX]
        mark.save(update_fields=["note", "updated_at"])
    return {
        "reference_id": ref.pk,
        "theme_id": theme_obj.pk,
        "theme": theme_obj.name,
        "marked": True,
        "note": mark.note,
        "mark_id": mark.pk,
    }


def matrix(project) -> dict:
    """The whole table: themes (with coverage), rows (papers with cells keyed by theme id)."""
    themes = list(project.review_themes.order_by("order", "pk"))
    links = list(
        project.project_references.select_related("reference").order_by(
            "reference__year", "reference__bibtex_key"
        )
    )
    marks = {
        (m.theme_id, m.project_reference_id): m
        for m in ReviewMark.objects.filter(theme__project=project)
    }
    rows = []
    for link in links:
        ref = link.reference
        cells = {}
        for t in themes:
            m = marks.get((t.pk, link.pk))
            if m:
                cells[str(t.pk)] = {"mark_id": m.pk, "note": m.note}
        rows.append(
            {
                "link_id": link.pk,
                "reference_id": ref.pk,
                "bibtex_key": ref.bibtex_key,
                "title": ref.title,
                "year": ref.year,
                "authors": ", ".join(
                    a.get("family") or a.get("given") or "" for a in (ref.authors or [])[:2]
                ),
                "reading_status": link.reading_status,
                "has_pdf": bool(ref.pdf),
                "cells": cells,
                "covered": len(cells),
            }
        )
    total = len(links)
    theme_rows = [
        {
            "id": t.pk,
            "name": t.name,
            "order": t.order,
            "covered": sum(1 for r in rows if str(t.pk) in r["cells"]),
            "total": total,
        }
        for t in themes
    ]
    return {
        "project": project.slug,
        "themes": theme_rows,
        "rows": rows,
        "papers": total,
        "unmarked": sum(1 for r in rows if r["covered"] == 0),
    }


def matrix_markdown(project) -> str:
    data = matrix(project)
    if not data["themes"]:
        return "| Paper |\n|---|\n" + "\n".join(f"| {r['bibtex_key']} |" for r in data["rows"])
    head = "| Paper | " + " | ".join(t["name"] for t in data["themes"]) + " |"
    sep = "|---" * (len(data["themes"]) + 1) + "|"
    lines = [head, sep]
    for r in data["rows"]:
        cells = []
        for t in data["themes"]:
            c = r["cells"].get(str(t["id"]))
            cells.append((c["note"] or "✓") if c else "")
        lines.append(f"| {r['bibtex_key']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
