"""Smart capture triage (Inbox v2 slice 1).

A captured line is rarely just text: it is a DOI to add, a URL to keep, a task for today, a note
to write, or a decision to record. `detect` reads the hints; `convert` turns the capture into the
first-class object in one call and marks it processed.
"""

from __future__ import annotations

import re
from datetime import date

from django.db import transaction
from django.utils import timezone

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
ARXIV_RE = re.compile(r"(?:arxiv[:\s/]*(?:abs/)?|\b)(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
TODO_RE = re.compile(r"^\s*(?:todo|to do|task)\s*[:\-]\s*", re.IGNORECASE)
DECISION_RE = re.compile(r"^\s*(?:decision|decided|decide)\s*[:\-]\s*", re.IGNORECASE)
NOTE_RE = re.compile(r"^\s*(?:note|idea)\s*[:\-]\s*", re.IGNORECASE)
MILESTONE_RE = re.compile(r"^\s*(?:milestone|ms)\s*[:\-]\s*", re.IGNORECASE)
TARGETS = ("paper", "note", "todo", "milestone", "decision")


def detect(text: str) -> dict:
    """{suggested, doi, arxiv_id, url, title} — the cheapest useful read of a capture."""
    text = (text or "").strip()
    doi = DOI_RE.search(text)
    arxiv = ARXIV_RE.search(text)
    url = URL_RE.search(text)
    if doi or arxiv:
        suggested = "paper"
    elif TODO_RE.match(text):
        suggested = "todo"
    elif DECISION_RE.match(text):
        suggested = "decision"
    elif MILESTONE_RE.match(text):
        suggested = "milestone"
    elif NOTE_RE.match(text) or len(text) > 240 or "\n" in text:
        suggested = "note"
    else:
        suggested = "todo"
    return {
        "suggested": suggested,
        "doi": doi.group(1).rstrip(".,;)") if doi else "",
        "arxiv_id": arxiv.group(1) if arxiv else "",
        "url": url.group(0).rstrip(".,;)") if url else "",
        "title": _title(text),
    }


def _title(text: str) -> str:
    first = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    for pattern in (TODO_RE, DECISION_RE, NOTE_RE, MILESTONE_RE):
        first = pattern.sub("", first, count=1)
    return first[:300].strip() or "Untitled"


@transaction.atomic
def convert(capture, target: str, project=None, *, phase=None, due: date | None = None) -> dict:
    """Turn a capture into a paper / note / todo / milestone / decision; mark it processed."""
    if target not in TARGETS:
        raise ValueError(f"target must be one of {TARGETS}")
    hints = detect(capture.text)
    if target in ("note", "milestone", "decision") and project is None:
        raise ValueError(f"a {target} needs a project")
    if target == "paper":
        from literature.models import ProjectReference
        from literature.services import add_reference_by_identifier

        identifier = hints["doi"] or hints["arxiv_id"]
        if not identifier:
            raise ValueError("no DOI or arXiv id found in the capture")
        reference, created = add_reference_by_identifier(identifier)
        if project is not None:
            ProjectReference.objects.get_or_create(project=project, reference=reference)
        result = {
            "kind": "reference",
            "id": reference.pk,
            "title": reference.title,
            "created": created,
            "app_url": f"/references/{reference.pk}",
        }
    elif target == "note":
        from notes.models import Note
        from notes.services import sync_note_links, sync_note_references

        title = hints["title"]
        base, k = title, 2
        while project.notes.filter(title__iexact=title).exists():
            title = f"{base} ({k})"
            k += 1
        body = capture.text.strip()
        if hints["url"] and hints["url"] not in body:
            body += f"\n\n{hints['url']}"
        note = Note.objects.create(project=project, title=title, body=body)
        sync_note_links(note)
        sync_note_references(note)
        result = {
            "kind": "note",
            "id": note.pk,
            "title": note.title,
            "app_url": f"/projects/{project.slug}/notes/{note.pk}",
        }
    elif target == "todo":
        from core.models import TodoItem

        last = TodoItem.objects.order_by("-position").values_list("position", flat=True).first()
        todo = TodoItem.objects.create(
            text=hints["title"][:300], project=project, position=(last or 0) + 1
        )
        result = {"kind": "todo", "id": todo.pk, "title": todo.text, "app_url": "/today"}
    elif target == "milestone":
        from plans.models import Milestone, Phase

        if phase is None:
            from plans.selectors import current_phase

            phase = current_phase(project)
        if phase is None:
            phase = Phase.objects.create(
                project=project, name="Backlog", order=(project.phases.count() + 1)
            )
        milestone = Milestone.objects.create(
            phase=phase,
            title=hints["title"],
            due_date=due,
            notes=capture.text.strip() if "\n" in capture.text.strip() else "",
        )
        result = {
            "kind": "milestone",
            "id": milestone.pk,
            "title": milestone.title,
            "phase": phase.name,
            "app_url": f"/projects/{project.slug}/plan",
        }
    else:
        from projects.models import DecisionRecord

        lines = capture.text.strip().splitlines()
        rest = "\n".join(lines[1:]).strip()
        decision = DecisionRecord.objects.create(
            project=project,
            title=hints["title"],
            decision=rest or hints["title"],
            decided_on=timezone.localdate(),
        )
        result = {
            "kind": "decision",
            "id": decision.pk,
            "title": decision.title,
            "app_url": f"/projects/{project.slug}/decisions",
        }
    capture.processed = True
    if project is not None:
        capture.project = project
    capture.save(update_fields=["processed", "project", "updated_at"])
    return result
