"""#512: milestone dependencies — "blocked by", the way Linear and Asana mean it.

A milestone is *blocked* while any milestone it depends on is not complete. Dependencies stay
inside one project, never point at themselves and never form a cycle; the plan payload and
the roadmap carry the flags from grouped queries so no page asks per row.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import Q

from .models import Milestone


class DependencyError(ValueError):
    """A dependency that must not exist; the message is user-readable."""


def _project_id(milestone: Milestone) -> int:
    return milestone.phase.project_id


def check_blockers(milestone: Milestone, blockers: list[Milestone]) -> None:
    """Raise DependencyError for a self-link, a foreign-project link or a cycle."""
    for b in blockers:
        if b.pk == milestone.pk:
            raise DependencyError("A milestone cannot block itself.")
        if _project_id(b) != _project_id(milestone):
            raise DependencyError("Dependencies stay inside one project.")
    # a cycle: walking *upstream* from the new blockers must never reach this milestone
    edges = defaultdict(set)
    for source_id, target_id in Milestone.blocked_by.through.objects.filter(
        from_milestone__phase__project_id=_project_id(milestone)
    ).values_list("from_milestone_id", "to_milestone_id"):
        edges[source_id].add(target_id)
    edges[milestone.pk] = {b.pk for b in blockers}
    seen, frontier = set(), list(edges[milestone.pk])
    while frontier:
        current = frontier.pop()
        if current == milestone.pk:
            raise DependencyError("That would make a loop — a milestone would block itself.")
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(edges.get(current, ()))


def set_blockers(milestone: Milestone, blocker_ids: list[int]) -> list[Milestone]:
    """Replace the milestone's dependencies after the checks; returns the blockers."""
    blockers = list(
        Milestone.objects.filter(pk__in=set(blocker_ids)).select_related("phase").order_by("pk")
    )
    missing = set(blocker_ids) - {b.pk for b in blockers}
    if missing:
        raise DependencyError(f"Unknown milestone id(s): {sorted(missing)}.")
    check_blockers(milestone, blockers)
    milestone.blocked_by.set(blockers)
    return blockers


def open_blockers(milestone: Milestone) -> list[Milestone]:
    """The dependencies that are still open — empty means the milestone is free to start."""
    return list(milestone.blocked_by.filter(completed_at__isnull=True).select_related("phase"))


def is_blocked(milestone: Milestone) -> bool:
    return bool(milestone.completed_at is None and open_blockers(milestone))


def dependency_edges(project) -> list[tuple[int, int, str, bool]]:
    """Every dependency of a project in one query: (dependant id, blocker id, blocker title,
    blocker done) in a stable order — the input to every map below."""
    return [
        (source_id, target_id, title, done is not None)
        for source_id, target_id, title, done in Milestone.blocked_by.through.objects.filter(
            from_milestone__phase__project=project
        )
        .order_by("to_milestone_id")
        .values_list(
            "from_milestone_id",
            "to_milestone_id",
            "to_milestone__title",
            "to_milestone__completed_at",
        )
    ]


def blocked_map(project, edges=None) -> dict[int, list[dict]]:
    """{milestone id: [{id, title} of its *open* blockers]} for a project (one query)."""
    out: dict[int, list[dict]] = defaultdict(list)
    for source_id, target_id, title, done in dependency_edges(project) if edges is None else edges:
        if not done:
            out[source_id].append({"id": target_id, "title": title})
    return out


def blocker_ids(project, edges=None) -> dict[int, list[int]]:
    """{milestone id: [every blocker id, done or not]} for a project — the roadmap's arrows."""
    out: dict[int, list[int]] = defaultdict(list)
    for source_id, target_id, _title, _done in (
        dependency_edges(project) if edges is None else edges
    ):
        out[source_id].append(target_id)
    return out


def unblocked_by(milestone: Milestone) -> list[Milestone]:
    """Milestones that become free once *this* one completes (every other blocker done)."""
    out = []
    for dependant in milestone.blocks.filter(completed_at__isnull=True).select_related("phase"):
        others = dependant.blocked_by.filter(~Q(pk=milestone.pk), completed_at__isnull=True)
        if not others.exists():
            out.append(dependant)
    return out


# #513: dates that contradict the dependencies


def _due_graph(project):
    """Open milestones of a project with their open blockers: {id: milestone}, {id: [blocker ids]}."""
    milestones = {
        m.pk: m
        for m in Milestone.objects.filter(phase__project=project, completed_at__isnull=True)
        .select_related("phase")
        .order_by("pk")
    }
    blockers: dict[int, list[int]] = defaultdict(list)
    for source_id, target_id in (
        Milestone.blocked_by.through.objects.filter(
            from_milestone_id__in=milestones, to_milestone_id__in=milestones
        )
        .order_by("to_milestone_id")
        .values_list("from_milestone_id", "to_milestone_id")
    ):
        blockers[source_id].append(target_id)
    return milestones, blockers


