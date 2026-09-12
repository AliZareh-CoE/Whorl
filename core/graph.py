"""Project knowledge-graph builder (Graph v2): references + notes as nodes, citations,
note-links and note→paper citations as edges, plus per-node facts the side panel shows and
whole-graph stats for the toolbar."""

from collections import Counter

from literature.models import CitationEdge, Highlight, Reference
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
    highlight_counts = Counter(
        Highlight.objects.filter(reference__in=[r.pk for r in references]).values_list(
            "reference_id", flat=True
        )
    )
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
                "year": ref.year,
                "venue": ref.venue,
                "citations": ref.citation_count,
                "authors": ", ".join(
                    a.get("family") or a.get("given") or "" for a in (ref.authors or [])[:3]
                ),
                "has_pdf": bool(ref.pdf),
                "highlights": highlight_counts.get(ref.pk, 0),
                "app_url": f"/references/{ref.pk}",
            }
        )

    notes = list(project.notes.all())
    note_ids = set()
    for note in notes:
        note_ids.add(note.pk)
        words = len((note.body or "").split())
        nodes.append(
            {
                "id": f"note-{note.pk}",
                "type": "note",
                "label": note.title,
                "title": note.title,
                "group": "note",
                "size": min(12, 4 + words**0.5 / 4),
                "url": note.get_absolute_url(),
                "words": words,
                "updated_at": note.updated_at.date().isoformat(),
                "app_url": f"/projects/{project.slug}/notes/{note.pk}",
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

    degree: Counter = Counter()
    for link in links:
        degree[link["source"]] += 1
        degree[link["target"]] += 1
    for node in nodes:
        node["degree"] = degree.get(node["id"], 0)
    hubs = sorted(nodes, key=lambda n: (-n["degree"], n["label"]))[:5]
    stats = {
        "references": len(ref_ids),
        "notes": len(note_ids),
        "links": len(links),
        "by_kind": dict(Counter(link["kind"] for link in links)),
        "orphans": sum(1 for n in nodes if n["degree"] == 0),
        "hubs": [
            {"id": n["id"], "label": n["label"], "degree": n["degree"]} for n in hubs if n["degree"]
        ],
    }
    return {"nodes": nodes, "links": links, "stats": stats}
