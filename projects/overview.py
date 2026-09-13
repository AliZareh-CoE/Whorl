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
    # bodies=False (#444): the digest lists events; rendering every body here made the
    # overview pay for the whole timeline's markdown
    events = [e for e in project_timeline(project, bodies=False) if e["date"] >= since]
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


WORKING = ("outlining", "drafting", "internal_review", "revision")  # #479: pre-flight shown


def manuscripts_glance(project, today: date | None = None, limit: int = 4) -> list[dict]:
    from writing.budget import budget
    from writing.clock import WAITING, nudge, status_clock, venue_turnaround
    from writing.preflight import preflight

    today = today or timezone.localdate()
    live = [
        m
        for m in project.manuscripts.prefetch_related("events")
        if m.status not in ("published", "shelved")
    ]
    live.sort(key=lambda m: (m.deadline is None, m.deadline or today, m.pk))
    out = []
    turnarounds: dict[str, dict] = {}
    for m in live[:limit]:
        b = budget(m) if m.venue_limits else None
        # #479: what the studio knows — the clock (and whether a nudge is fair) for a paper
        # that waits on a venue, the pre-flight verdict for a paper being worked on
        clock = status_clock(m, today)
        if m.status in WAITING:
            key = m.target_venue.strip().lower()
            if key not in turnarounds:
                turnarounds[key] = venue_turnaround(m.target_venue)
            clock["nudge"] = nudge(m, clock, today, turnarounds[key])
        readiness = None
        if m.status in WORKING:
            r = preflight(m)
            readiness = {
                "ready": r["ready"],
                "fails": r["fails"],
                "warns": r["warns"],
                "summary": r["summary"],
            }
        out.append(
            {
                "id": m.pk,
                "title": m.title,
                "status": m.status,
                "deadline": m.deadline,
                "days": (m.deadline - today).days if m.deadline else None,
                "target_venue": m.target_venue,
                "over": b["over"] if b else [],
                "clock": clock,
                "readiness": readiness,
            }
        )
    return out


def literature_glance(project, today: date | None = None) -> dict:
    """#480: the project's reading state at a glance — how much is unread (and how much of
    that is high priority), what was read this month, the next paper up (highest priority,
    oldest first — the reading queue's own order) and the last paper added."""
    today = today or timezone.localdate()
    links = list(project.project_references.select_related("reference").order_by("created_at"))
    by_status: dict[str, int] = {}
    for link in links:
        by_status[link.reading_status] = by_status.get(link.reading_status, 0) + 1
    unread = [link for link in links if link.reading_status == "to_read"]
    high = [link for link in unread if link.priority == "high"]
    month_start = today.replace(day=1)
    read_this_month = sum(
        1
        for link in links
        if link.reading_status in ("read", "annotated") and link.updated_at.date() >= month_start
    )
    rank = {"high": 0, "normal": 1, "low": 2}
    queue = sorted(unread, key=lambda link: (rank.get(link.priority, 1), link.created_at))

    def _row(link):
        r = link.reference
        return {
            "id": r.pk,
            "title": r.title,
            "year": r.year,
            "priority": link.priority,
            "first_author": (r.authors[0].get("family") if r.authors else "") or "",
        }

    return {
        "total": len(links),
        "by_status": by_status,
        "to_read": len(unread),
        "high_priority_unread": len(high),
        "read_this_month": read_this_month,
        "next_up": _row(queue[0]) if queue else None,
        "last_added": _row(links[-1]) if links else None,
    }


QUIET_LAB_DAYS = 14  # #481: a lab log with no entry for two weeks is worth a nudge


def _note_row(note, today: date) -> dict:
    day = timezone.localtime(note.updated_at).date()
    return {
        "id": note.pk,
        "title": note.title,
        "updated": day.isoformat(),
        "days": (today - day).days,
    }


def notebook_glance(project, today: date | None = None) -> dict:
    """#481: the writing-for-yourself state — notes (how many, edited this week, how many
    sit unlinked, the last one touched), the lab log (entries, this month, the last entry
    and how long ago, quiet when nothing was logged for two weeks) and the datasets."""
    from notes.models import NoteLink

    today = today or timezone.localdate()
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)
    notes = list(project.notes.only("id", "title", "updated_at").order_by("-updated_at", "-id"))
    linked: set[int] = set()
    for src, dst in NoteLink.objects.filter(source__project=project).values_list(
        "source_id", "target_id"
    ):
        linked.add(src)
        linked.add(dst)
    last_note = notes[0] if notes else None
    entries = list(
        project.experiment_entries.only("id", "date", "title").order_by("-date", "-created_at")
    )
    last_entry = entries[0] if entries else None
    quiet_days = (today - last_entry.date).days if last_entry else None
    return {
        "notes": {
            "total": len(notes),
            "edited_this_week": sum(
                1 for n in notes if timezone.localtime(n.updated_at).date() >= week_ago
            ),
            "unlinked": sum(1 for n in notes if n.pk not in linked),
            "last_edited": _note_row(last_note, today) if last_note else None,
            "recent": [_note_row(n, today) for n in notes[:3]],
        },
        "experiments": {
            "total": len(entries),
            "this_month": sum(1 for e in entries if e.date >= month_start),
            "last": {
                "id": last_entry.pk,
                "title": last_entry.title,
                "date": last_entry.date.isoformat(),
                "days": quiet_days,
            }
            if last_entry
            else None,
            "quiet": bool(last_entry) and quiet_days >= QUIET_LAB_DAYS,
        },
        "datasets": {"total": project.datasets.count()},
    }


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
