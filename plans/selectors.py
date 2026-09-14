from django.db.models import F

from core.memo import memo
from projects.models import Project

from .models import Milestone, Phase


def project_progress(project: Project) -> tuple[int, int, int]:
    """Roll milestone completion up to the project level, in one aggregate query.

    Returns (done_milestones, total_milestones, percent).
    """
    from django.db.models import Count, Q

    def compute():
        counts = Milestone.objects.filter(phase__project=project).aggregate(
            total=Count("pk"), done=Count("pk", filter=Q(completed_at__isnull=False))
        )
        done, total = counts["done"], counts["total"]
        percent = round(100 * done / total) if total else 0
        return done, total, percent

    return memo(project, "project_progress", compute)


def plan_phases(project: Project):
    """Phases with milestones and tasks prefetched for the plan page."""
    return project.phases.prefetch_related("milestones__tasks")


def current_phase(project: Project) -> Phase | None:
    """The phase to surface on the overview: first in-progress/blocked, else first unfinished."""

    def compute():
        phases = list(project.phases.all())
        for phase in phases:
            if phase.status in (Phase.Status.IN_PROGRESS, Phase.Status.BLOCKED):
                return phase
        for phase in phases:
            if phase.status != Phase.Status.DONE:
                return phase
        return phases[-1] if phases else None

    return memo(project, "current_phase", compute)


def upcoming_milestones(project: Project, limit: int = 5):
    """Open milestones by due date — #512: the ones still blocked by another sort last, so
    "next" means the next thing that can actually be done."""
    from django.db.models import Case, Count, IntegerField, Q, When

    return (
        Milestone.objects.filter(phase__project=project, completed_at__isnull=True)
        .select_related("phase")
        .annotate(
            open_blockers=Count("blocked_by", filter=Q(blocked_by__completed_at__isnull=True)),
        )
        .annotate(
            waiting=Case(When(open_blockers__gt=0, then=1), default=0, output_field=IntegerField())
        )
        .order_by("waiting", F("due_date").asc(nulls_last=True), "pk")[:limit]
    )
