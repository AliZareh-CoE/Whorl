"""This week's focus for one project (Plan v2 slice 3).

Answers "what do I do on this project this week?": overdue milestones and tasks first, then
everything due in the next seven days, then the next undated milestones of the current phase so
the list is never empty while there is work left. Same data feeds the Plan page strip, the
project overview, and the MCP tool.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone

from projects.models import Project

from . import selectors
from .models import Milestone, Task

WEEK = 7


def _item(kind: str, obj, today: date) -> dict:
    if kind == "milestone":
        due, phase, milestone = obj.due_date, obj.phase, None
    else:
        due, phase, milestone = obj.due_date, obj.milestone.phase, obj.milestone
    return {
        "kind": kind,
        "id": obj.pk,
        "title": obj.title,
        "due_date": due,
        "days": (due - today).days if due else None,
        "phase": phase.name,
        "phase_id": phase.pk,
        "milestone": milestone.title if milestone else None,
        "milestone_id": milestone.pk if milestone else None,
    }


def week_focus(project: Project, today: date | None = None) -> dict:
    today = today or timezone.localdate()
    horizon = today + timedelta(days=WEEK)
    open_milestones = Milestone.objects.filter(
        phase__project=project, completed_at__isnull=True
    ).select_related("phase")
    open_tasks = Task.objects.filter(milestone__phase__project=project, done=False).select_related(
        "milestone__phase"
    )
    overdue = sorted(
        [_item("milestone", m, today) for m in open_milestones if m.due_date and m.due_date < today]
        + [_item("task", t, today) for t in open_tasks if t.due_date and t.due_date < today],
        key=lambda i: (i["due_date"], i["kind"] != "milestone"),
    )
    due_soon = sorted(
        [
            _item("milestone", m, today)
            for m in open_milestones
            if m.due_date and today <= m.due_date <= horizon
        ]
        + [
            _item("task", t, today)
            for t in open_tasks
            if t.due_date and today <= t.due_date <= horizon
        ],
        key=lambda i: (i["due_date"], i["kind"] != "milestone"),
    )
    listed = {(i["kind"], i["id"]) for i in overdue + due_soon}
    next_up: list[dict] = []
    phase = selectors.current_phase(project)
    if phase is not None:
        for m in open_milestones.filter(phase=phase).order_by("due_date", "pk"):
            if ("milestone", m.pk) not in listed:
                next_up.append(_item("milestone", m, today))
            if len(next_up) >= 3:
                break
    return {
        "project": project.slug,
        "today": today,
        "week_ends": horizon,
        "overdue": overdue,
        "due_this_week": due_soon,
        "next_up": next_up,
        "current_phase": (
            {"id": phase.pk, "name": phase.name, "status": phase.status} if phase else None
        ),
    }
