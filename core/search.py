"""Global full-text search across Atlas object types (Postgres FTS)."""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

from documents.models import Document
from literature.models import Reference
from notes.models import Note
from plans.models import Milestone, Phase
from projects.models import DecisionRecord, Project

LIMIT_PER_TYPE = 10


def _ranked(queryset, vector, query):
    return (
        queryset.annotate(rank=SearchRank(vector, query))
        .filter(rank__gt=0.001)
        .order_by("-rank")[:LIMIT_PER_TYPE]
    )


def search_all(text: str) -> list[dict]:
    """Returns [{"type": ..., "object": ..., "project": ...}, ...] ranked within type."""
    if not text.strip():
        return []
    query = SearchQuery(text)
    results = []

    for project in _ranked(
        Project.objects.all(), SearchVector("name", weight="A") + SearchVector("description"), query
    ):
        results.append({"type": "project", "object": project, "project": project})

    for ref in _ranked(
        Reference.objects.all(),
        SearchVector("title", weight="A")
        + SearchVector("abstract")
        + SearchVector("venue")
        + SearchVector("bibtex_key", weight="A"),
        query,
    ):
        results.append({"type": "reference", "object": ref, "project": None})

    for note in _ranked(
        Note.objects.select_related("project"),
        SearchVector("title", weight="A") + SearchVector("body"),
        query,
    ):
        results.append({"type": "note", "object": note, "project": note.project})

    for doc in _ranked(
        Document.objects.select_related("project"),
        SearchVector("title", weight="A") + SearchVector("description"),
        query,
    ):
        results.append({"type": "document", "object": doc, "project": doc.project})

    for decision in _ranked(
        DecisionRecord.objects.select_related("project"),
        SearchVector("title", weight="A")
        + SearchVector("decision")
        + SearchVector("context")
        + SearchVector("alternatives"),
        query,
    ):
        results.append({"type": "decision", "object": decision, "project": decision.project})

    for phase in _ranked(
        Phase.objects.select_related("project"),
        SearchVector("name", weight="A") + SearchVector("objective"),
        query,
    ):
        results.append({"type": "phase", "object": phase, "project": phase.project})

    for milestone in _ranked(
        Milestone.objects.select_related("phase__project"),
        SearchVector("title", weight="A") + SearchVector("notes"),
        query,
    ):
        results.append(
            {"type": "milestone", "object": milestone, "project": milestone.phase.project}
        )

    return results
