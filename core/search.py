"""Global full-text search across Atlas object types.

Postgres FTS with `websearch` query parsing ("quoted phrases", OR, -negation),
plus a trigram-similarity fallback so typos still find things.
"""

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
)

from documents.models import Document
from literature.models import Reference
from notes.models import Note
from plans.models import Milestone, Phase
from projects.models import DecisionRecord, Project

LIMIT_PER_TYPE = 10


def _ranked(queryset, vector, query):
    # filter on the actual boolean match; rank only orders (ts_rank ignores ! and &)
    return (
        queryset.annotate(search=vector, rank=SearchRank(vector, query))
        .filter(search=query)
        .order_by("-rank")[:LIMIT_PER_TYPE]
    )


TRIGRAM_FIELDS = {
    "project": ("name", lambda obj: obj),
    "reference": ("title", lambda obj: None),
    "note": ("title", lambda obj: obj.project),
    "document": ("title", lambda obj: obj.project),
    "decision": ("title", lambda obj: obj.project),
}


def _trigram_fallback(text: str) -> list[dict]:
    """Typo-tolerant rescue pass over the main title fields."""
    from documents.models import Document as Doc

    model_map = {
        "project": Project.objects.all(),
        "reference": Reference.objects.all(),
        "note": Note.objects.select_related("project"),
        "document": Doc.objects.select_related("project"),
        "decision": DecisionRecord.objects.select_related("project"),
    }
    results = []
    for kind, queryset in model_map.items():
        field, project_of = TRIGRAM_FIELDS[kind]
        # __trigram_similar compiles to the % operator, which the GIN trgm indexes serve;
        # similarity() > x alone would force a sequential scan
        matches = (
            queryset.filter(**{f"{field}__trigram_similar": text})
            .annotate(sim=TrigramSimilarity(field, text))
            .order_by("-sim")[:5]
        )
        for obj in matches:
            results.append({"type": kind, "object": obj, "project": project_of(obj)})
    return results


def search_all(text: str) -> list[dict]:
    """Returns [{"type": ..., "object": ..., "project": ...}, ...] ranked within type."""
    if not text.strip():
        return []
    query = SearchQuery(text, search_type="websearch")
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

    if not results:
        results = _trigram_fallback(text.strip())

    return results
