"""The plan as a document (Plan v2 slice 1).

A project's plan round-trips through a small Markdown outline so it can be written as fast as
a text file — in the SPA editor, from Claude through MCP, or in any editor and pasted back:

    # Literature review  [in_progress]  (2026-09-01 → 2026-10-15)  {#12}
    > Map the load-theory debate and pick the paradigm.
    - [ ] Annotated bibliography of 30 papers  (due 2026-09-20)  {#41}
      - [x] Pull the 2019–2024 citing papers  {#77}
      - [ ] Rate each paper on the review matrix
    - [x] Paradigm chosen

`{#id}` tokens are written by the exporter and let the parser keep ids (and so completion
timestamps, notes, links) across renames. Lines without an id create new objects; objects that
no longer appear are deleted — `preview()` reports all three before anything is written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.utils import timezone

from projects.models import Project

from .models import Milestone, Phase, Task

STATUS_ALIASES = {
    "not_started": Phase.Status.NOT_STARTED,
    "not started": Phase.Status.NOT_STARTED,
    "todo": Phase.Status.NOT_STARTED,
    "in_progress": Phase.Status.IN_PROGRESS,
    "in progress": Phase.Status.IN_PROGRESS,
    "active": Phase.Status.IN_PROGRESS,
    "blocked": Phase.Status.BLOCKED,
    "done": Phase.Status.DONE,
    "complete": Phase.Status.DONE,
    "completed": Phase.Status.DONE,
}

_ID = re.compile(r"\s*\{#(\d+)\}\s*$")
_STATUS = re.compile(r"\s*\[([a-z _]+)\]", re.IGNORECASE)
_RANGE = re.compile(r"\s*\((\d{4}-\d{2}-\d{2})?\s*(?:→|->|to|–)\s*(\d{4}-\d{2}-\d{2})?\)")
_DUE = re.compile(r"\s*\((?:due\s+)?(\d{4}-\d{2}-\d{2})\)", re.IGNORECASE)
_CHECK = re.compile(r"^(\s*)[-*+]\s+\[( |x|X)\]\s+(.*)$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")


class OutlineError(ValueError):
    """The outline could not be parsed; `errors` is [{line, message}]."""

    def __init__(self, errors: list[dict]):
        super().__init__("; ".join(f"line {e['line']}: {e['message']}" for e in errors))
        self.errors = errors


@dataclass
class TaskSpec:
    title: str
    done: bool = False
    due: date | None = None
    id: int | None = None
    line: int = 0


@dataclass
class MilestoneSpec:
    title: str
    done: bool = False
    due: date | None = None
    id: int | None = None
    line: int = 0
    tasks: list[TaskSpec] = field(default_factory=list)


@dataclass
class PhaseSpec:
    name: str
    status: str = Phase.Status.NOT_STARTED
    start: date | None = None
    end: date | None = None
    objective: str = ""
    id: int | None = None
    line: int = 0
    milestones: list[MilestoneSpec] = field(default_factory=list)


# --- export -----------------------------------------------------------------------------


def _iso(d: date | None) -> str:
    return d.isoformat() if d else ""


def plan_to_markdown(project: Project) -> str:
    """The whole plan as the outline above (always with `{#id}` tokens)."""
    out: list[str] = []
    for phase in project.phases.prefetch_related("milestones__tasks"):
        head = f"# {phase.name}  [{phase.status}]"
        if phase.target_start or phase.target_end:
            head += f"  ({_iso(phase.target_start)} → {_iso(phase.target_end)})"
        out.append(f"{head}  {{#{phase.pk}}}")
        for line in phase.objective.strip().splitlines():
            out.append(f"> {line}")
        for m in phase.milestones.all():
            due = f"  (due {m.due_date.isoformat()})" if m.due_date else ""
            out.append(f"- [{'x' if m.completed_at else ' '}] {m.title}{due}  {{#{m.pk}}}")
            for t in m.tasks.all():
                due = f"  (due {t.due_date.isoformat()})" if t.due_date else ""
                out.append(f"  - [{'x' if t.done else ' '}] {t.title}{due}  {{#{t.pk}}}")
        out.append("")
    return "\n".join(out).rstrip() + ("\n" if out else "")


# --- parse ------------------------------------------------------------------------------


def _pull_id(text: str) -> tuple[str, int | None]:
    m = _ID.search(text)
    return (text[: m.start()].rstrip(), int(m.group(1))) if m else (text.strip(), None)


def _parse_date(raw: str, line: int, errors: list[dict]) -> date | None:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        errors.append({"line": line, "message": f"'{raw}' is not a date (use YYYY-MM-DD)."})
        return None


def parse_outline(text: str) -> list[PhaseSpec]:
    """Parse the outline; raises OutlineError listing every problem with its line number."""
    phases: list[PhaseSpec] = []
    errors: list[dict] = []
    current_phase: PhaseSpec | None = None
    current_milestone: MilestoneSpec | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        if raw.lstrip().startswith("#"):
            body, pk = _pull_id(raw.lstrip().lstrip("#").strip())
            status = Phase.Status.NOT_STARTED
            sm = _STATUS.search(body)
            if sm:
                key = sm.group(1).strip().lower()
                if key in STATUS_ALIASES:
                    status = STATUS_ALIASES[key]
                    body = body[: sm.start()] + body[sm.end() :]
                else:
                    errors.append(
                        {"line": number, "message": f"unknown phase status '[{sm.group(1)}]'."}
                    )
            start = end = None
            rm = _RANGE.search(body)
            if rm:
                start = _parse_date(rm.group(1), number, errors) if rm.group(1) else None
                end = _parse_date(rm.group(2), number, errors) if rm.group(2) else None
                body = body[: rm.start()] + body[rm.end() :]
            name = " ".join(body.split())
            if not name:
                errors.append({"line": number, "message": "a phase needs a name after '#'."})
            current_phase = PhaseSpec(
                name=name, status=status, start=start, end=end, id=pk, line=number
            )
            current_milestone = None
            phases.append(current_phase)
            continue
        if raw.lstrip().startswith(">"):
            if current_phase is None:
                errors.append({"line": number, "message": "objective text before any phase."})
                continue
            line = raw.lstrip()[1:].strip()
            current_phase.objective = (current_phase.objective + "\n" + line).strip()
            continue
        cm = _CHECK.match(raw) or _BULLET.match(raw)
        if not cm:
            errors.append(
                {
                    "line": number,
                    "message": "expected '# phase', '> objective', '- [ ] milestone' "
                    "or an indented '- [ ] task'.",
                }
            )
            continue
        indent = len(cm.group(1).replace("\t", "  "))
        if cm.re is _CHECK:
            done, body = cm.group(2).lower() == "x", cm.group(3)
        else:
            done, body = False, cm.group(2)
        body, pk = _pull_id(body)
        due = None
        dm = _DUE.search(body)
        if dm:
            due = _parse_date(dm.group(1), number, errors)
            body = body[: dm.start()] + body[dm.end() :]
        title = " ".join(body.split())
        if not title:
            errors.append({"line": number, "message": "an item needs a title."})
            continue
        if current_phase is None:
            errors.append({"line": number, "message": "milestones must come under a '# phase'."})
            continue
        if indent >= 2 and current_milestone is not None:
            current_milestone.tasks.append(
                TaskSpec(title=title, done=done, due=due, id=pk, line=number)
            )
        else:
            current_milestone = MilestoneSpec(title=title, done=done, due=due, id=pk, line=number)
            current_phase.milestones.append(current_milestone)
    if errors:
        raise OutlineError(errors)
    return phases


# --- diff + apply -----------------------------------------------------------------------


def _existing(project: Project):
    phases = {p.pk: p for p in project.phases.all()}
    milestones = {m.pk: m for m in Milestone.objects.filter(phase__project=project)}
    tasks = {t.pk: t for t in Task.objects.filter(milestone__phase__project=project)}
    return phases, milestones, tasks


def preview(project: Project, text: str) -> dict:
    """What `apply()` would do: counts + names of created / updated / deleted objects."""
    specs = parse_outline(text)
    phases, milestones, tasks = _existing(project)
    seen_p: set[int] = set()
    seen_m: set[int] = set()
    seen_t: set[int] = set()
    created: list[str] = []
    renamed: list[str] = []
    for ps in specs:
        if ps.id in phases:
            seen_p.add(ps.id)
            if phases[ps.id].name != ps.name:
                renamed.append(f"phase “{phases[ps.id].name}” → “{ps.name}”")
        else:
            created.append(f"phase “{ps.name}”")
        for ms in ps.milestones:
            if ms.id in milestones:
                seen_m.add(ms.id)
                if milestones[ms.id].title != ms.title:
                    renamed.append(f"milestone “{milestones[ms.id].title}” → “{ms.title}”")
            else:
                created.append(f"milestone “{ms.title}”")
            for ts in ms.tasks:
                if ts.id in tasks:
                    seen_t.add(ts.id)
                    if tasks[ts.id].title != ts.title:
                        renamed.append(f"task “{tasks[ts.id].title}” → “{ts.title}”")
                else:
                    created.append(f"task “{ts.title}”")
    deleted = (
        [f"phase “{p.name}”" for pk, p in phases.items() if pk not in seen_p]
        + [
            f"milestone “{m.title}”"
            for pk, m in milestones.items()
            if pk not in seen_m and m.phase_id in seen_p
        ]
        + [
            f"task “{t.title}”"
            for pk, t in tasks.items()
            if pk not in seen_t and t.milestone_id in seen_m
        ]
    )
    return {
        "phases": len(specs),
        "milestones": sum(len(p.milestones) for p in specs),
        "tasks": sum(len(m.tasks) for p in specs for m in p.milestones),
        "created": created,
        "renamed": renamed,
        "deleted": deleted,
        "errors": [],
    }


@transaction.atomic
def apply(project: Project, text: str) -> dict:
    """Make the plan match the outline. Returns the same summary as `preview()`."""
    summary = preview(project, text)
    specs = parse_outline(text)
    phases, milestones, tasks = _existing(project)
    keep_p: set[int] = set()
    keep_m: set[int] = set()
    keep_t: set[int] = set()
    now = timezone.now()
    for order, ps in enumerate(specs, start=1):
        phase = phases.get(ps.id) if ps.id else None
        if phase is None:
            phase = Phase(project=project)
        phase.name = ps.name
        phase.order = order
        phase.status = ps.status
        phase.target_start = ps.start
        phase.target_end = ps.end
        phase.objective = ps.objective
        phase.save()
        keep_p.add(phase.pk)
        for ms in ps.milestones:
            milestone = milestones.get(ms.id) if ms.id else None
            if milestone is None or milestone.phase_id not in (phase.pk, *phases):
                milestone = Milestone(phase=phase)
            milestone.phase = phase
            milestone.title = ms.title
            milestone.due_date = ms.due
            if ms.done and not milestone.completed_at:
                milestone.completed_at = now
            elif not ms.done:
                milestone.completed_at = None
            milestone.save()
            keep_m.add(milestone.pk)
            for t_order, ts in enumerate(ms.tasks):
                task = tasks.get(ts.id) if ts.id else None
                if task is None:
                    task = Task(milestone=milestone)
                task.milestone = milestone
                task.title = ts.title
                task.done = ts.done
                task.due_date = ts.due
                task.order = t_order
                task.save()
                keep_t.add(task.pk)
    Task.objects.filter(milestone__phase__project=project).exclude(pk__in=keep_t).delete()
    Milestone.objects.filter(phase__project=project).exclude(pk__in=keep_m).delete()
    project.phases.exclude(pk__in=keep_p).delete()
    return summary
