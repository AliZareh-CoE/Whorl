"""Project knowledge-graph builder: references + notes as nodes, citations + note-links as edges."""

from literature.models import CitationEdge, Reference
from notes.models import NoteLink
from projects.models import Project


def project_graph(project: Project) -> dict:
    nodes, links = [], []

    references = list(
        Reference.objects.filter(project_links__project=project).prefetch_related("project_links")
    )
    status_by_ref = {
        link.reference_id: link.reading_status for link in project.project_references.all()
    }
    ref_ids = set()
    for ref in references:
        ref_ids.add(ref.pk)
        nodes.append(
            {
                "id": f"ref-{ref.pk}",
                "type": "reference",
                "label": ref.bibtex_key,
                "title": ref.title,
                "group": status_by_ref.get(ref.pk, "to_read"),
                "size": min(30, 4 + (ref.citation_count or 0) ** 0.5),
                "url": ref.get_absolute_url(),
            }
        )

    notes = list(project.notes.all())
    note_ids = set()
    for note in notes:
        note_ids.add(note.pk)
        nodes.append(
            {
                "id": f"note-{note.pk}",
                "type": "note",
                "label": note.title,
                "title": note.title,
                "group": "note",
                "size": 6,
                "url": note.get_absolute_url(),
            }
        )

    for edge in CitationEdge.objects.filter(citing__in=ref_ids, cited__in=ref_ids):
        links.append(
            {
                "source": f"ref-{edge.citing_id}",
                "target": f"ref-{edge.cited_id}",
                "kind": "citation",
            }
        )
    for link in NoteLink.objects.filter(source__in=note_ids, target__in=note_ids):
        links.append(
            {
                "source": f"note-{link.source_id}",
                "target": f"note-{link.target_id}",
                "kind": "note-link",
            }
        )
    for note in notes:
        for ref in note.references.all():
            if ref.pk in ref_ids:
                links.append(
                    {
                        "source": f"note-{note.pk}",
                        "target": f"ref-{ref.pk}",
                        "kind": "note-citation",
                    }
                )

    return {"nodes": nodes, "links": links}
