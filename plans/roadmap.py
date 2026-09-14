"""Roadmap data for the Plan page (Plan v2 slice 2).

Phases become bars on a time axis, milestones become diamonds on their due dates, and each
phase gets an honest health reading: the share of milestones done against the share of the
phase's time that has elapsed, plus a finish forecast from the pace of the milestones already
completed. Phases without dates get a suggested window so the roadmap never starts empty.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone

from core.memo import memo
from projects.models import Project

from .models import Phase

DEFAULT_PHASE_WEEKS = 6


def _phase_window(phase: Phase, previous_end: date | None, today: date) -> tuple[date, date, bool]:
    """(start, end, inferred) — real dates, else a window inferred from milestones/neighbours."""
    milestones = list(phase.milestones.all())
    dues = sorted(m.due_date for m in milestones if m.due_date)
    start, end = phase.target_start, phase.target_end
    inferred = False
    if start is None:
        inferred = True
        start = (previous_end + timedelta(days=1)) if previous_end else (dues[0] if dues else today)
        if end is None and dues:
            start = min(start, dues[0])
    if end is None:
        inferred = True
        end = dues[-1] if dues else start + timedelta(weeks=DEFAULT_PHASE_WEEKS)
    if end < start:
        end = start
    return start, end, inferred


def _health(phase: Phase, start: date, end: date, today: date) -> dict:
    milestones = list(phase.milestones.all())
    total = len(milestones)
    done = [m for m in milestones if m.completed_at]
    if phase.status == Phase.Status.DONE:
        return {"state": "done", "label": "done", "forecast_end": None}
    if total == 0:
        return {"state": "empty", "label": "no milestones", "forecast_end": None}
    span = max(1, (end - start).days)
    elapsed = min(max((today - start).days, 0), span) / span
    progress = len(done) / total
    remaining = total - len(done)
    forecast = None
    if remaining and len(done) >= 2:
        # pace: days per milestone measured between the first and last completions
        stamps = sorted(m.completed_at.date() for m in done)
        pace = max(1, (stamps[-1] - stamps[0]).days) / (len(done) - 1)
        forecast = today + timedelta(days=round(pace * remaining))
    if today < start:
        state, label = "upcoming", f"starts in {(start - today).days} d"
    elif today > end:
        state, label = "overdue", f"{(today - end).days} d past its end"
    elif phase.status == Phase.Status.BLOCKED:
        state, label = "blocked", "blocked"
    elif progress + 0.15 < elapsed:
        state, label = (
            "behind",
            f"behind — {len(done)}/{total} done, {round(elapsed * 100)}% of time used",
        )
    elif progress > elapsed + 0.15:
        state, label = "ahead", f"ahead — {len(done)}/{total} done"
    else:
        state, label = "on_track", "on track"
    return {"state": state, "label": label, "forecast_end": forecast}


def project_roadmap(project: Project, today: date | None = None) -> dict:
    today = today or timezone.localdate()
    return memo(project, ("project_roadmap", today), lambda: _project_roadmap(project, today))


def _project_roadmap(project: Project, today: date) -> dict:
    from .dependencies import (
        blocked_map,
        blocker_ids,
        critical_chain,
        date_conflicts,
        dependency_edges,
        slack_map,
    )
    from .drift import change_rows, milestone_drift

    phases = list(project.phases.prefetch_related("milestones"))
    moves = change_rows(project)  # #516: one query for the ghost diamonds
    facts = dependency_edges(project)  # one query for #512's flags, #513's conflicts, #514's arrows
    blocked = blocked_map(project, facts)
    edges = blocker_ids(project, facts)
    open_ms = {m.pk: m for ph in phases for m in ph.milestones.all() if m.completed_at is None}
    open_blockers = {mid: [b for b in edges.get(mid, ()) if b in open_ms] for mid in open_ms}
    conflicts = {c["id"] for c in date_conflicts(project, open_ms, open_blockers)}
    slack = slack_map(project, open_ms, open_blockers)  # #515
    chain = critical_chain(project, open_ms, open_blockers)
    rows = []
    previous_end: date | None = None
    for phase in phases:
        start, end, inferred = _phase_window(phase, previous_end, today)
        previous_end = end
        milestones = [
            {
                "id": m.pk,
                "title": m.title,
                "due_date": m.due_date,
                "done": bool(m.completed_at),
                "overdue": m.is_overdue,
                "blocked": bool(blocked.get(m.pk)) and m.completed_at is None,
                "blocked_by": edges.get(m.pk, []),
                "conflict": m.pk in conflicts,
                "slack": slack.get(m.pk, {}).get("slack"),
                # #516: baseline / moves / slipped (the history stays on the plan payload)
                **{
                    k: v
                    for k, v in milestone_drift(m, moves.get(m.pk, [])).items()
                    if k != "history"
                },
            }
            for m in phase.milestones.all()
        ]
        health = _health(phase, start, end, today)
        rows.append(
            {
                "id": phase.pk,
                "name": phase.name,
                "order": phase.order,
                "status": phase.status,
                "start": start,
                "end": end,
                "inferred": inferred,
                "progress": phase.progress,
                "milestones": milestones,
                **health,
            }
        )
    starts = [r["start"] for r in rows]
    ends = [r["end"] for r in rows] + [r["forecast_end"] for r in rows if r["forecast_end"]]
    return {
        "project": project.slug,
        "today": today,
        "range_start": min(starts + [today]) if rows else today,
        "range_end": max(ends + [today]) if rows else today + timedelta(weeks=12),
        "phases": rows,
        "critical_chain": chain,  # #515
    }
