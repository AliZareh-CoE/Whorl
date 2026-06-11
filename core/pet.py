"""The Atlas pet (Owner idea #12): a calm companion fed by real research activity.

Everything is derived from the database — the pet never nags, never decays into
guilt, and "sleeping" just means you rested too. Activity is cached for 5 minutes.
"""

import datetime

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
