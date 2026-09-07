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
from notes.models import Note, QuickCapture
from plans.models import Milestone, Phase, ResearchQuestion
from projects.models import DecisionRecord, Project
from research.models import Dataset, ExperimentEntry, Hypothesis, Protocol
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
    # #428: the three kinds search had skipped
    (
        "dataset",
        lambda: Dataset.objects.select_related("project"),
        ["name", "location", "description"],
        lambda o: o.project,
    ),
    (
        "protocol",
        lambda: Protocol.objects.select_related("project"),
        ["title", "body"],
        lambda o: o.project,
    ),
    (
        "capture",
        lambda: QuickCapture.objects.select_related("project"),
        ["text"],
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

    # #428: datasets, protocols and inbox captures
    for dataset in _ranked(
        Dataset.objects.select_related("project"),
        SearchVector("name", weight="A") + SearchVector("location") + SearchVector("description"),
        query,
    ):
        results.append({"type": "dataset", "object": dataset, "project": dataset.project})

    for protocol in _ranked(
        Protocol.objects.select_related("project"),
        SearchVector("title", weight="A") + SearchVector("body"),
        query,
    ):
        results.append({"type": "protocol", "object": protocol, "project": protocol.project})

    for capture in _ranked(
        QuickCapture.objects.select_related("project"), SearchVector("text", weight="A"), query
    ):
        results.append({"type": "capture", "object": capture, "project": capture.project})

    if not results:
        results = _trigram_fallback(text.strip())

    return results


# --- Search v2 (2026-09-06): explain each hit — snippet, page, SPA link, meta ---------------

EXCERPT_RADIUS = 80


def excerpt(text: str, q: str, radius: int = EXCERPT_RADIUS) -> str:
    """A short window of `text` around the first term of `q` (or the start when absent)."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    terms = [t.strip('"') for t in q.split() if t.strip('"') and not t.startswith("-")]
    low = text.lower()
    pos = -1
    for term in terms:
        pos = low.find(term.lower())
        if pos >= 0:
            break
    if pos < 0:
        return text[: radius * 2] + ("…" if len(text) > radius * 2 else "")
    lo, hi = max(0, pos - radius), min(len(text), pos + radius)
    return ("…" if lo > 0 else "") + text[lo:hi] + ("…" if hi < len(text) else "")


def describe(result: dict, q: str) -> dict:
    """Snippet / page / app_url / meta for one search_all() row."""
    kind, obj, project = result["type"], result["object"], result["project"]
    slug = project.slug if project else None
    out = {"snippet": "", "page": None, "app_url": None, "meta": "", "where": ""}
    if kind == "reference":
        from literature.fulltext import search_pages

        hits = search_pages(obj, q.strip('"'), limit=1) if q.strip() else []
        authors = ", ".join(
            a.get("family") or a.get("given") or "" for a in (obj.authors or [])[:3]
        )
        out["meta"] = " · ".join(str(x) for x in (authors, obj.year, obj.venue) if x)
        out["app_url"] = f"/references/{obj.pk}"
        if hits:
            out.update(snippet=hits[0]["snippet"], page=hits[0]["page"], where="in the PDF")
        else:
            out["snippet"] = excerpt(obj.abstract, q)
    elif kind == "note":
        out.update(
            snippet=excerpt(obj.body, q),
            app_url=f"/projects/{slug}/notes/{obj.pk}",
            meta=obj.updated_at.date().isoformat(),
        )
    elif kind == "project":
        out.update(
            snippet=excerpt(obj.description, q), app_url=f"/projects/{obj.slug}", meta=obj.status
        )
    elif kind == "document":
        out.update(
            snippet=excerpt(obj.description, q),
            app_url=f"/projects/{slug}/files",
            meta=obj.created_at.date().isoformat(),
        )
    elif kind == "decision":
        out.update(
            snippet=excerpt(obj.decision or obj.context, q),
            app_url=f"/projects/{slug}/decisions",
            meta=obj.decided_on.isoformat(),
        )
    elif kind == "phase":
        out.update(
            snippet=excerpt(obj.objective, q),
            app_url=f"/projects/{slug}/plan",
            meta=obj.status.replace("_", " "),
        )
    elif kind == "milestone":
        out.update(
            snippet=excerpt(obj.notes, q),
            app_url=f"/projects/{slug}/plan",
            meta=(f"due {obj.due_date}" if obj.due_date else ""),
        )
    elif kind == "manuscript":
        out.update(
            snippet=excerpt(obj.abstract, q),
            app_url=f"/manuscripts/{obj.pk}",
            meta=obj.status.replace("_", " "),
        )
    elif kind == "protocol":
        out.update(
            snippet=excerpt(obj.body, q),
            app_url=f"/projects/{slug}/research",
            meta=f"v{obj.version}" + ("" if obj.is_current else " (superseded)"),
        )
    elif kind == "capture":
        out.update(
            snippet=excerpt(obj.text, q),
            app_url="/inbox",
            meta="filed" if obj.processed else "in the inbox",
        )
    elif kind in ("hypothesis", "experiment", "dataset", "question"):
        body = (
            getattr(obj, "statement", "")
            or getattr(obj, "body", "")
            or getattr(obj, "description", "")
            or getattr(obj, "question", "")
        )
        out.update(
            snippet=excerpt(body, q),
            app_url=f"/projects/{slug}/research",
            meta=getattr(obj, "status", "") or "",
        )
    return out
