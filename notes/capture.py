"""Smart capture triage (Inbox v2 slice 1).

A captured line is rarely just text: it is a DOI to add, a URL to keep, a task for today, a note
to write, or a decision to record. `detect` reads the hints; `convert` turns the capture into the
first-class object in one call and marks it processed.
"""

from __future__ import annotations

import re
from datetime import UTC, date, timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from notes.when import parse_when

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
    when = parse_when(_title(text), timezone.localdate())  # #500: a date/time in the line
    return {
        "suggested": suggested,
        "doi": doi.group(1).rstrip(".,;)") if doi else "",
        "arxiv_id": arxiv.group(1) if arxiv else "",
        "url": url.group(0).rstrip(".,;)") if url else "",
        "title": _title(text),
        "due": when["date"].isoformat() if when["date"] else "",
        "due_time": when["time"].strftime("%H:%M") if when["time"] else "",
    }


def _zone(tz: str):
    """A tzinfo from an IANA name ("Europe/Berlin") or an offset ("+05:30"); the server's
    current zone otherwise."""
    import re as _re
    from datetime import timedelta as _td
    from datetime import timezone as _tz
    from zoneinfo import ZoneInfo

    tz = (tz or "").strip()
    if not tz:
        return timezone.get_current_timezone()
    m = _re.fullmatch(r"([+-])(\d{2}):?(\d{2})", tz)
    if m:
        sign = 1 if m.group(1) == "+" else -1
        return _tz(sign * _td(hours=int(m.group(2)), minutes=int(m.group(3))))
    try:
        return ZoneInfo(tz)
    except Exception:  # an unknown name: fall back rather than refuse the triage
        return timezone.get_current_timezone()


def due_instant(when: dict, tz: str = ""):
    """#500: the aware datetime a todo is due from a parsed {date, time}: the date at the
    time (today when only a time was written), or None. A date without a time is an all-day
    item (#546): local noon, the same shape the Today page writes for "on Friday"."""
    from datetime import datetime as _dt

    from core.todos import day_instant

    if not when["date"] and not when["time"]:
        return None
    zone = _zone(tz)
    if not when["time"]:
        return day_instant(when["date"], zone)
    day = when["date"] or _dt.now(zone).date()
    return _dt.combine(day, when["time"], tzinfo=zone)


SNOOZE_KEYWORDS = ("tomorrow", "monday", "next-week", "weekend")


def snooze_date(until: str | date | None, today: date | None = None) -> date | None:
    """#495: turn "tomorrow" / "monday" / "next-week" / "weekend" / an ISO date into the day
    the capture comes back; "" or None clears the snooze. Raises ValueError on anything else
    or on a day that is not in the future."""
    today = today or timezone.localdate()
    if until is None or until == "":
        return None
    if isinstance(until, date):
        day = until
    else:
        key = until.strip().lower().replace(" ", "-").replace("_", "-")
        if key == "tomorrow":
            day = today + timedelta(days=1)
        elif key in ("monday", "next-monday"):
            day = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
        elif key == "next-week":
            day = today + timedelta(days=7)
        elif key in ("weekend", "saturday"):
            day = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
        else:
            try:
                day = date.fromisoformat(key)
            except ValueError:
                raise ValueError(
                    "until must be tomorrow, monday, next-week, weekend or YYYY-MM-DD"
                ) from None
    if day <= today:
        raise ValueError("a snooze ends on a day after today")
    return day


def snooze(capture, until: str | date | None, today: date | None = None):
    """Park the capture until `until` (see snooze_date); "" wakes it. Returns the capture."""
    capture.snoozed_until = snooze_date(until, today)
    capture.save(update_fields=["snoozed_until", "updated_at"])
    return capture


def open_captures(queryset=None, today: date | None = None):
    """Untriaged captures that are due now: not processed and not snoozed past today."""
    from django.db.models import Q

    from notes.models import QuickCapture

    today = today or timezone.localdate()
    queryset = QuickCapture.objects.all() if queryset is None else queryset
    return queryset.filter(processed=False).filter(
        Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=today)
    )


def snoozed_captures(queryset=None, today: date | None = None):
    """Untriaged captures still asleep (snoozed past today), soonest first."""
    from notes.models import QuickCapture

    today = today or timezone.localdate()
    queryset = QuickCapture.objects.all() if queryset is None else queryset
    return queryset.filter(processed=False, snoozed_until__gt=today).order_by("snoozed_until")


MIN_SUGGEST_SCORE = 2  # #494: two matching terms (or one from the project's own name)
NAME_WEIGHT = 3


def _terms(text: str) -> set[str]:
    from core.keywords import ALL_STOPWORDS, WORD_RE

    out: set[str] = set()
    for w in WORD_RE.findall(text or ""):
        # a hyphenated word counts as itself and as its parts ("load-theory" → load, theory)
        for part in (w, *w.split("-")):
            part = part.lower()
            if len(part) >= 3 and part not in ALL_STOPWORDS:
                out.add(part)
    return out


