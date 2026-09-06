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
from plans.models import Milestone, Phase, ResearchQuestion
from projects.models import DecisionRecord, Project
from research.models import ExperimentEntry, Hypothesis
from writing.models import Manuscript

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


# The fields each type matches on, shared by the FTS vectors above and the icontains
# fallback below. (kind, queryset-factory, fields, project-accessor).
_SEARCH_SPECS = [
    ("project", lambda: Project.objects.all(), ["name", "description"], lambda o: o),
    (
        "reference",
        lambda: Reference.objects.all(),
        ["title", "abstract", "venue", "bibtex_key", "text__body"],
        lambda o: None,
    ),
    (
        "note",
        lambda: Note.objects.select_related("project"),
        ["title", "body"],
        lambda o: o.project,
    ),
    (
        "document",
        lambda: Document.objects.select_related("project"),
        ["title", "description"],
        lambda o: o.project,
    ),
    (
        "decision",
        lambda: DecisionRecord.objects.select_related("project"),
        ["title", "decision", "context", "alternatives"],
        lambda o: o.project,
    ),
    (
        "phase",
        lambda: Phase.objects.select_related("project"),
        ["name", "objective"],
        lambda o: o.project,
    ),
    (
        "milestone",
        lambda: Milestone.objects.select_related("phase__project"),
        ["title", "notes"],
        lambda o: o.phase.project,
    ),
    (
        "manuscript",
        lambda: Manuscript.objects.select_related("project"),
        ["title", "abstract"],
        lambda o: o.project,
    ),
    (
        "hypothesis",
        lambda: Hypothesis.objects.select_related("project"),
        ["statement"],
        lambda o: o.project,
    ),
    (
        "question",
        lambda: ResearchQuestion.objects.select_related("project"),
        ["question"],
        lambda o: o.project,
    ),
    (
        "experiment",
        lambda: ExperimentEntry.objects.select_related("project"),
        ["title", "body"],
        lambda o: o.project,
    ),
]


def _icontains_search(text: str) -> list[dict]:
    """Plain LIKE search for non-Postgres backends (the SQLite desktop build, #210b).

    No ranking or typo-tolerance — just case-insensitive substring matches over the same
    fields the FTS path uses — so global search still works without Postgres.
    """
    from django.db.models import Q

    results = []
    for kind, qs_factory, fields, project_of in _SEARCH_SPECS:
        condition = Q()
        for field in fields:
            condition |= Q(**{f"{field}__icontains": text})
        for obj in qs_factory().filter(condition)[:LIMIT_PER_TYPE]:
            results.append({"type": kind, "object": obj, "project": project_of(obj)})
    return results


def search_all(text: str) -> list[dict]:
    """Returns [{"type": ..., "object": ..., "project": ...}, ...] ranked within type."""
    if not text.strip():
        return []
    from django.db import connection

    if connection.vendor != "postgresql":
        return _icontains_search(text.strip())
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
        + SearchVector("bibtex_key", weight="A")
        + SearchVector("text__body", weight="D"),  # slice 8: inside the PDF too
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

    for manuscript in _ranked(
        Manuscript.objects.select_related("project"),
        SearchVector("title", weight="A") + SearchVector("abstract"),
        query,
    ):
        results.append({"type": "manuscript", "object": manuscript, "project": manuscript.project})

    for hypothesis in _ranked(
        Hypothesis.objects.select_related("project"),
        SearchVector("statement", weight="A"),
        query,
    ):
        results.append({"type": "hypothesis", "object": hypothesis, "project": hypothesis.project})

    for question in _ranked(
        ResearchQuestion.objects.select_related("project"),
        SearchVector("question", weight="A"),
        query,
    ):
        results.append({"type": "question", "object": question, "project": question.project})

    for experiment in _ranked(
        ExperimentEntry.objects.select_related("project"),
        SearchVector("title", weight="A") + SearchVector("body"),
        query,
    ):
        results.append({"type": "experiment", "object": experiment, "project": experiment.project})

    if not results:
        results = _trigram_fallback(text.strip())

    return results
