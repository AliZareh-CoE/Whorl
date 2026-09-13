"""Status clock (#474): how long a paper has sat where it is, and how long this venue takes.

``status_clock`` reads the submission timeline: *under review* counts from the last
``submitted`` / ``revision_submitted`` event, *revision* from ``reviews_received``,
*submitted* from ``submitted``, *accepted* / *published* from their events; every other
status counts from the manuscript's last change. ``venue_turnaround`` looks across the
owner's manuscripts at the same venue and reports the median days from a submission to the
next decision (reviews received, desk reject, accepted or rejected) — the number every
author wants when the inbox stays quiet.
"""

from __future__ import annotations

import statistics
from datetime import date

STATUS_EVENTS = {
    "submitted": ("submitted",),
    "under_review": ("revision_submitted", "submitted"),
    "revision": ("reviews_received",),
    "accepted": ("accepted",),
    "published": ("published",),
}
STATUS_PHRASE = {
    "idea": "as an idea",
    "outlining": "outlining",
    "drafting": "drafting",
    "internal_review": "in internal review",
    "submitted": "since submission",
    "under_review": "under review",
    "revision": "revising",
    "accepted": "since acceptance",
    "published": "published",
    "shelved": "shelved",
}
SUBMISSION_KINDS = ("submitted", "revision_submitted")
DECISION_KINDS = ("reviews_received", "desk_reject", "accepted", "rejected")


def status_clock(manuscript, today: date | None = None) -> dict:
    today = today or date.today()
    events = sorted(manuscript.events.all(), key=lambda e: (e.date, e.created_at), reverse=True)
    since = None
    source = "updated"
    for kind_set in (STATUS_EVENTS.get(manuscript.status),):
        if not kind_set:
            break
        for e in events:
            if e.kind in kind_set:
                since, source = e.date, e.kind
                break
    if since is None:
        since = manuscript.updated_at.date()
    days = max(0, (today - since).days)
    phrase = STATUS_PHRASE.get(manuscript.status, manuscript.status.replace("_", " "))
    return {
        "status": manuscript.status,
        "since": since.isoformat(),
        "days": days,
        "source": source,
        "label": f"{days} d {phrase}",
    }


def _rounds(events) -> list[tuple[str, int]]:
    """(kind of the submission that opened the round, days to the next decision)."""
    ordered = sorted(events, key=lambda e: (e.date, e.created_at))
    out: list[tuple[str, int]] = []
    open_kind, open_date = None, None
    for e in ordered:
        if e.kind in SUBMISSION_KINDS:
            open_kind, open_date = e.kind, e.date
        elif e.kind in DECISION_KINDS and open_date is not None:
            out.append((open_kind, (e.date - open_date).days))
            open_kind, open_date = None, None
    return out


def venue_turnaround(venue: str, exclude_id: int | None = None) -> dict:
    from writing.models import Manuscript

    venue = (venue or "").strip()
    empty = {
        "venue": venue,
        "manuscripts": 0,
        "rounds": 0,
        "median_days": None,
        "first_decision_median_days": None,
        "fastest_days": None,
        "slowest_days": None,
    }
    if not venue:
        return empty
    qs = Manuscript.objects.filter(target_venue__iexact=venue).prefetch_related("events")
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    rounds: list[tuple[str, int]] = []
    papers = 0
    for m in qs:
        r = _rounds(m.events.all())
        if r:
            papers += 1
            rounds.extend(r)
    if not rounds:
        return empty
    all_days = [d for _, d in rounds]
    first = [d for k, d in rounds if k == "submitted"]
    return {
        "venue": venue,
        "manuscripts": papers,
        "rounds": len(rounds),
        "median_days": int(statistics.median(all_days)),
        "first_decision_median_days": int(statistics.median(first)) if first else None,
        "fastest_days": min(all_days),
        "slowest_days": max(all_days),
    }
