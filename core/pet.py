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


# Buddy-style personality (Owner idea #23): stats grown from real work, reaction
# one-liners for live events. Observations and celebrations only — never demands.

STAT_RULES = [
    # (stat, blurb shown when it's the dominant trait)
    ("wisdom", "Mostly WISDOM — it reads over your shoulder."),
    ("focus", "Mostly FOCUS — it lives for a checked-off milestone."),
    ("curiosity", "Mostly CURIOSITY — it hoards stray ideas."),
    ("grit", "Mostly GRIT — it respects a finished experiment."),
]

REACTION_LINES = {
    "milestone": [
        "A milestone falls! *happy hop*",
        "Checked. The plan advances.",
        "That one's done. Onward.",
    ],
    "paper": [
        "Om nom — knowledge.",
        "Another paper digested.",
        "The library grows wiser.",
    ],
    "capture": [
        "Caught that thought.",
        "Idea secured. Carry on.",
        "Into the inbox it goes.",
    ],
    "note": [
        "Scribble heard. Notebook fed.",
        "A note! It remembers everything.",
    ],
}


def _level(n: int) -> int:
    """0–10 display level that grows fast early, slow late — pets should feel alive
    from day one."""
    for level, threshold in enumerate([1, 2, 4, 7, 11, 17, 26, 42, 68, 100]):
        if n < threshold:
            return level
    return 10


def pet_stats() -> dict:
    from core.models import Comment
    from literature.models import ProjectReference
    from notes.models import Note
    from plans.models import Milestone
    from research.models import ExperimentEntry
    from writing.models import SubmissionEvent

    return {
        "wisdom": _level(
            ProjectReference.objects.filter(reading_status__in=["read", "annotated"]).count()
        ),
        "focus": _level(Milestone.objects.filter(completed_at__isnull=False).count()),
        "curiosity": _level(Note.objects.count() + Comment.objects.count()),
        "grit": _level(ExperimentEntry.objects.count() + SubmissionEvent.objects.count()),
    }


POINTS_LEGEND = [
    ("milestone completed", 3),
    ("note written", 2),
    ("paper read or annotated", 2),
    ("experiment logged", 2),
    ("paper added to the library", 1),
    ("comment left", 1),
]


def _activity_days(limit: int = 120) -> set:
    """Calendar days with any pet-feeding activity (for the streak)."""
    from literature.models import ProjectReference, Reference
    from notes.models import Note
    from plans.models import Milestone
    from research.models import ExperimentEntry

    since = timezone.now() - datetime.timedelta(days=limit)
    days = set()
    for qs, field in (
        (Milestone.objects.filter(completed_at__isnull=False), "completed_at"),
        (Note.objects.all(), "created_at"),
        (Reference.objects.all(), "created_at"),
        (ProjectReference.objects.filter(reading_status__in=["read", "annotated"]), "updated_at"),
        (ExperimentEntry.objects.all(), "created_at"),
    ):
        for value in qs.filter(**{f"{field}__gte": since}).values_list(field, flat=True):
            days.add(timezone.localtime(value).date())
    return days


def streak_days(days: set | None = None, today=None) -> int:
    """Consecutive days ending today (or yesterday, so a morning visit does not read 0)."""
    days = _activity_days() if days is None else days
    today = today or timezone.localdate()
    start = today if today in days else today - datetime.timedelta(days=1)
    if start not in days:
        return 0
    n = 0
    while start in days:
        n += 1
        start -= datetime.timedelta(days=1)
    return n


ACHIEVEMENTS = [
    # (key, title, description, predicate(stats, lifetime, streak, counts))
    (
        "first_light",
        "First light",
        "Feed Mochi once — any note, paper or milestone.",
        lambda st, life, streak, c: life >= 1,
    ),
    ("hatched", "Hatched", "Reach 10 lifetime points.", lambda st, life, streak, c: life >= 10),
    (
        "bookworm",
        "Bookworm",
        "Read or annotate 10 papers.",
        lambda st, life, streak, c: c["read"] >= 10,
    ),
    (
        "closer",
        "Closer",
        "Complete 10 milestones.",
        lambda st, life, streak, c: c["milestones"] >= 10,
    ),
    ("scribe", "Scribe", "Write 25 notes.", lambda st, life, streak, c: c["notes"] >= 25),
    ("lab_rat", "Lab rat", "Log 5 experiments.", lambda st, life, streak, c: c["experiments"] >= 5),
    (
        "week_long",
        "Seven days",
        "A seven-day activity streak.",
        lambda st, life, streak, c: streak >= 7,
    ),
    (
        "month_long",
        "Thirty days",
        "A thirty-day activity streak.",
        lambda st, life, streak, c: streak >= 30,
    ),
    (
        "well_rounded",
        "Well-rounded",
        "Every stat at level 3 or more.",
        lambda st, life, streak, c: min(st.values()) >= 3,
    ),
    ("sage", "Sage", "Reach the sage stage (120 points).", lambda st, life, streak, c: life >= 120),
]


def achievements(stats: dict, lifetime: int, streak: int) -> list[dict]:
    from literature.models import ProjectReference
    from notes.models import Note
    from plans.models import Milestone
    from research.models import ExperimentEntry

    counts = {
        "read": ProjectReference.objects.filter(reading_status__in=["read", "annotated"]).count(),
        "milestones": Milestone.objects.filter(completed_at__isnull=False).count(),
        "notes": Note.objects.count(),
        "experiments": ExperimentEntry.objects.count(),
    }
    return [
        {
            "key": key,
            "title": title,
            "description": desc,
            "unlocked": bool(pred(stats, lifetime, streak, counts)),
        }
        for key, title, desc, pred in ACHIEVEMENTS
    ]


def rename_pet(name: str) -> str:
    from core.models import Pet

    name = (name or "").strip()[:40] or "Mochi"
    pet, _ = Pet.objects.get_or_create(pk=1)
    pet.name = name
    pet.save(update_fields=["name", "updated_at"])
    cache.delete("atlas-pet-state")
    return name


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

    now = timezone.localtime()
    rng = random.Random(f"{now.date()}-{now.hour}")
    stats = pet_stats()
    dominant = max(stats, key=lambda k: stats[k])
    lines = _speech_candidates(now)
    if stats[dominant] > 0:
        lines.append(dict(STAT_RULES)[dominant])
    rng.shuffle(lines)
    streak = streak_days()
    state = {
        "name": pet.name,
        "speech": lines[0],
        "speech_lines": lines[:6],  # the widget rotates through these, Buddy-style
        "reactions": {kind: rng.choice(pool) for kind, pool in REACTION_LINES.items()},
        "stats": stats,
        "dominant_stat": dominant,
        "stage": stage[1],
        "emoji": stage[2],
        "stage_blurb": stage[3],
        "mood": mood[1],
        "mood_blurb": mood[2],
        "weekly_points": weekly,
        "lifetime_points": lifetime,
        "to_next_stage": (next_stage[0] - lifetime) if next_stage else None,
        "next_stage_name": next_stage[1] if next_stage else None,
        "stage_floor": stage[0],
        "next_stage_points": next_stage[0] if next_stage else None,
        "streak_days": streak,
        "achievements": achievements(stats, lifetime, streak),
        "points_legend": [{"action": a, "points": p} for a, p in POINTS_LEGEND],
        "stages": [{"points": p, "name": n, "blurb": b} for p, n, _e, b in STAGES],
    }
    cache.set("atlas-pet-state", state, 300)
    return state
