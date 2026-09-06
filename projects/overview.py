"""Overview v2 extras: the week digest, open questions, manuscripts at a glance, hypotheses."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from django.utils import timezone

DIGEST_LABELS = {
    "milestone": "milestones done",
    "paper_added": "papers added",
    "paper_read": "papers read",
    "note": "notes",
    "decision": "decisions",
    "experiment": "experiments",
    "hypothesis": "hypotheses",
    "document": "documents",
    "manuscript": "manuscript events",
    "manuscript_compiled": "compiles",
}


def week_digest(project, today: date | None = None, days: int = 7) -> dict:
    """What happened in the last `days` days: counts per kind and the newest items."""
    from core.timeline import project_timeline

    today = today or timezone.localdate()
    since = (today - timedelta(days=days)).isoformat()
    events = [e for e in project_timeline(project) if e["date"] >= since]
    counts = Counter(e["kind"] for e in events)
    return {
        "since": since,
        "total": len(events),
        "counts": [
            {"kind": kind, "label": DIGEST_LABELS.get(kind, kind), "count": n}
            for kind, n in counts.most_common()
        ],
        "items": events[:6],
    }


def open_questions(project, limit: int = 6) -> list[dict]:
    order = {"open": 0, "partially_answered": 1, "answered": 2, "abandoned": 3}
    rows = sorted(project.questions.all(), key=lambda q: (order.get(q.status, 9), -q.pk))
    return [
        {
            "id": q.pk,
            "question": q.question,
            "status": q.status,
            "phases": [p.name for p in q.phases.all()],
        }
        for q in rows[:limit]
    ]


def manuscripts_glance(project, today: date | None = None, limit: int = 4) -> list[dict]:
    from writing.budget import budget

    today = today or timezone.localdate()
    live = [m for m in project.manuscripts.all() if m.status not in ("published", "shelved")]
    live.sort(key=lambda m: (m.deadline is None, m.deadline or today, m.pk))
    out = []
    for m in live[:limit]:
        b = budget(m) if m.venue_limits else None
        out.append(
            {
                "id": m.pk,
                "title": m.title,
                "status": m.status,
                "deadline": m.deadline,
                "days": (m.deadline - today).days if m.deadline else None,
                "target_venue": m.target_venue,
                "over": b["over"] if b else [],
            }
        )
    return out


def hypotheses_summary(project) -> dict:
    counts = Counter(project.hypotheses.values_list("status", flat=True))
    return {"total": sum(counts.values()), "by_status": dict(counts)}
