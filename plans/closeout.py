"""#521 — phase close-out: the report card of a phase (planned vs actual window, how every
milestone landed, drift, moves, the questions it carried) and the act of closing it — status
→ done and a decision record that keeps the report and what the phase taught. A plan that
never looks back cannot calibrate; this is where the looking back is written down."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from projects.models import DecisionRecord

from .calibration import _median, bucket_of
from .drift import baseline_of, change_rows
from .models import Phase


def phase_report(phase: Phase, today: date | None = None) -> dict:
    """{id, name, status, objective, planned_start, planned_end, actual_end, overrun, counts
    {total, done, open, on_time}, median_late, drift, moves, milestones [{id, title, due_date,
    baseline, landed, late, late_first, moves, done}], questions [{id, question, status}],
    closable, markdown}. `planned_end` is the target end, else the last first-given date;
    `actual_end` the latest completion; `overrun` the days between them."""
    today = today or timezone.localdate()
    milestones = list(phase.milestones.select_related("phase").order_by("due_date", "pk"))
    moves = change_rows(phase.project)
    rows, lates = [], []
    baseline_end: date | None = None
    actual_end: date | None = None
    drift, move_count = 0, 0
    for m in milestones:
        changes = moves.get(m.pk, [])
        baseline = baseline_of(changes, m.due_date)
        landed = timezone.localtime(m.completed_at).date() if m.completed_at else None
        late = (landed - m.due_date).days if landed and m.due_date else None
        late_first = (landed - baseline).days if landed and baseline else None
        if late is not None:
            lates.append(late)
        if m.due_date is not None and baseline is not None:
            drift += (m.due_date - baseline).days
        move_count += len(changes)
        if baseline is not None:
            baseline_end = max(baseline_end or baseline, baseline)
        if landed is not None:
            actual_end = max(actual_end or landed, landed)
        rows.append(
            {
                "id": m.pk,
                "title": m.title,
                "due_date": m.due_date,
                "baseline": baseline,
                "landed": landed,
                "late": late,
                "late_first": late_first,
                "bucket": bucket_of(late) if late is not None else None,
                "moves": len(changes),
                "done": landed is not None,
            }
        )
    done = sum(1 for r in rows if r["done"])
    planned_end = phase.target_end or baseline_end
    overrun = (actual_end - planned_end).days if actual_end is not None and planned_end else None
    questions = [
        {"id": q.pk, "question": q.question, "status": q.status}
        for q in phase.questions.order_by("pk")
    ]
    report = {
        "id": phase.pk,
        "name": phase.name,
        "status": phase.status,
        "objective": phase.objective,
        "planned_start": phase.target_start,
        "planned_end": planned_end,
        "actual_end": actual_end,
        "overrun": overrun,
        "counts": {
            "total": len(rows),
            "done": done,
            "open": len(rows) - done,
            "on_time": sum(1 for late in lates if late <= 0),
        },
        "median_late": _median(lates),
        "drift": drift,
        "moves": move_count,
        "milestones": rows,
        "questions": questions,
        "closable": bool(rows) and done == len(rows) and phase.status != Phase.Status.DONE,
    }
    report["markdown"] = report_markdown(report)
    return report


def _days(n: int | None, late_word: str = "late", early_word: str = "early") -> str:
    if n is None:
        return "—"
    if n == 0:
        return "on the day"
    return f"{n} d {late_word}" if n > 0 else f"{-n} d {early_word}"


def report_markdown(report: dict) -> str:
    """The report as paste-ready Markdown — the context of the closing decision."""
    c = report["counts"]
    lines = [
        f"## Phase report — {report['name']}",
        "",
        f"- Milestones: {c['done']}/{c['total']} done, {c['on_time']} on time",
        f"- Planned end: {report['planned_end'] or '—'} · actual end: "
        f"{report['actual_end'] or '—'} · overrun: {_days(report['overrun'])}",
        f"- Landing: median {_days(report['median_late'])} · drift {report['drift']:+d} d over "
        f"{report['moves']} move{'s' if report['moves'] != 1 else ''}",
    ]
    if report["objective"]:
        lines += ["", f"> {report['objective']}"]
    if report["milestones"]:
        lines += [
            "",
            "| Milestone | first date | held date | landed | late |",
            "|---|---|---|---|---|",
        ]
        for m in report["milestones"]:
            lines.append(
                f"| {m['title']} | {m['baseline'] or '—'} | {m['due_date'] or '—'} | "
                f"{m['landed'] or 'open'} | {_days(m['late'])} |"
            )
    if report["questions"]:
        lines += ["", "Questions:"] + [
            f"- {q['question']} — {q['status'].replace('_', ' ')}" for q in report["questions"]
        ]
    return "\n".join(lines)


def close_phase(phase: Phase, lessons: str = "", today: date | None = None) -> dict:
    """Mark the phase done and file the report with the lessons as a decision record. Returns
    {report, decision_id}."""
    today = today or timezone.localdate()
    report = phase_report(phase, today)
    phase.status = Phase.Status.DONE
    phase.save(update_fields=["status", "updated_at"])
    c = report["counts"]
    decision = DecisionRecord.objects.create(
        project=phase.project,
        title=f"Phase closed: {phase.name}",
        context=report["markdown"],
        decision=lessons.strip()
        or f"Closed with {c['done']}/{c['total']} milestones done"
        + (
            f", {_days(report['overrun'], 'over', 'under')}"
            if report["overrun"] is not None
            else ""
        )
        + ".",
        decided_on=today,
    )
    report["status"] = phase.status
    report["closable"] = False
    return {"report": report, "decision_id": decision.pk}
