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
    projects = Project.objects.filter(status__in=[Project.Status.PLANNING, Project.Status.ACTIVE])
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
    """GitHub-style: list of weeks, each a list of 7 {date, count, level} cells."""
    today = today or timezone.localdate()
    start = today - datetime.timedelta(weeks=HEATMAP_WEEKS)
    start -= datetime.timedelta(days=start.weekday())  # align to Monday

    counts: dict[datetime.date, int] = {}
    for model in ACTIVITY_MODELS:
        for field in ("created_at", "updated_at"):
            for value in model.objects.filter(**{f"{field}__date__gte": start}).values_list(
                field, flat=True
            ):
                day = timezone.localtime(value).date()
                counts[day] = counts.get(day, 0) + 1

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
