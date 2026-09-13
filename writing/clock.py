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
WAITING = ("submitted", "under_review")
NUDGE_FACTOR = 1.5  # a nudge is fair once the wait passes 1.5× the venue's usual round
NUDGE_MIN_DAYS = 60  # ... but never before two months
NUDGE_DEFAULT_DAYS = 90  # with no history at the venue, three months
NUDGE_MARK = "nudge"  # a note event whose text mentions this restarts the count


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


def nudge(
    manuscript, clock: dict, today: date | None = None, turnaround: dict | None = None
) -> dict:
    """#475: is a polite note to the editor fair now? Only while the paper waits on the venue.
    The threshold is 1.5× your own median round at this venue (never under 60 days), or 90
    days when you have no history there. A logged nudge (a note event mentioning "nudge")
    restarts the count from its date, so the hint never nags."""
    today = today or date.today()
    if manuscript.status not in WAITING:
        return {"due": False, "after_days": None, "basis": None, "waited": None, "last": None}
    since = date.fromisoformat(clock["since"])
    last = None
    for e in manuscript.events.all():
        if e.kind == "note" and NUDGE_MARK in (e.notes or "").lower() and e.date >= since:
            if last is None or e.date > last:
                last = e.date
    start = last or since
    waited = max(0, (today - start).days)
    if turnaround is None:
        turnaround = venue_turnaround(manuscript.target_venue)
    median = turnaround.get("median_days") if turnaround else None
    if median:
        after = max(NUDGE_MIN_DAYS, int(round(median * NUDGE_FACTOR)))
        basis = f"1.5× your median of {median} d at {turnaround['venue']}"
    else:
        after = NUDGE_DEFAULT_DAYS
        basis = "no history at this venue yet — 90 d"
    return {
        "due": waited >= after,
        "after_days": after,
        "basis": basis,
        "waited": waited,
        "last": last.isoformat() if last else None,
    }


def waiting_manuscripts(today: date | None = None) -> list[dict]:
    """#475: every paper whose nudge is due, for the dashboard's needs-attention list."""
    from writing.models import Manuscript

    today = today or date.today()
    out = []
    cache: dict[str, dict] = {}
    qs = (
        Manuscript.objects.filter(status__in=WAITING)
        .select_related("project")
        .prefetch_related("events")
        .order_by("id")
    )
    for m in qs:
        key = m.target_venue.strip().lower()
        if key not in cache:
            cache[key] = venue_turnaround(m.target_venue)
        c = status_clock(m, today)
        n = nudge(m, c, today, cache[key])
        if n["due"]:
            out.append(
                {
                    "id": m.id,
                    "title": m.title,
                    "project": m.project.name,
                    "venue": m.target_venue,
                    "status": m.status,
                    "waited": n["waited"],
                    "after_days": n["after_days"],
                    "basis": n["basis"],
                    "url": f"/manuscripts/{m.id}",
                }
            )
    out.sort(key=lambda r: r["waited"] - r["after_days"], reverse=True)
    return out
