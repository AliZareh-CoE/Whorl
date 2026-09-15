"""#517 — the plan review: a sitting where every open milestone is looked at once, with
everything Atlas knows about it (late, blocked, slack, conflict, drift, open tasks), and given a
verdict — keep, done, move, skip. `review_queue` is the list in review order, `review_state`
says when the plan was last reviewed and whether a review is due, `finish_review` records the
sitting."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from projects.models import Project

from .calibration import calibration, likely_date
from .dependencies import blocked_map, date_conflicts, due_graph, slack_map
from .drift import change_rows, milestone_drift
from .models import Milestone, PlanReview

REVIEW_DAYS = 7  # a plan reviewed less often than weekly is one nobody is steering


def review_state(project: Project, today: date | None = None) -> dict:
    """{last: datetime | None, days_since: int | None, due: bool, open: int} — `due` when open
    milestones exist and the plan was never reviewed or the last review is REVIEW_DAYS old."""
    today = today or timezone.localdate()
    last = project.plan_reviews.order_by("-reviewed_at", "-pk").first()
    open_count = Milestone.objects.filter(phase__project=project, completed_at__isnull=True).count()
    days_since = (
        (today - timezone.localtime(last.reviewed_at).date()).days if last is not None else None
    )
    due = open_count > 0 and (days_since is None or days_since >= REVIEW_DAYS)
    return {
        "last": last.reviewed_at if last is not None else None,
        "days_since": days_since,
        "due": due,
        "open": open_count,
        "summary": (
            {
                "kept": last.kept,
                "completed": last.completed,
                "moved": last.moved,
                "skipped": last.skipped,
                "note": last.note,
            }
            if last is not None
            else None
        ),
    }


def review_queue(project: Project, today: date | None = None) -> list[dict]:
    """Every open milestone in review order — overdue first (latest first), then dated by due
    date, undated last — each with its phase, days to due, open blockers, slack, conflict,
    drift, the likely landing (#520) and open-task count."""
    today = today or timezone.localdate()
    milestones = list(
        Milestone.objects.filter(phase__project=project, completed_at__isnull=True)
        .select_related("phase")
        .prefetch_related("tasks")
        .order_by("due_date", "pk")
    )
    blocked = blocked_map(project)
    graph = due_graph(project)
    slack = slack_map(project, *graph)
    conflicts = {c["id"] for c in date_conflicts(project, *graph)}
    moves = change_rows(project)
    cal = calibration(project, rows=moves)  # #520: one read of the completed milestones
    rows = []
    for m in milestones:
        drift = milestone_drift(m, moves.get(m.pk, []))
        days = (m.due_date - today).days if m.due_date else None
        rows.append(
            {
                "id": m.pk,
                "title": m.title,
                "phase": m.phase.name,
                "phase_id": m.phase_id,
                "due_date": m.due_date,
                "days": days,
                "overdue": days is not None and days < 0,
                "notes": m.notes,
                "blocked": bool(blocked.get(m.pk)),
                "blocked_by": [b["title"] for b in blocked.get(m.pk, [])],
                "slack": slack.get(m.pk, {}).get("slack"),
                "conflict": m.pk in conflicts,
                "baseline": drift["baseline"],
                "moves": drift["moves"],
                "slipped": drift["slipped"],
                "likely": likely_date(m.due_date, cal, today),  # #520
                "open_tasks": sum(1 for t in m.tasks.all() if not t.done),
                "tasks": sum(1 for _ in m.tasks.all()),
            }
        )

    def order(row: dict):
        if row["days"] is None:
            return (2, 0, row["id"])
        if row["days"] < 0:
            return (0, row["days"], row["id"])  # most overdue first
        return (1, row["days"], row["id"])

    rows.sort(key=order)
    return rows


def finish_review(
    project: Project,
    *,
    kept: int = 0,
    completed: int = 0,
    moved: int = 0,
    skipped: int = 0,
    note: str = "",
) -> dict:
    """Record a sitting and return the new `review_state`."""
    PlanReview.objects.create(
        project=project,
        kept=kept,
        completed=completed,
        moved=moved,
        skipped=skipped,
        note=note.strip(),
    )
    return review_state(project)
