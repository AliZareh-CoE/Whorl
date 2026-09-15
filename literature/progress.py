"""Reading progress (#523, Library return pass): where the reader left off, and when a paper
was started and finished in each project.

The position lives on the Reference — one PDF, one reader, one researcher — while the
started / finished stamps live on the ProjectReference, because "read" is a verdict given per
project. Nothing here changes a reading status: the researcher does that; Atlas only remembers
when. Pure functions over the ORM, no network.
"""

from __future__ import annotations

import math
from datetime import timedelta

from django.utils import timezone

from .models import ProjectReference, Reference

FINISHED = {ProjectReference.ReadingStatus.READ, ProjectReference.ReadingStatus.ANNOTATED}
RECENT_DAYS = 30


class ProgressError(ValueError):
    """A position that cannot be recorded (page 0, past the end, an unknown project)."""


def percent_of(page: int | None, pages: int | None) -> int | None:
    """Whole-number progress, half-up; None until the page count is known."""
    if not page or not pages:
        return None
    return max(0, min(100, math.floor(100 * page / pages + 0.5)))


def progress_of(reference: Reference) -> dict:
    return {
        "page": reference.last_page,
        "pages": reference.page_count,
        "percent": percent_of(reference.last_page, reference.page_count),
        "last_read_at": reference.last_read_at,
    }


def record_position(
    reference: Reference,
    page: int,
    page_count: int | None = None,
    project=None,
    now=None,
) -> dict:
    """Remember the page the reader is on. `page_count` (what the reader saw) is stored when
    given; a page past the known end is refused. With a project the link's `started_at` is
    stamped once. Bumps `updated_at` so the list ETags move with the bars."""
    now = now or timezone.now()
    try:
        page = int(page)
    except (TypeError, ValueError) as exc:
        raise ProgressError("page must be a whole number") from exc
    if page < 1:
        raise ProgressError("page must be 1 or more")
    if page_count is not None:
        try:
            page_count = int(page_count)
        except (TypeError, ValueError) as exc:
            raise ProgressError("page_count must be a whole number") from exc
        if page_count < 1:
            raise ProgressError("page_count must be 1 or more")
        reference.page_count = page_count
    if reference.page_count and page > reference.page_count:
        raise ProgressError(f"page {page} is past the end ({reference.page_count} pages)")
    reference.last_page = page
    reference.last_read_at = now
    reference.save(update_fields=["last_page", "page_count", "last_read_at", "updated_at"])
    if project is not None:
        link = ProjectReference.objects.filter(project=project, reference=reference).first()
        if link is None:
            raise ProgressError("this paper is not filed in that project")
        if link.started_at is None:
            link.started_at = now
            link.save(update_fields=["started_at", "updated_at"])
    return progress_of(reference)


def stamp_transition(link: ProjectReference, loaded_status: str | None, now=None) -> list[str]:
    """Called by ProjectReference.save(): stamp `started_at` when a paper leaves *to read*
    (or is created past it) and `finished_at` when it reaches *read* / *annotated*; leaving
    those two clears `finished_at` and keeps `started_at`. Returns the fields set."""
    status = link.reading_status
    if loaded_status == status:
        return []
    now = now or timezone.now()
    touched: list[str] = []
    to_read = ProjectReference.ReadingStatus.TO_READ
    if status != to_read and link.started_at is None:
        link.started_at = now
        touched.append("started_at")
    if status in FINISHED and link.finished_at is None:
        link.finished_at = now
        touched.append("finished_at")
    if status not in FINISHED and link.finished_at is not None:
        link.finished_at = None  # the verdict was withdrawn (read → skimmed, or back to the queue)
        touched.append("finished_at")
    return touched


def reading_now(limit: int = 5, days: int = RECENT_DAYS, now=None) -> list[dict]:
    """Papers you are in the middle of: a remembered page past the first, read within `days`,
    not at the last page — newest first. The Library rail's "Continue reading"."""
    now = now or timezone.now()
    since = now - timedelta(days=days)
    qs = (
        Reference.objects.filter(last_read_at__gte=since, last_page__gte=2)
        .prefetch_related("project_links__project")
        .order_by("-last_read_at")
    )
    rows = []
    for ref in qs:
        if ref.page_count and ref.last_page >= ref.page_count:
            continue
        links = list(ref.project_links.all())
        if links and all(link.reading_status in FINISHED for link in links):
            continue  # marked read everywhere it is filed: the verdict outranks the page
        rows.append(
            {
                "id": ref.pk,
                "title": ref.title,
                "bibtex_key": ref.bibtex_key,
                "year": ref.year,
                "pdf": ref.pdf.url if ref.pdf else None,
                **progress_of(ref),
                "projects": [link.project.slug for link in ref.project_links.all()],
            }
        )
        if len(rows) >= limit:
            break
    return rows
