"""Weekly research review (Owner idea #84 / [REV] cycle 85 data layer).

Assembles "what happened this week" — the items, not just counts — across one project or
everything, for a chosen week window. Reuses the same models the dashboard aggregates.
"""

import datetime

from django.utils import timezone


def _window(weeks_back: int):
    """Return (start, end) dates for the Mon–Sun week `weeks_back` weeks before now."""
    today = timezone.localdate()
    monday = today - datetime.timedelta(days=today.weekday())
    start = monday - datetime.timedelta(weeks=weeks_back)
    return start, start + datetime.timedelta(days=7)


def weekly_review(project=None, weeks_back: int = 0) -> dict:
    """Items completed/created in the week window, optionally scoped to one project."""
    from literature.models import ProjectReference
    from notes.models import Note
    from plans.models import Milestone
    from projects.models import DecisionRecord
    from research.models import ExperimentEntry

    start, end = _window(weeks_back)

    def scoped(qs, path):
        return qs.filter(**{f"{path}": project.slug}) if project else qs

    papers = scoped(
        ProjectReference.objects.filter(
            reading_status__in=["read", "annotated"],
            updated_at__date__gte=start,
            updated_at__date__lt=end,
        ).select_related("reference", "project"),
        "project__slug",
    )
    notes = scoped(
        Note.objects.filter(created_at__date__gte=start, created_at__date__lt=end).select_related(
            "project"
        ),
        "project__slug",
    )
    milestones = scoped(
        Milestone.objects.filter(
            completed_at__date__gte=start, completed_at__date__lt=end
        ).select_related("phase__project"),
        "phase__project__slug",
    )
    decisions = scoped(
        DecisionRecord.objects.filter(decided_on__gte=start, decided_on__lt=end).select_related(
            "project"
        ),
        "project__slug",
    )
    experiments = scoped(
        ExperimentEntry.objects.filter(date__gte=start, date__lt=end).select_related("project"),
        "project__slug",
    )

    return {
        "start": start.isoformat(),
        "end": (end - datetime.timedelta(days=1)).isoformat(),
        "weeks_back": weeks_back,
        "project": project.slug if project else None,
        "papers_read": [
            {
                "key": p.reference.bibtex_key,
                "title": p.reference.title,
                "project": p.project.name,
                "reference_id": p.reference_id,
            }
            for p in papers
        ],
        "notes_written": [{"id": n.pk, "title": n.title, "project": n.project.name} for n in notes],
        "milestones_done": [
            {"title": m.title, "project": m.phase.project.name} for m in milestones
        ],
        "decisions": [{"title": d.title, "project": d.project.name} for d in decisions],
        "experiments": [
            {"title": e.title, "date": e.date.isoformat(), "project": e.project.name}
            for e in experiments
        ],
    }
