"""Cross-project dashboard: what should I work on today, everywhere?"""

import datetime

from django.db.models import F
from django.utils import timezone

from documents.models import Document
from literature.models import ProjectReference, Reference
from notes.models import Note, QuickCapture
from plans.models import Milestone
from plans.selectors import current_phase, project_progress
from projects.models import DecisionRecord, Project
from research.models import Dataset, Evidence, ExperimentEntry, Hypothesis
from writing.models import Manuscript, SubmissionEvent

HEATMAP_WEEKS = 26

ACTIVITY_MODELS = [
    Project,
    DecisionRecord,
    Document,
    Note,
    QuickCapture,
    Reference,
    ProjectReference,
    Milestone,
    Manuscript,
    SubmissionEvent,
    Hypothesis,
    Evidence,
    ExperimentEntry,
    Dataset,
]


def active_projects():
    projects = Project.objects.filter(
        status__in=[Project.Status.PLANNING, Project.Status.ACTIVE]
    ).prefetch_related("phases")
    rows = []
    for project in projects:
        done, total, percent = project_progress(project)
        rows.append(
            {
                "project": project,
                "phase": current_phase(project),
                "done": done,
                "total": total,
                "percent": percent,
            }
        )
    return rows


def upcoming_milestones(limit=10):
    return (
        Milestone.objects.filter(completed_at__isnull=True, due_date__isnull=False)
        .filter(phase__project__status__in=["planning", "active"])
        .select_related("phase__project")
        .order_by(F("due_date").asc())[:limit]
    )


def upcoming_deadlines(limit=5):
    return (
        Manuscript.objects.filter(deadline__isnull=False)
        .exclude(status__in=["published", "shelved"])
        .select_related("project")
        .order_by("deadline")[:limit]
    )


def activity_heatmap(today=None):
    """GitHub-style: list of weeks, each a list of 7 {date, count, level} cells.

    Cached for 10 minutes — 28 aggregate queries that change at day granularity.
    """
    from django.core.cache import cache

    today = today or timezone.localdate()
    cache_key = f"activity_heatmap:{today.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    weeks = _build_heatmap(today)
    cache.set(cache_key, weeks, 600)
    return weeks


def _build_heatmap(today):
    start = today - datetime.timedelta(weeks=HEATMAP_WEEKS)
    start -= datetime.timedelta(days=start.weekday())  # align to Monday

    from django.db.models import Count
    from django.db.models.functions import TruncDate

    counts: dict[datetime.date, int] = {}
    for model in ACTIVITY_MODELS:
        for field in ("created_at", "updated_at"):
            rows = (
                model.objects.filter(**{f"{field}__date__gte": start})
                .annotate(_day=TruncDate(field))
                .values("_day")
                .annotate(n=Count("pk"))
            )
            for row in rows:
                counts[row["_day"]] = counts.get(row["_day"], 0) + row["n"]

    weeks = []
    cursor = start
    while cursor <= today:
        week = []
        for _ in range(7):
            count = counts.get(cursor, 0)
            level = (
                0
                if count == 0
                else 1
                if count <= 2
                else 2
                if count <= 6
                else 3
                if count <= 15
                else 4
            )
            week.append({"date": cursor, "count": count, "level": level, "future": cursor > today})
            cursor += datetime.timedelta(days=1)
        weeks.append(week)
    return weeks


def monthly_stats(today=None):
    today = today or timezone.localdate()
    month_start = today.replace(day=1)
    return {
        "papers_read": ProjectReference.objects.filter(
            reading_status__in=["read", "annotated"], updated_at__date__gte=month_start
        ).count(),
        "notes_written": Note.objects.filter(created_at__date__gte=month_start).count(),
        "milestones_done": Milestone.objects.filter(completed_at__date__gte=month_start).count(),
        "experiments_logged": ExperimentEntry.objects.filter(date__gte=month_start).count(),
    }


def dashboard_context():
    return {
        "active": active_projects(),
        "milestones": upcoming_milestones(),
        "deadlines": upcoming_deadlines(),
        "heatmap": activity_heatmap(),
        "stats": monthly_stats(),
        "inbox_count": QuickCapture.objects.filter(processed=False).count(),
    }
