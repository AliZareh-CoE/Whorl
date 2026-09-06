"""Library v2 query layer: facets, filters, bulk actions, and metadata recovery.

Pure-ish functions over querysets so the API stays thin and everything is unit-testable.
"""

from __future__ import annotations

import re

import httpx
from django.db.models import Count, Q, QuerySet

from projects.models import Project

from .models import LibraryTag, ProjectReference, Reference, SavedView
from .services import (
    TIMEOUT,
    USER_AGENT,
    MetadataError,
    _crossref_to_meta,
    _normalize_title,
    fetch_metadata_by_arxiv,
    fetch_metadata_by_doi,
)


def _ordering(sort: str) -> list:
    """Ordering expressions per sort key; NULL years/citations always sink to the bottom."""
    from django.db.models import F

    return {
        "added": ["-created_at"],
        "-added": ["created_at"],
        "year": [F("year").desc(nulls_last=True)],
        "-year": [F("year").asc(nulls_last=True)],
        "title": ["title"],
        "-title": ["-title"],
        "citations": [F("citation_count").desc(nulls_last=True)],
    }.get(sort, ["-created_at"])


def filter_references(qs: QuerySet, params) -> QuerySet:
    """Apply the Library workbench filters from a query-params mapping."""
    q = (params.get("q") or "").strip()[:200]
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(venue__icontains=q)
            | Q(bibtex_key__icontains=q)
            | Q(abstract__icontains=q)
            | Q(authors__icontains=q)
            | Q(doi__icontains=q)
        )
    year = params.get("year")
    if year and year.isdigit():
        qs = qs.filter(year=int(year))
    for key, lookup in (("year_min", "year__gte"), ("year_max", "year__lte")):
        value = params.get(key)
        if value and value.isdigit():
            qs = qs.filter(**{lookup: int(value)})
    entry_type = params.get("entry_type")
    if entry_type:
        qs = qs.filter(entry_type=entry_type)
    venue = params.get("venue")
    if venue:
        qs = qs.filter(venue=venue)
    has_pdf = params.get("has_pdf")
    if has_pdf in ("true", "1"):
        qs = qs.exclude(pdf="").exclude(pdf__isnull=True)
    elif has_pdf in ("false", "0"):
        qs = qs.filter(Q(pdf="") | Q(pdf__isnull=True))
    needs = params.get("needs_metadata")
    if needs in ("true", "1"):
        qs = qs.filter(extra__needs_metadata=True)
    project = params.get("project")
    if project:
        qs = qs.filter(project_links__project__slug=project)
    status = params.get("reading_status")
    if status and project:
        qs = qs.filter(project_links__project__slug=project, project_links__reading_status=status)
    tag = params.get("tag")
    if tag:
        qs = qs.filter(tags__name__iexact=tag)
    untagged = params.get("untagged")
    if untagged in ("true", "1"):
        qs = qs.filter(tags__isnull=True)
    unfiled = params.get("unfiled")
    if unfiled in ("true", "1"):
        qs = qs.filter(project_links__isnull=True)
    qs = qs.order_by(*_ordering(params.get("sort") or "added"), "-id")
    return qs.distinct()


def facets(qs: QuerySet) -> dict:
    """Counts that drive the left rail — computed on the *unfiltered* base so the rail always
    shows the whole shape of the library (like a good faceted search does)."""
    years = [
        {"year": row["year"], "count": row["n"]}
        for row in qs.exclude(year__isnull=True)
        .values("year")
        .annotate(n=Count("id"))
        .order_by("year")
    ]
    types = [
        {"entry_type": row["entry_type"], "count": row["n"]}
        for row in qs.values("entry_type").annotate(n=Count("id")).order_by("-n")
    ]
    venues = [
        {"venue": row["venue"], "count": row["n"]}
        for row in qs.exclude(venue="")
        .values("venue")
        .annotate(n=Count("id"))
        .order_by("-n", "venue")[:10]
    ]
    projects = [
        {
            "slug": row["project_links__project__slug"],
            "name": row["project_links__project__name"],
            "count": row["n"],
        }
        for row in qs.exclude(project_links__isnull=True)
        .values("project_links__project__slug", "project_links__project__name")
        .annotate(n=Count("id", distinct=True))
        .order_by("-n")
    ]
    tags = [
        {"name": row["tags__name"], "color": row["tags__color"], "count": row["n"]}
        for row in qs.exclude(tags__isnull=True)
        .values("tags__name", "tags__color")
        .annotate(n=Count("id", distinct=True))
        .order_by("-n", "tags__name")
    ]
    total = qs.count()
    with_pdf = qs.exclude(pdf="").exclude(pdf__isnull=True).count()
    return {
        "total": total,
        "with_pdf": with_pdf,
        "without_pdf": total - with_pdf,
        "needs_metadata": qs.filter(extra__needs_metadata=True).count(),
        "unfiled": qs.filter(project_links__isnull=True).count(),
        "untagged": qs.filter(tags__isnull=True).count(),
        "tags": tags,
        "views": list(SavedView.objects.values("id", "name", "params", "position")),
        "years": years,
        "entry_types": types,
        "venues": venues,
        "projects": projects,
        "all_projects": list(
            Project.objects.order_by("position", "name").values("slug", "name", "color")
        ),
    }


