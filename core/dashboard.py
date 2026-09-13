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
                # grove tree size scales with scope: 64px floor, +5px per milestone, 112px cap
                "tree_size": min(112, 64 + 5 * total),
            }
        )
    return rows


PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


def reading_queue_everywhere(today=None, limit: int = 5) -> dict:
    """#486: the head of the reading queue across every planning/active project — highest
    priority first, then the paper that has waited longest — plus how much is unread and how
    much of that is high priority. The dashboard's answer to "what should I read today?"."""
    from literature.models import ProjectReference

    today = today or timezone.localdate()
    links = list(
        ProjectReference.objects.filter(
            reading_status="to_read",
            project__status__in=[Project.Status.PLANNING, Project.Status.ACTIVE],
        )
        .select_related("reference", "project")
        .order_by("created_at")
    )
    queue = sorted(links, key=lambda link: (PRIORITY_RANK.get(link.priority, 1), link.created_at))
    return {
        "to_read": len(links),
        "high_priority": sum(1 for link in links if link.priority == "high"),
        "projects": len({link.project_id for link in links}),
        "next": [
            {
                "id": link.reference_id,
                "title": link.reference.title,
                "first_author": (
                    (link.reference.authors[0].get("family") if link.reference.authors else "")
                    or ""
                ),
                "year": link.reference.year,
                "priority": link.priority,
                "project": link.project.name,
                "project_slug": link.project.slug,
                "waiting_days": (today - timezone.localtime(link.created_at).date()).days,
            }
            for link in queue[:limit]
        ],
    }


def needs_attention(today=None, window_days=14):
    """The lead of the dashboard ([REV] cycle 145): the ANSWER to "what should I
    work on today?", not just data. Overdue milestones, manuscript deadlines
    inside the window, and untriaged inbox items — each one actionable."""
    today = today or timezone.localdate()
    soon = today + datetime.timedelta(days=window_days)
    overdue = list(
        Milestone.objects.filter(
            completed_at__isnull=True,
            due_date__lt=today,
            phase__project__status__in=["planning", "active"],
        )
        .select_related("phase__project")
        .order_by("due_date")
    )
    deadlines = list(
        Manuscript.objects.filter(deadline__isnull=False, deadline__lte=soon)
        .exclude(status__in=["published", "shelved"])
        .select_related("project")
        .order_by("deadline")
    )
    inbox = list(QuickCapture.objects.filter(processed=False).order_by("created_at")[:5])
    return {
        "overdue": overdue,
        "deadlines": deadlines,
        "inbox": inbox,
        "empty": not (overdue or deadlines or inbox),
    }


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
        "words_written": words_written_since(month_start),
    }


def words_written_since(start) -> int:
    """Words added to manuscripts since ``start`` (#418): the sum of positive day-to-day
    deltas of the daily word samples (#413), across every manuscript."""
    from writing.models import WordCountSample

    total = 0
    previous: dict[int, int] = {}
    for sample in WordCountSample.objects.order_by("manuscript_id", "date").values_list(
        "manuscript_id", "date", "words"
    ):
        manuscript_id, day, words = sample
        if manuscript_id in previous and day >= start:
            total += max(0, words - previous[manuscript_id])
        previous[manuscript_id] = words
    return total


def dashboard_context():
    return {
        "active": active_projects(),
        "attention": needs_attention(),
        "milestones": upcoming_milestones(),
        "deadlines": upcoming_deadlines(),
        "heatmap": activity_heatmap(),
        "stats": monthly_stats(),
        "inbox_count": QuickCapture.objects.filter(processed=False).count(),
    }


def week_everywhere(today=None, days=7, limit=40):
    """Dashboard v2: overdue and due-within-a-week milestones/tasks across active projects,
    overdue first, each with its project — the cross-project "this week" list."""
    from plans.models import Task

    today = today or timezone.localdate()
    horizon = today + datetime.timedelta(days=days)
    live = ["planning", "active"]
    items = []
    for m in (
        Milestone.objects.filter(
            completed_at__isnull=True, due_date__lte=horizon, phase__project__status__in=live
        )
        .select_related("phase__project")
        .order_by("due_date")[:limit]
    ):
        items.append(
            {
                "kind": "milestone",
                "id": m.pk,
                "title": m.title,
                "due_date": m.due_date,
                "days": (m.due_date - today).days,
                "project": m.phase.project.slug,
                "project_name": m.phase.project.name,
                "color": m.phase.project.color,
                "phase": m.phase.name,
            }
        )
    for t in (
        Task.objects.filter(
            done=False, due_date__lte=horizon, milestone__phase__project__status__in=live
        )
        .select_related("milestone__phase__project")
        .order_by("due_date")[:limit]
    ):
        project = t.milestone.phase.project
        items.append(
            {
                "kind": "task",
                "id": t.pk,
                "title": t.title,
                "due_date": t.due_date,
                "days": (t.due_date - today).days,
                "project": project.slug,
                "project_name": project.name,
                "color": project.color,
                "phase": t.milestone.phase.name,
            }
        )
    items.sort(key=lambda i: (i["due_date"], i["kind"] != "milestone", i["title"]))
    return {
        "today": today,
        "week_ends": horizon,
        "overdue": [i for i in items if i["days"] < 0],
        "due_this_week": [i for i in items if i["days"] >= 0],
    }


def project_health(rows):
    """Attach the current phase's health (from the roadmap) to each active-project row."""
    from plans.roadmap import project_roadmap

    out = {}
    for row in rows:
        project, phase = row["project"], row["phase"]
        if phase is None:
            continue
        match = next((r for r in project_roadmap(project)["phases"] if r["id"] == phase.pk), None)
        if match:
            out[project.slug] = {
                "state": match["state"],
                "label": match["label"],
                "forecast_end": match["forecast_end"],
            }
    return out
