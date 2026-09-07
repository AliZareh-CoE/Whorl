"""Library v2 query layer: facets, filters, bulk actions, and metadata recovery.

Pure-ish functions over querysets so the API stays thin and everything is unit-testable.
"""

from __future__ import annotations

import re

import httpx
from django.db.models import Count, Exists, OuterRef, Q, QuerySet

from projects.models import Project

from .fulltext import pdf_match_filter
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


def _pdf_hit(q: str):
    from .models import ReferenceText

    return ReferenceText.objects.filter(reference=OuterRef("pk"), body__icontains=q)


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
            | pdf_match_filter(q)  # slice 8: inside the PDF text too
        )
        qs = qs.annotate(pdf_match=Exists(_pdf_hit(q)))
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
        {
            "id": row["tags__id"],
            "name": row["tags__name"],
            "color": row["tags__color"],
            "count": row["n"],
        }
        for row in qs.exclude(tags__isnull=True)
        .values("tags__id", "tags__name", "tags__color")
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
        "duplicates": sum(len(g["members"]) for g in duplicate_groups(qs)),
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


def touch_references(pks) -> None:
    """Bump updated_at so list/detail ETags change when only a tag (M2M) moved."""
    from django.utils import timezone

    if pks:
        Reference.objects.filter(pk__in=list(pks)).update(updated_at=timezone.now())


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
        touched: list[int] = []
        if action == "tag":
            tag = LibraryTag.get_or_create_named(value)
            for ref in refs:
                if not ref.tags.filter(pk=tag.pk).exists():
                    ref.tags.add(tag)
                    touched.append(ref.pk)
        else:
            tag = LibraryTag.objects.filter(name__iexact=value.strip()).first()
            if tag:
                for ref in refs.filter(tags=tag):
                    ref.tags.remove(tag)
                    touched.append(ref.pk)
        affected = len(touched)
        # M2M changes don't move updated_at, and the list ETag is built from it: without this
        # bump the SPA keeps getting 304s and never shows the new tag (#381).
        touch_references(touched)
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


# --- duplicates (Library v2 slice 6) ---------------------------------------------------------


