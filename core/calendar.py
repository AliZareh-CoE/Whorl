"""iCalendar (.ics) export of a project's deadlines (Backlog #9 — the calendar half).

A small, dependency-free RFC 5545 generator: it turns a project's milestone due dates and
manuscript deadlines into all-day VEVENTs so the owner can pull Atlas deadlines into any
calendar app or automation. Pure function (no request/ORM-write side effects) so it unit-tests
cleanly and the API action stays thin.
"""

from datetime import UTC, date

PRODID = "-//Atlas//Research PM//EN"


def _escape(text: str) -> str:
    """Escape a TEXT value per RFC 5545 §3.3.11 (backslash, comma, semicolon, newline)."""
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold a content line to <=75 octets with CRLF + leading space (RFC 5545 §3.1)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    chunks, start = [], 0
    # first chunk 75 octets, continuations 74 (the leading space counts toward the 75 limit)
    limit = 75
    while start < len(raw):
        end = min(start + limit, len(raw))
        # don't split a multi-byte char: back off until the next byte isn't a UTF-8 continuation
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1
        chunks.append(raw[start:end].decode("utf-8"))
        start = end
        limit = 74
    return "\r\n ".join(chunks)


def _event(uid: str, day: date, summary: str, dtstamp: str, done: bool = False) -> list[str]:
    return [
        "BEGIN:VEVENT",
        _fold(f"UID:{uid}"),
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
        _fold(f"SUMMARY:{_escape(summary)}"),
        f"STATUS:{'CONFIRMED' if done else 'TENTATIVE'}",
        "END:VEVENT",
    ]


def build_ics(projects, now=None, name: str = "Atlas — deadlines") -> str:
    """One VCALENDAR across ``projects`` (milestones + manuscript deadlines), for a calendar
    app's "subscribe by URL". Backlog #9, served at /api/v1/calendar.ics (2026-09-06)."""
    from django.utils import timezone

    from plans.models import Milestone
    from writing.models import Manuscript

    now = now or timezone.now()
    dtstamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    projects = list(projects)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _fold(f"X-WR-CALNAME:{_escape(name)}"),
    ]
    milestones = (
        Milestone.objects.filter(phase__project__in=projects, due_date__isnull=False)
        .select_related("phase__project")
        .order_by("due_date", "pk")
    )
    for m in milestones:
        check = "✓ " if m.completed_at else ""
        lines += _event(
            f"milestone-{m.pk}@atlas",
            m.due_date,
            f"{check}{m.phase.project.name}: {m.title}",
            dtstamp,
            done=bool(m.completed_at),
        )
    for ms in Manuscript.objects.filter(project__in=projects, deadline__isnull=False).order_by(
        "deadline", "pk"
    ):
        lines += _event(f"manuscript-{ms.pk}@atlas", ms.deadline, f"Deadline: {ms.title}", dtstamp)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def build_project_ics(project, now=None) -> str:
    """Return a VCALENDAR string of the project's milestone + manuscript deadlines."""
    from django.utils import timezone

    from plans.models import Milestone
    from writing.models import Manuscript

    now = now or timezone.now()
    dtstamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _fold(f"X-WR-CALNAME:Atlas — {_escape(project.name)}"),
    ]

    milestones = (
        Milestone.objects.filter(phase__project=project, due_date__isnull=False)
        .select_related("phase")
        .order_by("due_date", "pk")
    )
    for m in milestones:
        check = "✓ " if m.completed_at else ""
        lines += _event(
            f"milestone-{m.pk}@atlas",
            m.due_date,
            f"{check}Milestone: {m.title}",
            dtstamp,
            done=bool(m.completed_at),
        )

    manuscripts = Manuscript.objects.filter(project=project, deadline__isnull=False).order_by(
        "deadline", "pk"
    )
    for ms in manuscripts:
        lines += _event(
            f"manuscript-{ms.pk}@atlas",
            ms.deadline,
            f"Deadline: {ms.title}",
            dtstamp,
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
