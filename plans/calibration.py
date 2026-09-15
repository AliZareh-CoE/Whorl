"""#519 — calibration: how this project's milestones actually land against their dates.

Every completed milestone that held a date is a sample: `late` is the days between the date it
last held and the day it was completed (negative when early), `late_first` the same against the
first date it was ever given (#516's baseline). The medians are the project's bias, and the
median against the held date is the honest correction for the dates still open: `likely` =
due + median late, once there are `MIN_SAMPLE` landings. Pure functions over the milestones and
the drift log a caller already loaded — no extra queries on the plan payload."""

from __future__ import annotations

import math
from datetime import date, timedelta

from django.utils import timezone

from .drift import baseline_of, change_rows
from .models import Milestone

MIN_SAMPLE = 3  # fewer landings than this say nothing about a habit


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return math.floor((ordered[mid - 1] + ordered[mid]) / 2 + 0.5)  # halves round late, not even


def _percentile(values: list[int], share: float) -> int | None:
    """Nearest-rank percentile: the value `share` of the landings sit at or below."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, min(len(ordered), round(share * len(ordered) + 0.5)))
    return ordered[rank - 1]


def landing_rows(project, milestones: list[Milestone] | None = None, rows=None) -> list[dict]:
    """One row per completed milestone that held a date: {id, title, phase, phase_id, baseline,
    due_date, landed, late, late_first}, most recent landing first."""
    if milestones is None:
        milestones = list(
            Milestone.objects.filter(phase__project=project, completed_at__isnull=False)
            .exclude(due_date=None)
            .select_related("phase")
        )
    if rows is None:
        rows = change_rows(project)
    out = []
    for m in milestones:
        if m.completed_at is None or m.due_date is None:
            continue
        landed = timezone.localtime(m.completed_at).date()
        baseline = baseline_of(rows.get(m.pk, []), m.due_date) or m.due_date
        out.append(
            {
                "id": m.pk,
                "title": m.title,
                "phase": m.phase.name,
                "phase_id": m.phase_id,
                "baseline": baseline,
                "due_date": m.due_date,
                "landed": landed,
                "late": (landed - m.due_date).days,
                "late_first": (landed - baseline).days,
            }
        )
    out.sort(key=lambda r: (r["landed"], r["id"]), reverse=True)
    return out


def bucket_of(late: int) -> str:
    if late < 0:
        return "early"
    if late == 0:
        return "on_the_day"
    if late <= 7:
        return "week"
    if late <= 30:
        return "month"
    return "longer"


def calibration(project, milestones: list[Milestone] | None = None, rows=None) -> dict:
    """The project's landing habit: `count` landings, `on_time` (on or before the held date),
    `median_late` / `p80_late` against the held date, `median_late_first` against the first
    date, `buckets` {early, on_the_day, week, month, longer}, `worst` {id, title, late}, and
    `shift` — the days to add to an open date for a realistic one (None under MIN_SAMPLE)."""
    landings = landing_rows(project, milestones, rows)
    lates = [r["late"] for r in landings]
    buckets = {k: 0 for k in ("early", "on_the_day", "week", "month", "longer")}
    for late in lates:
        buckets[bucket_of(late)] += 1
    worst = max(landings, key=lambda r: (r["late"], -r["id"]), default=None)
    median = _median(lates)
    return {
        "count": len(landings),
        "on_time": sum(1 for late in lates if late <= 0),
        "median_late": median,
        "p80_late": _percentile(lates, 0.8),
        "median_late_first": _median([r["late_first"] for r in landings]),
        "buckets": buckets,
        "worst": (
            {"id": worst["id"], "title": worst["title"], "late": worst["late"]}
            if worst is not None and worst["late"] > 0
            else None
        ),
        "shift": median if len(landings) >= MIN_SAMPLE else None,
        "min_sample": MIN_SAMPLE,
    }


def likely_date(due: date | None, cal: dict, today: date | None = None) -> date | None:
    """The date an open milestone will realistically land: its held date plus the project's
    median lateness — None when undated, when the habit is not yet measurable, or when that
    date is already behind us (a prediction in the past is not a prediction)."""
    if due is None or cal.get("shift") is None:
        return None
    likely = due + timedelta(days=cal["shift"])
    return likely if likely >= (today or timezone.localdate()) else None


def phase_likely_end(
    milestones: list[Milestone], cal: dict, today: date | None = None
) -> date | None:
    """The latest `likely` date among a phase's open dated milestones (None when none)."""
    today = today or timezone.localdate()
    dates = [
        likely_date(m.due_date, cal, today)
        for m in milestones
        if m.completed_at is None and m.due_date is not None
    ]
    dates = [d for d in dates if d is not None]
    return max(dates) if dates else None


def calibration_report(project) -> dict:
    """`calibration` shaped for the API: the totals plus every landing row."""
    milestones = list(
        Milestone.objects.filter(phase__project=project, completed_at__isnull=False)
        .exclude(due_date=None)
        .select_related("phase")
    )
    rows = change_rows(project)
    return {
        "project": project.slug,
        **calibration(project, milestones, rows),
        "landings": landing_rows(project, milestones, rows),
    }
