"""#512: milestone dependencies — "blocked by", the way Linear and Asana mean it.

A milestone is *blocked* while any milestone it depends on is not complete. Dependencies stay
inside one project, never point at themselves and never form a cycle; the plan payload and
the roadmap carry the flags from grouped queries so no page asks per row.
"""

from __future__ import annotations

from collections import defaultdict

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


def blocked_map(project) -> dict[int, list[dict]]:
    """{milestone id: [{id, title} of its *open* blockers]} for a project, in two queries."""
    rows = (
        Milestone.blocked_by.through.objects.filter(
            from_milestone__phase__project=project, to_milestone__completed_at__isnull=True
        )
        .order_by("to_milestone_id")  # a stable order for payloads and tests
        .values_list("from_milestone_id", "to_milestone_id", "to_milestone__title")
    )
    out: dict[int, list[dict]] = defaultdict(list)
    for source_id, target_id, title in rows:
        out[source_id].append({"id": target_id, "title": title})
    return out


def unblocked_by(milestone: Milestone) -> list[Milestone]:
    """Milestones that become free once *this* one completes (every other blocker done)."""
    out = []
    for dependant in milestone.blocks.filter(completed_at__isnull=True).select_related("phase"):
        others = dependant.blocked_by.filter(~Q(pk=milestone.pk), completed_at__isnull=True)
        if not others.exists():
            out.append(dependant)
    return out