def _ordered(milestones: dict, blockers: dict) -> list[int]:
    """Milestone ids with every blocker before its dependant (the graph is loop-free)."""
    out, seen = [], set()

    def visit(mid: int) -> None:
        if mid in seen:
            return
        seen.add(mid)
        for b in blockers.get(mid, ()):
            visit(b)
        out.append(mid)

    for mid in milestones:
        visit(mid)
    return out


def due_graph(project):
    """Public name for the (milestones, blockers) load that `date_conflicts`, `slack_map` and
    `critical_chain` accept, so a view computes it once and passes it to all three."""
    return _due_graph(project)


def date_conflicts(project, milestones=None, blockers=None) -> list[dict]:
    """Open milestones due on or before the latest due date of an open blocker, with the
    day after that blocker as the suggestion. Blockers without a date cannot conflict.
    `milestones` ({id: open Milestone}) and `blockers` ({id: [open blocker ids]}) may be
    passed by a caller that already has them (the roadmap), else two queries fetch them."""
    if milestones is None or blockers is None:
        milestones, blockers = _due_graph(project)
    rows = []
    for mid in _ordered(milestones, blockers):
        m = milestones[mid]
        dated = [milestones[b] for b in blockers.get(mid, ()) if milestones[b].due_date]
        if not m.due_date or not dated:
            continue
        latest = max(dated, key=lambda b: b.due_date)
        if m.due_date <= latest.due_date:
            rows.append(
                {
                    "id": m.pk,
                    "title": m.title,
                    "due_date": m.due_date,
                    "blocker_id": latest.pk,
                    "blocker_title": latest.title,
                    "blocker_due": latest.due_date,
                    "suggested": latest.due_date + timedelta(days=1),
                }
            )
    return rows


def resolve_conflicts(project) -> list[dict]:
    """Push every conflicting due date to the day after its latest blocker, in dependency
    order so a push cascades downstream. Returns [{id, title, from, to}]."""
    milestones, blockers = _due_graph(project)
    changes = []
    for mid in _ordered(milestones, blockers):
        m = milestones[mid]
        dated = [milestones[b] for b in blockers.get(mid, ()) if milestones[b].due_date]
        if not m.due_date or not dated:
            continue
        floor = max(b.due_date for b in dated) + timedelta(days=1)
        if m.due_date < floor:
            changes.append({"id": m.pk, "title": m.title, "from": m.due_date, "to": floor})
            m.due_date = floor
            m.save(update_fields=["due_date", "updated_at"])
    return changes


# #515: slack and the critical chain

TIGHT_DAYS = 7  # a blocker with this little room before its dependant is worth a chip


def slack_map(project, milestones=None, blockers=None) -> dict[int, dict]:
    """Per open dated milestone: {slack, tight_dependant} — slack is the fewest days it can
    slip before it pushes a dated dependant (dependant due − own due − 1; negative when the
    dates already contradict, #513). None when nothing dated waits on it."""
    if milestones is None or blockers is None:
        milestones, blockers = _due_graph(project)
    dependants: dict[int, list[int]] = defaultdict(list)
    for mid, bs in blockers.items():
        for b in bs:
            dependants[b].append(mid)
    out: dict[int, dict] = {}
    for mid, m in milestones.items():
        if not m.due_date:
            continue
        best = None
        for d in dependants.get(mid, ()):
            dep = milestones.get(d)
            if dep is None or not dep.due_date:
                continue
            gap = (dep.due_date - m.due_date).days - 1
            if best is None or gap < best[0]:
                best = (gap, d)
        out[mid] = {
            "slack": best[0] if best else None,
            "tight_dependant": best[1] if best else None,
        }
    return out


def critical_chain(project, milestones=None, blockers=None) -> dict:
    """The chain that decides the plan's end: from the open dated milestone due last, walk
    upstream through the blocker with the least room each step. Returns ids (upstream →
    downstream), titles, the span in days, and the chain's least slack (None for no chain)."""
    if milestones is None or blockers is None:
        milestones, blockers = _due_graph(project)
    dated = [m for m in milestones.values() if m.due_date]
    if not dated:
        return {"ids": [], "titles": [], "from": None, "to": None, "days": 0, "slack": None}
    end = max(dated, key=lambda m: (m.due_date, -m.pk))
    chain, seen, least = [end], {end.pk}, None
    current = end
    while True:
        options = [milestones[b] for b in blockers.get(current.pk, ()) if milestones[b].due_date]
        options = [b for b in options if b.pk not in seen]
        if not options:
            break
        step = max(options, key=lambda b: (b.due_date, -b.pk))  # the tightest: due latest
        gap = (current.due_date - step.due_date).days - 1
        least = gap if least is None else min(least, gap)
        chain.append(step)
        seen.add(step.pk)
        current = step
    chain.reverse()
    return {
        "ids": [m.pk for m in chain],
        "titles": [m.title for m in chain],
        "from": chain[0].due_date,
        "to": chain[-1].due_date,
        "days": (chain[-1].due_date - chain[0].due_date).days,
        "slack": least,
    }
