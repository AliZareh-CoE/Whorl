"""#516 — plan drift: every due-date move is logged (`Milestone.save` → `record_move`), and
the log answers "how far has the plan slipped from what was first written?" — per milestone
(baseline, moves, days slipped) and per project (total drift, the milestone that slipped most,
the end of the plan then and now). Pure functions over one query per project."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from django.utils import timezone

from .models import Milestone, MilestoneDateChange

COALESCE_MINUTES = 10  # nudging a diamond three times in a row is one move


def record_move(
    milestone: Milestone, from_date: date | None, to_date: date | None
) -> MilestoneDateChange | None:
    """Log a due-date change. A move within `COALESCE_MINUTES` of the previous one folds into
    it (its `to_date` is replaced); a fold that lands back on the previous `from_date` deletes
    the row, so an undo leaves no trace. Returns the row that now records the move (None when
    the fold cancelled it)."""
    if from_date == to_date:
        return None
    latest = milestone.date_changes.order_by("-changed_at", "-pk").first()
    if latest is not None and latest.changed_at >= timezone.now() - timedelta(
        minutes=COALESCE_MINUTES
    ):
        if latest.from_date == to_date:
            latest.delete()
            return None
        latest.to_date = to_date
        latest.save(update_fields=["to_date"])
        return latest
    return MilestoneDateChange.objects.create(
        milestone=milestone, from_date=from_date, to_date=to_date
    )


def change_rows(project) -> dict[int, list[MilestoneDateChange]]:
    """Every logged move in the project, oldest first, grouped by milestone id — one query."""
    rows: dict[int, list[MilestoneDateChange]] = defaultdict(list)
    for change in MilestoneDateChange.objects.filter(milestone__phase__project=project).order_by(
        "changed_at", "pk"
    ):
        rows[change.milestone_id].append(change)
    return rows


def baseline_of(changes: list[MilestoneDateChange], current: date | None) -> date | None:
    """The date the milestone was first given: the earliest logged `from_date`, else the
    earliest `to_date` (a milestone dated after it was created), else the current date."""
    for change in changes:
        if change.from_date is not None:
            return change.from_date
    for change in changes:
        if change.to_date is not None:
            return change.to_date
    return current


def milestone_drift(milestone: Milestone, changes: list[MilestoneDateChange]) -> dict:
    """{baseline, moves, slipped (days, negative when pulled in, None when undated), history
    [{from, to, at}]} for one milestone."""
    baseline = baseline_of(changes, milestone.due_date)
    slipped = (
        (milestone.due_date - baseline).days
        if milestone.due_date is not None and baseline is not None
        else None
    )
    return {
        "baseline": baseline,
        "moves": len(changes),
        "slipped": slipped,
        "history": [
            {"from": c.from_date, "to": c.to_date, "at": c.changed_at, "reason": c.reason}
            for c in changes
        ],
    }


def project_drift(project, milestones: list[Milestone] | None = None, rows=None) -> dict:
    """The plan's drift: `total` days slipped across every dated milestone with a baseline
    (pull-ins count negative), `moved` milestones, `most` — the milestone that slipped most
    ({id, title, phase, slipped, baseline, due_date}) — and the plan's end (the last due date)
    as first written vs now. `milestones` may be passed prefetched with their phases; `rows`
    from `change_rows` lets a caller share the query."""
    if milestones is None:
        milestones = list(Milestone.objects.filter(phase__project=project).select_related("phase"))
    if rows is None:
        rows = change_rows(project)
    per: dict[int, dict] = {}
    total, moved, most = 0, 0, None
    baseline_end: date | None = None
    current_end: date | None = None
    for m in milestones:
        d = milestone_drift(m, rows.get(m.pk, []))
        per[m.pk] = d
        if d["moves"]:
            moved += 1
        if d["slipped"] is not None:
            total += d["slipped"]
            if most is None or d["slipped"] > most["slipped"]:
                most = {
                    "id": m.pk,
                    "title": m.title,
                    "phase": m.phase.name,
                    "slipped": d["slipped"],
                    "baseline": d["baseline"],
                    "due_date": m.due_date,
                }
        if d["baseline"] is not None:
            baseline_end = max(baseline_end or d["baseline"], d["baseline"])
        if m.due_date is not None:
            current_end = max(current_end or m.due_date, m.due_date)
    if most is not None and most["slipped"] <= 0:
        most = None
    return {
        "milestones": per,
        "total": total,
        "moved": moved,
        "most": most,
        "baseline_end": baseline_end,
        "current_end": current_end,
    }


def drift_report(project) -> dict:
    """`project_drift` shaped for the API: milestone rows sorted by slip (most first) with
    titles and phases, plus the project totals."""
    milestones = list(
        Milestone.objects.filter(phase__project=project)
        .select_related("phase")
        .order_by("phase__order", "due_date", "pk")
    )
    drift = project_drift(project, milestones)
    rows = [
        {
            "id": m.pk,
            "title": m.title,
            "phase": m.phase.name,
            "due_date": m.due_date,
            "done": m.completed_at is not None,
            **drift["milestones"][m.pk],
        }
        for m in milestones
    ]
    rows.sort(key=lambda r: (-(r["slipped"] or 0), r["id"]))
    return {
        "project": project.slug,
        "total": drift["total"],
        "moved": drift["moved"],
        "most": drift["most"],
        "baseline_end": drift["baseline_end"],
        "current_end": drift["current_end"],
        "milestones": rows,
    }
