"""The daily brief (#491): the dashboard as a paste-ready markdown note.

The cross-project twin of the project status update (#482): what needs you, what is on
your list, what is due this week everywhere, what to read next, every live paper, each
active project with its rhythm, and this month's numbers against last month — from the
same helpers the dashboard renders, so the note and the page never disagree.
"""

from __future__ import annotations

import datetime

from django.utils import timezone

MAX_ROWS = 8


def _due(days: int) -> str:
    if days < 0:
        return f"overdue {-days} d"
    if days == 0:
        return "due today"
    return f"due in {days} d"


def daily_brief(today: datetime.date | None = None) -> dict:
    from core.backups import backup_status
    from core.dashboard import (
        active_projects,
        monthly_stats,
        needs_attention,
        pulses_everywhere,
        quiet_projects,
        reading_queue_everywhere,
        stats_trend,
        week_everywhere,
        writing_everywhere,
    )
    from core.models import TodoItem
    from writing.clock import waiting_manuscripts

    today = today or timezone.localdate()
    attention = needs_attention(today=today)
    waiting = waiting_manuscripts(today)
    active = active_projects()
    pulses = pulses_everywhere([r["project"] for r in active], today=today)
    quiet = quiet_projects(active, pulses)
    backup = backup_status()
    todos = list(
        TodoItem.objects.filter(done=False)
        .select_related("project")
        .order_by("position", "id")[:MAX_ROWS]
    )
    week = week_everywhere(today=today)
    reading = reading_queue_everywhere(today=today, limit=5)
    writing = writing_everywhere(today=today, limit=6)
    stats = monthly_stats(today=today)
    trend = stats_trend(today=today)

    lines: list[str] = [f"# Brief — {today.strftime('%A, %B %-d')}", ""]

    # what needs you
    needs: list[str] = []
    for m in attention["overdue"]:
        needs.append(f"- Overdue: {m.title} ({m.phase.project.name}, due {m.due_date.isoformat()})")
    for ms in attention["deadlines"]:
        needs.append(
            f"- Deadline: {ms.title} ({ms.project.name}) in {ms.days_to_deadline} d "
            f"({ms.deadline.isoformat()})"
        )
    for w in waiting:
        needs.append(
            f"- Waiting: {w['title']} — {w['waited']} d at {w['venue'] or w['project']}, "
            f"usually {w['after_days']} — a nudge is fair"
        )
    for q in quiet:
        needs.append(f"- Quiet: {q['name']} — nothing logged for {q['quiet_weeks']} weeks")
    if attention["inbox"]:
        n = len(attention["inbox"])
        needs.append(f"- Inbox: {n} item{'s' if n != 1 else ''} to triage")
    if backup.get("stale") and backup.get("has_data"):
        last = backup.get("last")
        needs.append(
            f"- Backup: last one {last['days_ago']} days ago" if last else "- Backup: none yet"
        )
    lines += ["## Needs you"] + (needs or ["- Nothing — all clear."])

    if todos:
        lines += ["", "## On your list"]
        for t in todos:
            tail = f" · {t.project.name}" if t.project_id else ""
            lines.append(f"- [ ] {t.text}{tail}")

    items = week["overdue"] + week["due_this_week"]
    if items:
        lines += ["", "## This week, everywhere"]
        for i in items[:MAX_ROWS]:
            lines.append(f"- {i['title']} — {i['project_name']} · {_due(i['days'])}")

    if reading["next"]:
        lines += ["", f"## Next to read ({reading['to_read']} unread)"]
        for r in reading["next"]:
            who = " ".join(str(x) for x in (r["first_author"], r["year"]) if x)
            pri = " · high priority" if r["priority"] == "high" else ""
            lines.append(
                f"- {r['title']}" + (f" ({who})" if who else "") + f" — {r['project']}{pri}"
            )

    if writing["rows"]:
        lines += ["", f"## Writing ({writing['live']} live)"]
        for m in writing["rows"]:
            bits = [m["status"].replace("_", " "), m["project"]]
            if m["days"] is not None:
                bits.append(_due(m["days"]).replace("due", "deadline"))
            if m.get("clock") and m["clock"]["days"] >= 1:
                bits.append(m["clock"]["label"])
                if m["clock"].get("nudge", {}).get("due"):
                    bits.append("nudge?")
            if m.get("readiness"):
                r = m["readiness"]
                bits.append(
                    "ready to submit"
                    if r["ready"] and not r["warns"]
                    else f"ready, {r['warns']} to look at"
                    if r["ready"]
                    else f"{r['fails']} blocking"
                )
            lines.append(f"- {m['title']} — {' · '.join(bits)}")

    if active:
        lines += ["", "## Projects"]
        for row in active:
            p = row["project"]
            pulse = pulses.get(p.pk) or {}
            bits = [f"{row['done']}/{row['total']} milestones"]
            if row["phase"]:
                bits.insert(0, row["phase"].name)
            if pulse.get("quiet_weeks", 0) >= 3:
                bits.append(f"quiet {pulse['quiet_weeks']} wk")
            elif pulse.get("total"):
                bits.append(f"{pulse['total']} events in 12 wk")
            lines.append(f"- {p.name} — {' · '.join(bits)}")

    def delta(key: str) -> str:
        d = stats[key] - trend["previous"][key]
        return f"({'+' if d > 0 else ''}{d} vs last month)" if d else "(= last month)"

    lines += [
        "",
        "## This month",
        f"- {stats['papers_read']} papers read {delta('papers_read')}",
        f"- {stats['notes_written']} notes written {delta('notes_written')}",
        f"- {stats['milestones_done']} milestones done {delta('milestones_done')}",
        f"- {stats['experiments_logged']} lab entries {delta('experiments_logged')}",
        f"- {stats['words_written']} words written {delta('words_written')}",
    ]
    return {
        "date": today.isoformat(),
        "markdown": "\n".join(lines).rstrip() + "\n",
        "needs": len(needs),
        "todos": len(todos),
        "reading": len(reading["next"]),
        "writing": len(writing["rows"]),
    }
