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


def themes(project, limit: int = 10) -> list[dict]:
    """Keyword chips for the overview (#398, backlog #41): the salient phrases across the
    project's papers (titles + abstracts), notes, decisions and questions, each weighted by
    how many of those sources carry it. Local extraction (core.keywords), no model."""
    from core.keywords import extract_keywords

    sources: list[str] = []
    for link in project.project_references.select_related("reference")[:400]:
        ref = link.reference
        sources.append(f"{ref.title}. {(ref.abstract or '')[:1500]}")
    sources += [f"{n.title}. {(n.body or '')[:1500]}" for n in project.notes.all()[:200]]
    sources += [f"{d.title}. {(d.decision or '')[:600]}" for d in project.decisions.all()[:100]]
    sources += [q.question for q in project.questions.all()[:100]]
    if not sources:
        return []
    corpus = "\n".join(sources)[:120_000]
    candidates = extract_keywords(corpus, max_keywords=limit * 3)
    lowered = [s.lower() for s in sources]
    rows = []
    for label in candidates:
        weight = sum(1 for text in lowered if label in text)
        if weight:
            rows.append({"label": label, "weight": weight})
    rows.sort(key=lambda r: (-r["weight"], r["label"]))
    return rows[:limit]