def project_index(projects=None) -> list[dict]:
    """#494: one term set per planning/active project — its name (weighted), description,
    phase names, research questions, note titles, decision titles, paper titles and tags —
    built with one grouped query per source so the cost does not grow with projects."""
    from documents.models import Tag
    from literature.models import ProjectReference
    from notes.models import Note
    from plans.models import Phase, ResearchQuestion
    from projects.models import DecisionRecord, Project

    if projects is None:
        projects = list(
            Project.objects.filter(status__in=[Project.Status.PLANNING, Project.Status.ACTIVE])
        )
    ids = [p.pk for p in projects]
    rows = {
        p.pk: {
            "slug": p.slug,
            "name": p.name,
            "name_terms": _terms(p.name),
            "terms": _terms(p.description),
        }
        for p in projects
    }
    if not ids:
        return []
    sources = (
        Phase.objects.filter(project_id__in=ids).values_list("project_id", "name"),
        ResearchQuestion.objects.filter(project_id__in=ids).values_list("project_id", "question"),
        Note.objects.filter(project_id__in=ids).values_list("project_id", "title"),
        DecisionRecord.objects.filter(project_id__in=ids).values_list("project_id", "title"),
        Tag.objects.filter(project_id__in=ids).values_list("project_id", "name"),
        ProjectReference.objects.filter(project_id__in=ids)
        .order_by("-created_at")
        .values_list("project_id", "reference__title")[:2000],
    )
    for source in sources:
        for pid, text in source:
            rows[pid]["terms"] |= _terms(text)
    return list(rows.values())


def suggest_project(text: str, index: list[dict]) -> dict | None:
    """#494: the project whose vocabulary the capture shares most — a name word counts
    three, any other term one; needs at least MIN_SUGGEST_SCORE and a clear winner."""
    words = _terms(_title(text) + " " + (text or ""))
    if not words or len(index) < 1:
        return None
    scored = []
    for row in index:
        hits = sorted(words & (row["terms"] | row["name_terms"]))
        score = sum(NAME_WEIGHT if w in row["name_terms"] else 1 for w in hits)
        if score:
            scored.append((score, row, hits))
    if not scored:
        return None
    scored.sort(key=lambda t: -t[0])
    best = scored[0]
    if best[0] < MIN_SUGGEST_SCORE or (len(scored) > 1 and scored[1][0] == best[0]):
        return None
    return {"slug": best[1]["slug"], "name": best[1]["name"], "score": best[0], "terms": best[2]}


def _title(text: str) -> str:
    first = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    for pattern in (TODO_RE, DECISION_RE, NOTE_RE, MILESTONE_RE):
        first = pattern.sub("", first, count=1)
    return first[:300].strip() or "Untitled"


