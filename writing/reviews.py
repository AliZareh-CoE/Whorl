"""Reviewer-response tracker (Writing v2 slice 2).

Paste the reviews you received; Atlas splits them into numbered points per reviewer, logs a
`reviews_received` event, and writes a point-by-point response note (`- [ ] **R1.3** …` with a
"Response:" slot under each). Ticking the boxes in the note is the progress the studio shows.
"""

from __future__ import annotations

import re
from datetime import date

from django.utils import timezone

REVIEWER_RE = re.compile(
    r"^\s*(?:#+\s*)?(?:reviewer|referee|reviewer\s*comments?)\s*#?\s*([0-9]+|[A-Z])\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
POINT_RE = re.compile(r"^\s*(?:\(?\d+[\).:]|[-*•]|\[\d+\])\s+(.*\S)\s*$")
CHECK_RE = re.compile(r"^\s*- \[( |x|X)\] \*\*R", re.MULTILINE)


def parse_review_points(text: str) -> list[dict]:
    """[{reviewer, n, text}] — reviewers split on 'Reviewer N' headings; points on numbered or
    bulleted lines (a paragraph without markers becomes one point)."""
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    sections: list[tuple[str, str]] = []
    matches = list(REVIEWER_RE.finditer(text))
    if not matches:
        sections.append(("1", text))
    else:
        if text[: matches[0].start()].strip():
            sections.append(("1", text[: matches[0].start()]))
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((m.group(1).upper(), text[m.end() : end]))
    points: list[dict] = []
    for reviewer, body in sections:
        points.extend(_points_for(reviewer, body))
    return points


def _points_for(reviewer: str, body: str) -> list[dict]:
    out: list[dict] = []
    current: list[str] = []

    def flush() -> None:
        joined = " ".join(s.strip() for s in current if s.strip())
        if joined:
            out.append({"reviewer": reviewer, "n": len(out) + 1, "text": joined})
        current.clear()

    for line in body.split("\n"):
        pm = POINT_RE.match(line)
        if pm:
            flush()
            current.append(pm.group(1))
        elif not line.strip():
            flush()
        else:
            current.append(line)
    flush()
    return out


def response_markdown(manuscript, points: list[dict], received: date) -> str:
    lines = [
        f"Point-by-point response for *{manuscript.title}* — reviews received {received.isoformat()}.",
        "",
        "Tick a point when its response is final. Keep the reviewer's words; answer under each.",
        "",
    ]
    by_reviewer: dict[str, list[dict]] = {}
    for p in points:
        by_reviewer.setdefault(p["reviewer"], []).append(p)
    for reviewer, items in by_reviewer.items():
        lines += [f"## Reviewer {reviewer}", ""]
        for p in items:
            lines += [f"- [ ] **R{reviewer}.{p['n']}** {p['text']}", "  > Response: ", ""]
    if not points:
        lines += ["## Reviewer 1", "", "- [ ] **R1.1** ", "  > Response: ", ""]
    return "\n".join(lines).rstrip() + "\n"


def log_reviews(manuscript, text: str, received: date | None = None, notes: str = ""):
    """Create the reviews_received event and the response note. Returns (event, note, points)."""
    from notes.models import Note
    from notes.services import sync_note_links, sync_note_references

    from .models import SubmissionEvent

    received = received or timezone.localdate()
    points = parse_review_points(text)
    title = f"Response to reviewers — {manuscript.title[:60]} ({received.isoformat()})"
    base, k = title, 2
    while manuscript.project.notes.filter(title__iexact=title).exists():
        title = f"{base} ({k})"
        k += 1
    note = Note.objects.create(
        project=manuscript.project,
        title=title,
        body=response_markdown(manuscript, points, received),
    )
    sync_note_links(note)
    sync_note_references(note)
    summary = (
        notes.strip()
        or f"{len(points)} point(s) from {len({p['reviewer'] for p in points}) or 1} reviewer(s)"
    )
    event = SubmissionEvent.objects.create(
        manuscript=manuscript,
        kind=SubmissionEvent.Kind.REVIEWS_RECEIVED,
        date=received,
        notes=f"{summary} → [[{note.title}]]",
    )
    return event, note, points


def response_progress(manuscript) -> dict | None:
    """{note_id, title, done, total, percent} from the newest response note, or None."""
    note = (
        manuscript.project.notes.filter(
            title__istartswith=f"Response to reviewers — {manuscript.title[:60]}"
        )
        .order_by("-created_at")
        .first()
    )
    if note is None:
        return None
    boxes = CHECK_RE.findall(note.body or "")
    total = len(boxes)
    done = sum(1 for b in boxes if b.lower() == "x")
    return {
        "note_id": note.pk,
        "title": note.title,
        "done": done,
        "total": total,
        "percent": round(100 * done / total) if total else 0,
        "app_url": f"/projects/{manuscript.project.slug}/notes/{note.pk}",
    }
