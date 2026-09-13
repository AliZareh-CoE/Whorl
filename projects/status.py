"""A paste-ready status update (#482): the project's week as markdown for whoever asks
"how is it going?" — an advisor, a collaborator, a grant report, the owner's own log.

Built from the same helpers the overview uses (progress, the phase's health, the week
digest, the focus list, the manuscripts glance, the open questions), so the text and the
page never disagree. Plain markdown, short lines, nothing that needs Atlas to read.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone

DONE_HEADINGS = {
    "milestone": "Milestones",
    "paper_read": "Read",
    "paper_added": "Added to the library",
    "note": "Notes",
    "decision": "Decisions",
    "experiment": "Lab log",
    "hypothesis": "Hypotheses",
    "document": "Documents",
    "manuscript": "Manuscript events",
    "manuscript_compiled": None,  # compiles are rhythm, not news
}
DONE_ORDER = list(DONE_HEADINGS)
MAX_PER_KIND = 6


def _due(item: dict) -> str:
    days = item.get("days")
    if days is None:
        return ""
    if days < 0:
        return f"overdue {-days} d"
    if days == 0:
        return "due today"
    return f"due in {days} d"


def status_update(project, days: int = 7, today: date | None = None) -> dict:
    from plans import selectors
    from plans.focus import week_focus
    from plans.roadmap import project_roadmap
    from projects.overview import manuscripts_glance, open_questions, week_digest

    today = today or timezone.localdate()
    days = max(1, min(int(days), 90))
    since = today - timedelta(days=days)
    done, total, _ = selectors.project_progress(project)
    phase = selectors.current_phase(project)
    health = None
    if phase is not None:
        row = next((r for r in project_roadmap(project)["phases"] if r["id"] == phase.pk), None)
        health = row["label"] if row else None
    digest = week_digest(project, today=today, days=days)
    focus = week_focus(project, today=today)
    papers = manuscripts_glance(project, today=today)
    questions = [
        q for q in open_questions(project) if q["status"] in ("open", "partially_answered")
    ]

    lines: list[str] = [f"# {project.name} — status, {since.isoformat()} → {today.isoformat()}", ""]
    if phase is not None:
        phase_line = f"**Phase:** {phase.name}"
        if health:
            phase_line += f" ({health})"
        phase_line += f" · project {done}/{total} milestones"
        lines.append(phase_line)
    else:
        lines.append(f"**Plan:** no phases yet · {done}/{total} milestones")
    for m in papers:
        bits = [m["status"].replace("_", " ")]
        if m["target_venue"]:
            bits.append(f"at {m['target_venue']}")
        if m.get("clock") and m["clock"]["days"] >= 1:
            bits.append(m["clock"]["label"])
            if m["clock"].get("nudge", {}).get("due"):
                bits.append("a nudge to the editor is fair")
        if m.get("readiness"):
            r = m["readiness"]
            bits.append(
                "ready to submit"
                if r["ready"] and not r["warns"]
                else f"ready, {r['warns']} to look at"
                if r["ready"]
                else f"{r['fails']} blocking pre-flight item{'s' if r['fails'] != 1 else ''}"
            )
        if m["days"] is not None:
            bits.append(
                f"deadline in {m['days']} d" if m["days"] >= 0 else f"deadline {-m['days']} d ago"
            )
        lines.append(f"**Manuscript:** {m['title']} — {', '.join(bits)}")

    # what got done
    by_kind: dict[str, list[dict]] = {}
    for e in digest["items_all"]:
        by_kind.setdefault(e["kind"], []).append(e)
    lines += ["", f"## Done in the last {days} days"]
    any_done = False
    for kind in DONE_ORDER:
        heading = DONE_HEADINGS.get(kind)
        rows = by_kind.get(kind)
        if not heading or not rows:
            continue
        any_done = True
        lines.append(f"**{heading}**")
        for e in rows[:MAX_PER_KIND]:
            detail = e.get("detail") or ""
            tail = f" ({detail})" if kind in ("milestone", "experiment") and detail else ""
            lines.append(f"- {e['label']}{tail}")
        if len(rows) > MAX_PER_KIND:
            lines.append(f"- … and {len(rows) - MAX_PER_KIND} more")
    if not any_done:
        lines.append("- Nothing logged in this window.")

    # what is next
    nxt = focus["overdue"] + focus["due_this_week"] + focus["next_up"]
    lines += ["", "## Next"]
    if nxt:
        for item in nxt[:8]:
            where = item.get("phase") or ""
            due = _due(item)
            tail = " · ".join(x for x in (where, due) if x)
            lines.append(f"- {item['title']}" + (f" — {tail}" if tail else ""))
    else:
        lines.append("- Nothing scheduled — the plan needs its next milestones.")

    if questions:
        lines += ["", "## Open questions"]
        for q in questions[:5]:
            tag = " (partly answered)" if q["status"] == "partially_answered" else ""
            lines.append(f"- {q['question']}{tag}")

    blockers = [f"{i['title']} — overdue {-i['days']} d" for i in focus["overdue"] if i.get("days")]
    if phase is not None and phase.status == "blocked":
        blockers.insert(0, f"Phase *{phase.name}* is marked blocked")
    if blockers:
        lines += ["", "## Blockers"] + [f"- {b}" for b in blockers[:6]]

    return {
        "project": project.slug,
        "since": since.isoformat(),
        "until": today.isoformat(),
        "days": days,
        "markdown": "\n".join(lines).rstrip() + "\n",
        "done": sum(len(v) for k, v in by_kind.items() if DONE_HEADINGS.get(k)),
        "next": len(nxt),
        "blockers": len(blockers),
    }