@transaction.atomic
def convert(
    capture, target: str, project=None, *, phase=None, due: date | None = None, tz: str = ""
) -> dict:
    """Turn a capture into a paper / note / todo / milestone / decision; mark it processed.
    #500: a date/time written into the line becomes a todo's due_at (in the caller's `tz`)
    or a milestone's due date (an explicit `due` wins), and leaves the title."""
    if target not in TARGETS:
        raise ValueError(f"target must be one of {TARGETS}")
    hints = detect(capture.text)
    when = parse_when(hints["title"], timezone.localdate())
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
        # #499: a capture that is just a link takes the page's title, once it is known
        if capture.link_title and hints["url"] and capture.text.strip() == hints["url"]:
            title = capture.link_title[:300]
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
            text=(when["text"].splitlines()[0] if when["text"].strip() else hints["title"])[:300],
            project=project,
            position=(last or 0) + 1,
            due_at=due_instant(when, tz),
            all_day=bool(when["date"] and not when["time"]),
        )
        result = {
            "kind": "todo",
            "id": todo.pk,
            "title": todo.text,
            "app_url": "/today",
            "due_at": todo.due_at.astimezone(UTC).isoformat() if todo.due_at else None,
            "all_day": todo.all_day,
        }
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
            title=(when["text"].splitlines()[0] if when["text"].strip() else hints["title"])[:300],
            due_date=due or when["date"],
            notes=capture.text.strip() if "\n" in capture.text.strip() else "",
        )
        result = {
            "kind": "milestone",
            "id": milestone.pk,
            "title": milestone.title,
            "phase": phase.name,
            "app_url": f"/projects/{project.slug}/plan",
            "due_date": milestone.due_date.isoformat() if milestone.due_date else None,
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
    capture.became_kind = result["kind"]
    capture.became_id = result["id"]
    capture.triaged_at = timezone.now()
    if project is not None:
        capture.project = project
    capture.save(
        update_fields=[
            "processed",
            "became_kind",
            "became_id",
            "triaged_at",
            "project",
            "updated_at",
        ]
    )
    return result


BULK_ACTIONS = ("file", "dismiss", "snooze", "todo", "wake")
BULK_LIMIT = 200


def bulk_triage(ids, action: str, project=None, until: str | None = None) -> dict:
    """#497: one motion over many captures — file under a project, dismiss, snooze until a
    day, wake, or turn each into a Today item. Only untriaged captures in `ids` are touched;
    returns {action, count, ids} with the ids actually changed."""
    from notes.models import QuickCapture

    if action not in BULK_ACTIONS:
        raise ValueError(f"action must be one of {BULK_ACTIONS}")
    ids = [int(i) for i in list(ids)[:BULK_LIMIT]]
    if action == "file" and project is None:
        raise ValueError("filing needs a project")
    captures = list(QuickCapture.objects.filter(pk__in=ids, processed=False).order_by("pk"))
    now = timezone.now()
    done: list[int] = []
    with transaction.atomic():
        if action == "snooze":
            day = snooze_date(until or "tomorrow")
            for c in captures:
                c.snoozed_until = day
                c.save(update_fields=["snoozed_until", "updated_at"])
                done.append(c.pk)
        elif action == "wake":
            for c in captures:
                if c.snoozed_until is not None:
                    c.snoozed_until = None
                    c.save(update_fields=["snoozed_until", "updated_at"])
                    done.append(c.pk)
        elif action == "todo":
            for c in captures:
                convert(c, "todo", project)
                done.append(c.pk)
        else:
            for c in captures:
                c.processed = True
                c.triaged_at = now
                if action == "file":
                    c.project = project
                c.save(update_fields=["processed", "triaged_at", "project", "updated_at"])
                done.append(c.pk)
    return {"action": action, "count": len(done), "ids": done}


BECAME_KINDS = ("reference", "note", "todo", "milestone", "decision")
HISTORY_LIMIT = 30


def _became_url(kind: str, obj_id: int, slug: str | None) -> str:
    if kind == "reference":
        return f"/references/{obj_id}"
    if kind == "todo":
        return "/today"
    if not slug:
        return "/inbox"
    if kind == "note":
        return f"/projects/{slug}/notes/{obj_id}"
    if kind == "milestone":
        return f"/projects/{slug}/plan"
    return f"/projects/{slug}/decisions?id={obj_id}"


def became(capture) -> dict | None:
    """#496: {kind, id, app_url} for a converted capture (no title — see triage_history for
    the resolved objects), None for one that was filed or dismissed."""
    if not capture.became_kind or capture.became_id is None:
        return None
    slug = capture.project.slug if capture.project_id else None
    return {
        "kind": capture.became_kind,
        "id": capture.became_id,
        "app_url": _became_url(capture.became_kind, capture.became_id, slug),
    }


def _resolve_became(captures) -> dict[tuple[str, int], str]:
    """Titles of the objects a batch of captures became — one query per kind, not per row."""
    from core.models import TodoItem
    from literature.models import Reference
    from notes.models import Note
    from plans.models import Milestone
    from projects.models import DecisionRecord

    wanted: dict[str, set[int]] = {}
    for c in captures:
        if c.became_kind in BECAME_KINDS and c.became_id is not None:
            wanted.setdefault(c.became_kind, set()).add(c.became_id)
    models = {
        "reference": (Reference, "title"),
        "note": (Note, "title"),
        "todo": (TodoItem, "text"),
        "milestone": (Milestone, "title"),
        "decision": (DecisionRecord, "title"),
    }
    titles: dict[tuple[str, int], str] = {}
    for kind, ids in wanted.items():
        model, field = models[kind]
        # #570: a todo that went to the Trash still has a title — it is not "missing"
        manager = getattr(model, "all_objects", model.objects)
        for pk, title in manager.filter(pk__in=ids).values_list("pk", field):
            titles[(kind, pk)] = title
    return titles


def triage_history(limit: int = HISTORY_LIMIT) -> list[dict]:
    """#496: the last `limit` captures that left the inbox, newest first — each with its
    outcome ("converted" with what it became and whether that object still exists, "filed"
    under a project, or "dismissed")."""
    from notes.models import QuickCapture

    limit = max(1, min(int(limit), 200))
    rows = list(
        QuickCapture.objects.filter(processed=True)
        .select_related("project")
        .order_by(F("triaged_at").desc(nulls_last=True), "-updated_at", "-id")[:limit]
    )
    titles = _resolve_became(rows)
    out = []
    for c in rows:
        made = became(c)
        if made is not None:
            key = (c.became_kind, c.became_id)
            made["title"] = titles.get(key, "")
            made["exists"] = key in titles
            outcome = "converted"
        else:
            outcome = "filed" if c.project_id else "dismissed"
        out.append(
            {
                "id": c.pk,
                "text": c.text,
                "project": c.project.slug if c.project_id else None,
                "project_name": c.project.name if c.project_id else "",
                "outcome": outcome,
                "became": made,
                "triaged_at": (c.triaged_at or c.updated_at).isoformat(),
                "created_at": c.created_at.isoformat(),
            }
        )
    return out
