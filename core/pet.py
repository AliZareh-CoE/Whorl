"""The Atlas pet (Owner idea #12): a calm companion fed by real research activity.

Everything is derived from the database — the pet never nags, never decays into
guilt, and "sleeping" just means you rested too. Activity is cached for 5 minutes.
"""

import datetime
import random

from django.core.cache import cache
from django.utils import timezone

WEEK = datetime.timedelta(days=7)

STAGES = [
    (0, "egg", "🥚", "An egg. Every project starts somewhere."),
    (10, "hatchling", "🐣", "Hatched! Fed by your first finished work."),
    (40, "scholar", "🦉", "A young scholar owl — it has seen some literature."),
    (120, "sage", "🦉✨", "A sage. It has watched whole phases complete."),
]

MOODS = [
    (0, "sleeping", "zzz… it rests while you rest"),
    (1, "content", "quietly pleased with this week's progress"),
    (5, "happy", "clearly delighted by this week"),
    (12, "thriving", "absolutely thriving — what a week"),
]


def _activity_points(since=None) -> int:
    from core.models import Comment
    from literature.models import ProjectReference, Reference
    from notes.models import Note
    from plans.models import Milestone
    from research.models import ExperimentEntry

    def window(qs, field="created_at"):
        return qs.filter(**{f"{field}__gte": since}) if since else qs

    points = 0
    points += (
        3 * window(Milestone.objects.filter(completed_at__isnull=False), "completed_at").count()
    )
    points += 2 * window(Note.objects.all()).count()
    points += 1 * window(Reference.objects.all()).count()
    points += (
        2
        * window(
            ProjectReference.objects.filter(reading_status__in=["read", "annotated"]), "updated_at"
        ).count()
    )
    points += 2 * window(ExperimentEntry.objects.all()).count()
    points += 1 * window(Comment.objects.all()).count()
    return points


def _speech_candidates(now) -> list[str]:
    """Short, calm lines drawn from real context — observations, never nagging."""
    from literature.models import ProjectReference
    from notes.models import Note
    from plans.models import Milestone, Phase

    today = now.date()
    lines = []

    overdue = Milestone.objects.filter(completed_at__isnull=True, due_date__lt=today).count()
    if overdue == 1:
        lines.append("One milestone slipped past its date. Tomorrow counts too.")
    elif overdue > 1:
        lines.append(f"{overdue} milestones are past due — pick one, forget the rest for today.")

    done_today = Milestone.objects.filter(completed_at__date=today).count()
    if done_today:
        lines.append(
            f"{done_today} milestone{'s' if done_today > 1 else ''} done today. I saw that."
        )

    notes_today = Note.objects.filter(created_at__date=today).count()
    if notes_today >= 3:
        lines.append(f"{notes_today} notes today — the lab notebook is humming.")
    elif notes_today:
        lines.append("A note written today. Small steps stack up.")

    read_week = ProjectReference.objects.filter(
        reading_status__in=["read", "annotated"], updated_at__gte=now - WEEK
    ).count()
    if read_week >= 5:
        lines.append(f"{read_week} papers read this week. Genuinely scholarly.")
    elif read_week:
        lines.append(
            f"{read_week} paper{'s' if read_week > 1 else ''} read this week — steady wins."
        )

    phase = (
        Phase.objects.filter(status="in_progress", project__status="active")
        .select_related("project")
        .first()
    )
    if phase:
        done, total = phase.milestone_counts
        lines.append(f"“{phase.name}” is moving — {done}/{total} milestones.")

    hour = now.hour
    if hour < 6:
        lines.append("Up before the birds. I'll keep watch.")
    elif hour < 12:
        lines.append("Morning. Big ideas like coffee.")
    elif hour < 18:
        lines.append("A fine afternoon to check one small thing off.")
    else:
        lines.append("Evening session — stop while it's still fun.")
    return lines


def pet_speech(now=None) -> str:
    """One line, stable within the hour so it doesn't flicker between page loads."""
    now = now or timezone.localtime()
    candidates = _speech_candidates(now)
    return random.Random(f"{now.date()}-{now.hour}").choice(candidates)


def pet_state() -> dict:
    cached = cache.get("atlas-pet-state")
    if cached is not None:
        return cached

    from core.models import Pet

    pet, _ = Pet.objects.get_or_create(pk=1, defaults={"name": "Mochi"})
    lifetime = _activity_points()
    weekly = _activity_points(since=timezone.now() - WEEK)

    stage = next(s for s in reversed(STAGES) if lifetime >= s[0])
    mood = next(m for m in reversed(MOODS) if weekly >= m[0])
    next_stage = next((s for s in STAGES if s[0] > lifetime), None)

    state = {
        "name": pet.name,
        "speech": pet_speech(),
        "stage": stage[1],
        "emoji": stage[2],
        "stage_blurb": stage[3],
        "mood": mood[1],
        "mood_blurb": mood[2],
        "weekly_points": weekly,
        "lifetime_points": lifetime,
        "to_next_stage": (next_stage[0] - lifetime) if next_stage else None,
        "next_stage_name": next_stage[1] if next_stage else None,
    }
    cache.set("atlas-pet-state", state, 300)
    return state