def duplicate_groups(qs: QuerySet | None = None) -> list[dict]:
    """Clusters of probable duplicates (same DOI, same arXiv id, or near-identical titles),
    each with a suggested `keep` (the most complete record: PDF, DOI, abstract, links, age)."""
    from .services import check_duplicates

    refs = list(
        (qs if qs is not None else Reference.objects.all()).prefetch_related(
            "project_links", "tags"
        )
    )
    parent = {r.pk: r.pk for r in refs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    reasons: dict[int, set[str]] = {}
    for finding in check_duplicates(refs):
        a, b = finding["references"]
        # a similar title with clearly different years is a series/edition, not a duplicate
        if "DOI" not in finding["message"] and a.year and b.year and abs(a.year - b.year) > 1:
            continue
        union(a.pk, b.pk)
        reasons.setdefault(a.pk, set()).add("doi" if "DOI" in finding["message"] else "title")
        reasons.setdefault(b.pk, set()).add("doi" if "DOI" in finding["message"] else "title")
    by_arxiv: dict[str, Reference] = {}
    for r in refs:
        if r.arxiv_id:
            if r.arxiv_id in by_arxiv:
                union(by_arxiv[r.arxiv_id].pk, r.pk)
                reasons.setdefault(r.pk, set()).add("arxiv")
                reasons.setdefault(by_arxiv[r.arxiv_id].pk, set()).add("arxiv")
            else:
                by_arxiv[r.arxiv_id] = r
    clusters: dict[int, list[Reference]] = {}
    for r in refs:
        root = find(r.pk)
        if root in reasons or r.pk in reasons:
            clusters.setdefault(root, []).append(r)
    groups = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        members.sort(key=_completeness, reverse=True)
        groups.append(
            {
                "keep": members[0].pk,
                "reasons": sorted({x for m in members for x in reasons.get(m.pk, set())}),
                "members": [
                    {
                        "id": m.pk,
                        "title": m.title,
                        "year": m.year,
                        "doi": m.doi,
                        "venue": m.venue,
                        "bibtex_key": m.bibtex_key,
                        "has_pdf": bool(m.pdf),
                        "projects": [link.project.slug for link in m.project_links.all()],
                        "tags": [t.name for t in m.tags.all()],
                        "score": _completeness(m),
                    }
                    for m in members
                ],
            }
        )
    groups.sort(key=lambda g: -len(g["members"]))
    return groups


def _completeness(r: Reference) -> int:
    return (
        (8 if r.pdf else 0)
        + (4 if r.doi else 0)
        + (2 if r.abstract else 0)
        + (2 if r.year else 0)
        + (1 if r.venue else 0)
        + len(r.authors or [])
        + r.project_links.count() * 3
        + r.tags.count()
    )


def merge_references(keep_id: int, merge_ids: list[int]) -> dict:
    """Fold `merge_ids` into `keep_id`: project links (best reading state wins), tags, notes,
    manuscript bibliographies, evidence, citation edges, comments, and the PDF move over;
    empty fields on the kept record are filled from the merged ones; then the others are
    deleted. Returns {kept, merged, moved: {...}}."""
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction

    from core.models import Comment
    from research.models import Evidence
    from writing.models import ManuscriptReference

    from .models import CitationEdge

    keep = Reference.objects.get(pk=keep_id)
    others = list(Reference.objects.filter(pk__in=[i for i in merge_ids if i != keep_id]))
    if not others:
        raise ValueError("Nothing to merge into the kept reference.")
    merged_ids = [o.pk for o in others]  # captured now: delete() clears pk
    status_rank = {"to_read": 0, "skimmed": 1, "read": 2, "annotated": 3}
    moved = {
        "project_links": 0,
        "tags": 0,
        "notes": 0,
        "manuscripts": 0,
        "evidence": 0,
        "citations": 0,
        "comments": 0,
        "pdf": False,
    }
    ct = ContentType.objects.get_for_model(Reference)
    with transaction.atomic():
        for other in others:
            for link in other.project_links.all():
                existing = ProjectReference.objects.filter(
                    project=link.project, reference=keep
                ).first()
                if existing is None:
                    link.reference = keep
                    link.save(update_fields=["reference", "updated_at"])
                    moved["project_links"] += 1
                else:
                    if status_rank.get(link.reading_status, 0) > status_rank.get(
                        existing.reading_status, 0
                    ):
                        existing.reading_status = link.reading_status
                    if link.priority == "high":
                        existing.priority = "high"
                    if link.notes and link.notes not in existing.notes:
                        existing.notes = (existing.notes + "\n\n" + link.notes).strip()
                    existing.save()
                    for mark in link.review_marks.all():
                        if not existing.review_marks.filter(theme=mark.theme).exists():
                            mark.project_reference = existing
                            mark.save(update_fields=["project_reference"])
                    link.delete()
            for tag in other.tags.all():
                if not keep.tags.filter(pk=tag.pk).exists():
                    keep.tags.add(tag)
                    moved["tags"] += 1
            for note in other.notes.all():
                if not note.references.filter(pk=keep.pk).exists():
                    note.references.add(keep)
                    moved["notes"] += 1
                note.references.remove(other)
            for mref in ManuscriptReference.objects.filter(reference=other):
                if ManuscriptReference.objects.filter(
                    manuscript=mref.manuscript, reference=keep
                ).exists():
                    mref.delete()
                else:
                    mref.reference = keep
                    mref.save(update_fields=["reference"])
                    moved["manuscripts"] += 1
            moved["evidence"] += Evidence.objects.filter(reference=other).update(reference=keep)
            for edge in CitationEdge.objects.filter(citing=other):
                if (
                    edge.cited_id == keep.pk
                    or CitationEdge.objects.filter(citing=keep, cited=edge.cited).exists()
                ):
                    edge.delete()
                else:
                    edge.citing = keep
                    edge.save(update_fields=["citing"])
                    moved["citations"] += 1
            for edge in CitationEdge.objects.filter(cited=other):
                if (
                    edge.citing_id == keep.pk
                    or CitationEdge.objects.filter(citing=edge.citing, cited=keep).exists()
                ):
                    edge.delete()
                else:
                    edge.cited = keep
                    edge.save(update_fields=["cited"])
                    moved["citations"] += 1
            moved["comments"] += Comment.objects.filter(content_type=ct, object_id=other.pk).update(
                object_id=keep.pk
            )
            if not keep.pdf and other.pdf:
                keep.pdf = other.pdf
                other.pdf = None  # keep the file: it now belongs to `keep`
                moved["pdf"] = True
            for field in (
                "doi",
                "arxiv_id",
                "openalex_id",
                "abstract",
                "year",
                "venue",
                "url",
                "citation_count",
            ):
                if not getattr(keep, field) and getattr(other, field):
                    setattr(keep, field, getattr(other, field))
            if not keep.authors and other.authors:
                keep.authors = other.authors
            keep.extra = {
                **other.extra,
                **keep.extra,
                "merged_from": [*keep.extra.get("merged_from", []), other.bibtex_key],
            }
            # release the unique DOI (and the PDF file) from the merged record BEFORE the kept
            # one saves them, or the DOI unique constraint fires
            Reference.objects.filter(pk=other.pk).update(doi=None, pdf="")
            keep.save()
            other.delete()
    return {"kept": keep.pk, "merged": merged_ids, "moved": moved}