BULK_ACTIONS = (
    "link",
    "unlink",
    "status",
    "priority",
    "delete",
    "find_metadata",
    "fetch_pdf",
    "tag",
    "untag",
)


def bulk(
    ids: list[int], action: str, project_slug: str | None = None, value: str | None = None
) -> dict:
    """Apply one action to many references. Returns {affected, action, errors}."""
    if action not in BULK_ACTIONS:
        raise ValueError(f"Unknown bulk action '{action}'")
    refs = Reference.objects.filter(pk__in=ids)
    project = Project.objects.filter(slug=project_slug).first() if project_slug else None
    if action in ("link", "unlink", "status", "priority") and project is None:
        raise ValueError(f"'{action}' needs a project slug")
    affected = 0
    errors: list[str] = []
    if action == "link":
        for ref in refs:
            _, created = ProjectReference.objects.get_or_create(project=project, reference=ref)
            affected += int(created)
    elif action == "unlink":
        affected, _ = ProjectReference.objects.filter(project=project, reference__in=refs).delete()
    elif action in ("status", "priority"):
        field = "reading_status" if action == "status" else "priority"
        choices = {
            c
            for c, _ in (
                ProjectReference.ReadingStatus if action == "status" else ProjectReference.Priority
            ).choices
        }
        if value not in choices:
            raise ValueError(f"'{value}' is not a valid {field}")
        for link in ProjectReference.objects.filter(project=project, reference__in=refs):
            setattr(link, field, value)
            link.save(update_fields=[field, "updated_at"])  # per-row keeps updated_at honest
            affected += 1
    elif action == "delete":
        affected, _ = refs.delete()
    elif action in ("tag", "untag"):
        if not (value or "").strip():
            raise ValueError("'tag' / 'untag' need the tag name in value")
        if action == "tag":
            tag = LibraryTag.get_or_create_named(value)
            for ref in refs:
                if not ref.tags.filter(pk=tag.pk).exists():
                    ref.tags.add(tag)
                    affected += 1
        else:
            tag = LibraryTag.objects.filter(name__iexact=value.strip()).first()
            if tag:
                for ref in refs.filter(tags=tag):
                    ref.tags.remove(tag)
                    affected += 1
    elif action == "fetch_pdf":
        from .tasks import fetch_oa_pdf_task

        for ref in refs.filter(Q(pdf="") | Q(pdf__isnull=True)):
            fetch_oa_pdf_task(ref.pk)  # queued (worker) or immediate (desktop/dev)
            affected += 1
    elif action == "find_metadata":
        for ref in refs:
            try:
                if find_metadata(ref):
                    affected += 1
            except MetadataError as exc:
                errors.append(f"{ref.title[:60]}: {exc}")
    return {"action": action, "affected": affected, "errors": errors}


def _similar(a: str, b: str) -> float:
    """Cheap title similarity: shared-token Jaccard on normalised words."""
    ta = set(re.findall(r"[a-z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def search_crossref_by_title(title: str, client: httpx.Client | None = None) -> dict | None:
    """Best Crossref match for a title, or None when nothing is close enough."""
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    try:
        response = client.get(
            "https://api.crossref.org/works", params={"query.title": title[:300], "rows": 3}
        )
        if response.status_code != 200:
            return None
        items = response.json().get("message", {}).get("items", [])
    except (httpx.HTTPError, ValueError):
        return None
    finally:
        if own:
            client.close()
    for work in items:
        candidate = " ".join(work.get("title") or [])
        if _similar(candidate, title) >= 0.6 or _normalize_title(candidate) == _normalize_title(
            title
        ):
            return _crossref_to_meta(work)
    return None


def find_metadata(reference: Reference, client: httpx.Client | None = None) -> bool:
    """Recover real metadata for a stub (or refresh any reference): by DOI, by arXiv id, else
    by a Crossref title search. Returns True when the reference was updated."""
    meta = None
    if reference.doi:
        meta = fetch_metadata_by_doi(reference.doi)
    elif reference.arxiv_id:
        meta = fetch_metadata_by_arxiv(reference.arxiv_id)
    else:
        meta = search_crossref_by_title(reference.title, client)
        if meta is None:
            raise MetadataError("No confident match on Crossref for this title.")
    if not meta:
        return False
    if (
        meta.get("doi")
        and Reference.objects.filter(doi=meta["doi"]).exclude(pk=reference.pk).exists()
    ):
        raise MetadataError(f"Another reference already has DOI {meta['doi']}.")
    for field in (
        "doi",
        "arxiv_id",
        "openalex_id",
        "entry_type",
        "title",
        "authors",
        "year",
        "venue",
        "abstract",
        "url",
        "citation_count",
    ):
        value = meta.get(field)
        if value not in (None, "", []):
            setattr(reference, field, value)
    extra = {**reference.extra, **meta.get("extra", {})}
    extra.pop("needs_metadata", None)
    extra.pop("metadata_error", None)
    reference.extra = extra
    reference.save()
    return True


def export_bibtex(references) -> str:
    """One .bib for any iterable/queryset of references, stable generated keys."""
    from .services import render_bibtex

    return "\n\n".join(render_bibtex(ref) for ref in references) + ("\n" if references else "")
