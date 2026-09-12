"""Achievements (owner, 2026-09-07: "a lot of achievements — some just for fun, some really
hard to get, souls game mode on research").

Everything is derived from real research data, once, into a flat ``facts`` dict, and every
achievement is a predicate over it with a *progress* (current/target) so the ledger can show
how far away each one is. Four tiers:

- **fun** — small delights, several hidden until earned;
- **steady** — the ordinary shape of good research habits;
- **hard** — months of work;
- **souls** — brutal, dramatic, named the way a certain game names its trophies. "You died"
  is a hypothesis contradicted; "Git gud" is a rejection followed by an acceptance.

Souls mode is a tone, not a difficulty setting: the same data, told grimly — deaths (rejections,
contradictions, failed compiles), bonfires (milestones), bosses (acceptances).
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass

from django.utils import timezone

TIERS = {"fun": 5, "steady": 10, "hard": 25, "souls": 50}
RANKS = [
    (0, "Undergrad"),
    (25, "Grad student"),
    (75, "Candidate"),
    (150, "Postdoc"),
    (300, "Principal investigator"),
    (500, "Emeritus"),
    (800, "Ashen One"),
]


@dataclass(frozen=True)
class Achievement:
    key: str
    title: str
    description: str
    tier: str
    progress: Callable[[dict], tuple[int, int]]  # facts -> (current, target)
    hidden: bool = False

    @property
    def points(self) -> int:
        return TIERS[self.tier]


def _count(key: str, target: int):
    return lambda f: (min(f.get(key, 0), target), target)


def _flag(key: str):
    return lambda f: (1 if f.get(key) else 0, 1)


# ----------------------------------------------------------------------------- catalogue
CATALOGUE: list[Achievement] = [
    # fun ---------------------------------------------------------------------------
    Achievement(
        "first_light",
        "First light",
        "Feed Mochi once — any note, paper or milestone.",
        "fun",
        _count("lifetime", 1),
    ),
    Achievement("hatched", "Hatched", "Reach 10 lifetime points.", "fun", _count("lifetime", 10)),
    Achievement(
        "named_it", "Named it", "Give the companion a name of its own.", "fun", _flag("renamed")
    ),
    Achievement(
        "night_owl",
        "Night owl",
        "Do something between midnight and 5 am.",
        "fun",
        _flag("night_owl"),
        hidden=True,
    ),
    Achievement(
        "early_bird",
        "Early bird",
        "Do something between 5 and 7 am.",
        "fun",
        _flag("early_bird"),
        hidden=True,
    ),
    Achievement(
        "weekend_warrior",
        "Weekend warrior",
        "Research on a Saturday or Sunday.",
        "fun",
        _flag("weekend"),
    ),
    Achievement(
        "inbox_zero",
        "Inbox zero",
        "Triage ten captures and leave nothing in the inbox.",
        "fun",
        lambda f: (
            min(f.get("captures_done", 0), 10)
            if f.get("captures_open", 0) == 0
            else min(f.get("captures_done", 0), 9),
            10,
        ),
    ),
    Achievement(
        "hoarder", "Hoarder", "A hundred papers in the library.", "fun", _count("papers", 100)
    ),
    Achievement(
        "highlighter",
        "Highlighter",
        "Mark 25 passages while reading.",
        "fun",
        _count("highlights", 25),
    ),
    Achievement(
        "tag_youre_it", "Tag, you're it", "Ten library tags.", "fun", _count("library_tags", 10)
    ),
    Achievement(
        "on_the_record",
        "On the record",
        "Five decisions in the log.",
        "fun",
        _count("decisions", 5),
    ),
    Achievement(
        "figure_it_out", "Figure it out", "Five figures in a project.", "fun", _count("figures", 5)
    ),
    Achievement(
        "cartographer",
        "Cartographer",
        "Ten folders across your projects.",
        "fun",
        _count("folders", 10),
    ),
    Achievement(
        "prompt_engineer", "Prompt engineer", "Five saved prompts.", "fun", _count("prompts", 5)
    ),
    Achievement(
        "one_of_everything",
        "One of everything",
        "A note, a paper, a milestone, a decision, an experiment, a hypothesis and a manuscript.",
        "fun",
        lambda f: (
            sum(
                1
                for k in (
                    "notes",
                    "papers",
                    "milestones",
                    "decisions",
                    "experiments",
                    "hypotheses",
                    "manuscripts",
                )
                if f[k] > 0
            ),
            7,
        ),
    ),
    Achievement(
        "todo_tamer",
        "To-do tamer",
        "Tick off 50 items on the Today list.",
        "fun",
        _count("todos_done", 50),
    ),
    Achievement(
        "second_edition",
        "Second edition",
        "Revise a protocol to version 2.",
        "fun",
        _flag("protocol_v2"),
        hidden=True,
    ),
    Achievement(
        "questioner", "Questioner", "Ask five research questions.", "fun", _count("questions", 5)
    ),
    # steady ------------------------------------------------------------------------
    Achievement(
        "bookworm", "Bookworm", "Read or annotate 10 papers.", "steady", _count("read", 10)
    ),
    Achievement("closer", "Closer", "Complete 10 milestones.", "steady", _count("milestones", 10)),
    Achievement("scribe", "Scribe", "Write 25 notes.", "steady", _count("notes", 25)),
    Achievement("lab_rat", "Lab rat", "Log 5 experiments.", "steady", _count("experiments", 5)),
    Achievement(
        "week_long", "Seven days", "A seven-day activity streak.", "steady", _count("streak", 7)
    ),
    Achievement(
        "well_rounded",
        "Well-rounded",
        "Every companion stat at level 3 or more.",
        "steady",
        lambda f: (min(f["min_stat"], 3), 3),
    ),
    Achievement(
        "linked_in", "Linked in", "25 links between notes.", "steady", _count("note_links", 25)
    ),
    Achievement(
        "phase_done",
        "Phase complete",
        "Finish a whole phase of a plan.",
        "steady",
        _count("phases_done", 1),
    ),
    Achievement(
        "planner",
        "Planner",
        "A project with four or more phases.",
        "steady",
        _flag("four_phase_project"),
    ),
    Achievement(
        "weigh_the_evidence",
        "Weigh the evidence",
        "Attach 5 pieces of evidence to hypotheses.",
        "steady",
        _count("evidence", 5),
    ),
    Achievement(
        "drafting", "Drafting", "Take a manuscript past the outline.", "steady", _flag("drafting")
    ),
    Achievement(
        "compiled", "It compiles", "Build a manuscript PDF.", "steady", _count("compiles_ok", 1)
    ),
    Achievement(
        "submitted", "Submitted", "Send a manuscript out.", "steady", _count("submissions", 1)
    ),
    Achievement(
        "constellation",
        "Constellation",
        "50 citation edges in a project's graph.",
        "steady",
        _count("citation_edges", 50),
    ),
    Achievement(
        "data_steward", "Data steward", "Register 3 datasets.", "steady", _count("datasets", 3)
    ),
    Achievement(
        "annotated",
        "Annotator",
        "Annotate 10 papers (not just read them).",
        "steady",
        _count("annotated", 10),
    ),
    # hard --------------------------------------------------------------------------
    Achievement(
        "month_long", "Thirty days", "A thirty-day activity streak.", "hard", _count("streak", 30)
    ),
    Achievement(
        "sage", "Sage", "Reach the sage stage (120 points).", "hard", _count("lifetime", 120)
    ),
    Achievement("centurion", "Centurion", "Read 100 papers.", "hard", _count("read", 100)),
    Achievement(
        "two_hundred_notes", "Two hundred notes", "Write 200 notes.", "hard", _count("notes", 200)
    ),
    Achievement(
        "hundred_milestones",
        "A hundred milestones",
        "Complete 100 milestones.",
        "hard",
        _count("milestones", 100),
    ),
    Achievement(
        "lab_veteran", "Lab veteran", "Log 50 experiments.", "hard", _count("experiments", 50)
    ),
    Achievement("accepted", "Accepted", "A manuscript accepted.", "hard", _count("accepted", 1)),
    Achievement(
        "published", "Published", "A manuscript published.", "hard", _count("published", 1)
    ),
    Achievement(
        "polymath",
        "Polymath",
        "Three projects with three completed milestones each.",
        "hard",
        _count("projects_with_3_done", 3),
    ),
    Achievement(
        "deep_reader",
        "Deep reader",
        "Ten highlights on a single paper.",
        "hard",
        _count("max_highlights_on_paper", 10),
    ),
    Achievement(
        "evidence_mountain",
        "Evidence mountain",
        "50 pieces of evidence.",
        "hard",
        _count("evidence", 50),
    ),
    Achievement(
        "finisher", "Finisher", "Complete a project.", "hard", _count("projects_complete", 1)
    ),
    # souls -------------------------------------------------------------------------
    Achievement(
        "you_died",
        "You died",
        "A hypothesis contradicted by the evidence. Rise.",
        "souls",
        _count("contradicted", 1),
        hidden=True,
    ),
    Achievement(
        "prepare_to_write",
        "Prepare to write",
        "Ten saved revisions of one manuscript.",
        "souls",
        _count("max_revisions", 10),
    ),
    Achievement(
        "git_gud",
        "Git gud",
        "A rejection, then an acceptance.",
        "souls",
        _flag("rejected_then_accepted"),
        hidden=True,
    ),
    Achievement(
        "no_hit_run",
        "No-hit run",
        "A manuscript published without a single rejection.",
        "souls",
        _flag("clean_publication"),
    ),
    Achievement(
        "reviewer_two",
        "Boss slain: Reviewer 2",
        "Reviews received, a revision submitted, then accepted.",
        "souls",
        _flag("beat_reviewer_two"),
    ),
    Achievement(
        "bonfire_100", "Bonfire lit", "A hundred-day streak.", "souls", _count("streak", 100)
    ),
    Achievement(
        "hollowed",
        "Hollowed, returned",
        "Come back after a month away and keep going for a week.",
        "souls",
        _flag("returned_after_gap"),
        hidden=True,
    ),
    Achievement(
        "praise_the_sun",
        "Praise the sun",
        "Published, a hundred papers read and a thirty-day streak.",
        "souls",
        lambda f: ((f["published"] > 0) + (f["read"] >= 100) + (f["streak"] >= 30), 3),
    ),
    Achievement(
        "new_game_plus",
        "New game+",
        "Complete a second project.",
        "souls",
        _count("projects_complete", 2),
    ),
    Achievement(
        "the_abyss", "The abyss", "A thousand lifetime points.", "souls", _count("lifetime", 1000)
    ),
    Achievement(
        "still_hollow",
        "Still hollow",
        "Three manuscripts shelved.",
        "souls",
        _count("shelved", 3),
        hidden=True,
    ),
    # batch two (2026-09-07, #388) — fun ------------------------------------------------
    Achievement(
        "colour_coded",
        "Colour coded",
        "Give three library tags a colour.",
        "fun",
        _count("coloured_tags", 3),
    ),
    Achievement(
        "lunch_break",
        "Working lunch",
        "Log something between noon and two.",
        "fun",
        _flag("lunch_break"),
    ),
    Achievement(
        "midnight_oil",
        "Midnight oil",
        "Log something in the midnight hour.",
        "fun",
        _flag("midnight"),
    ),
    Achievement(
        "collector", "Collector", "Attach 25 PDFs in the library.", "fun", _count("pdfs", 25)
    ),
    Achievement("doi_hunter", "DOI hunter", "Fifty papers with a DOI.", "fun", _count("dois", 50)),
    Achievement(
        "second_opinion", "Second opinion", "Leave ten comments.", "fun", _count("comments", 10)
    ),
    Achievement(
        "pack_rat",
        "Pack rat",
        "A hundred documents in the workspace.",
        "fun",
        _count("documents", 100),
    ),
    Achievement(
        "many_files",
        "Many hands",
        "A manuscript with four or more source files.",
        "fun",
        _count("max_files_on_manuscript", 4),
    ),
    Achievement(
        "smart_views",
        "Smart views",
        "Save three views in the Library rail.",
        "fun",
        _count("saved_views", 3),
    ),
    Achievement(
        "second_project",
        "Second project",
        "Run two projects at once.",
        "fun",
        _count("projects", 2),
    ),
    Achievement(
        "done_today",
        "Good day",
        "Tick five to-dos in one day.",
        "fun",
        _count("todos_done_today", 5),
    ),
    Achievement(
        "anniversary",
        "Anniversary",
        "A year since your first entry.",
        "fun",
        _count("first_day_age", 365),
        hidden=True,
    ),
    # steady --------------------------------------------------------------------------
    Achievement("fortnight", "Fortnight", "A 14-day streak.", "steady", _count("streak", 14)),
    Achievement(
        "forty_days", "Forty days", "Forty active days.", "steady", _count("days_active", 40)
    ),
    Achievement(
        "margin_notes",
        "Margin notes",
        "Fifty highlights with a comment.",
        "steady",
        _count("commented_highlights", 50),
    ),
    Achievement(
        "balanced_ledger",
        "Balanced ledger",
        "Ten pieces of evidence for and ten against.",
        "steady",
        lambda f: (min(f.get("evidence_for", 0), f.get("evidence_against", 0)), 10),
    ),
    Achievement(
        "five_projects",
        "Five projects",
        "Five projects in the workspace.",
        "steady",
        _count("projects", 5),
    ),
    Achievement(
        "librarian", "Librarian", "250 papers in the library.", "steady", _count("papers", 250)
    ),
    Achievement(
        "ten_phases", "Ten phases", "Finish ten phases.", "steady", _count("phases_done", 10)
    ),
    # hard ----------------------------------------------------------------------------
    Achievement("quarter_streak", "A quarter", "A 90-day streak.", "hard", _count("streak", 90)),
    Achievement(
        "year_active",
        "Two hundred days",
        "Two hundred active days.",
        "hard",
        _count("days_active", 200),
    ),
    Achievement(
        "five_hundred_highlights",
        "Five hundred",
        "Five hundred highlights.",
        "hard",
        _count("highlights", 500),
    ),
    Achievement(
        "ten_manuscripts",
        "Ten manuscripts",
        "Ten manuscripts on the board.",
        "hard",
        _count("manuscripts", 10),
    ),
    Achievement(
        "three_complete",
        "Three complete",
        "Three projects marked complete.",
        "hard",
        _count("projects_complete", 3),
    ),
    # souls ---------------------------------------------------------------------------
    Achievement(
        "died_a_hundred",
        "Died a hundred times",
        "A hundred deaths — rejections, contradictions, failed compiles.",
        "souls",
        lambda f: (
            f.get("rejections", 0) + f.get("contradicted", 0) + f.get("compiles_failed", 0),
            100,
        ),
    ),
    Achievement(
        "kindled",
        "Kindled",
        "Fifty bonfires lit (milestones done).",
        "souls",
        _count("milestones", 50),
    ),
    Achievement(
        "invaded", "Invaded", "Five rejections and still here.", "souls", _count("rejections", 5)
    ),
    Achievement(
        "dragonslayer",
        "Dragonslayer",
        "Three acceptances.",
        "souls",
        _count("accepted", 3),
        hidden=True,
    ),
    Achievement(
        "estus",
        "Estus",
        "Twenty failed compiles and twenty good ones — you drank and went on.",
        "souls",
        lambda f: (min(f.get("compiles_failed", 0), f.get("compiles_ok", 0)), 20),
        hidden=True,
    ),
    # batch three (2026-09-07, #415): seasonal secrets, souls-only trophies, the platinum --
    Achievement(
        "new_year_new_hypothesis",
        "New year, new hypothesis",
        "Do research on the first of January.",
        "fun",
        _flag("new_year"),
        hidden=True,
    ),
    Achievement(
        "trick_or_treat",
        "Trick or treat",
        "Something happened on the 31st of October.",
        "fun",
        _flag("halloween"),
        hidden=True,
    ),
    Achievement(
        "solstice",
        "Solstice",
        "Work on the longest or the shortest day of the year.",
        "fun",
        _flag("solstice"),
        hidden=True,
    ),
    Achievement(
        "leap_of_faith",
        "Leap of faith",
        "Do anything on the 29th of February.",
        "steady",
        _flag("leap_day"),
        hidden=True,
    ),
    Achievement(
        "friday_the_13th",
        "Friday the 13th",
        "Research on a Friday the 13th. Nothing went wrong. Probably.",
        "fun",
        _flag("friday_13"),
        hidden=True,
    ),
    Achievement(
        "embrace_the_dark",
        "Embrace the dark",
        "Switch Souls mode on.",
        "fun",
        _flag("souls_on"),
    ),
    Achievement(
        "no_bonfire",
        "No bonfire",
        "Seven active days with Souls mode on — it only counts while it is on.",
        "souls",
        _count("souls_days", 7),
    ),
    Achievement(
        "the_dark_soul",
        "The Dark Soul",
        "Thirty active days in Souls mode. You are the dark now.",
        "souls",
        _count("souls_days", 30),
        hidden=True,
    ),
]

# The platinum: every other trophy in the ledger. Its progress is filled in by evaluate(),
# which counts the rest first — it is listed so that max_score and the tier totals include it.
PLATINUM = Achievement(
    "platinum",
    "Platinum",
    "Every other achievement in the ledger.",
    "souls",
    lambda f: (f.get("_unlocked_others", 0), f.get("_total_others", 1)),
)
CATALOGUE.append(PLATINUM)
BY_KEY = {a.key: a for a in CATALOGUE}


# ----------------------------------------------------------------------------- facts
def _hours_and_weekdays(limit: int = 400) -> tuple[set[int], set[int]]:
    """Local hours and weekdays with activity, from the newest notes/milestones/experiments."""
    from notes.models import Note
    from plans.models import Milestone
    from research.models import ExperimentEntry

    stamps = []
    stamps += list(
        Note.objects.order_by("-created_at").values_list("created_at", flat=True)[:limit]
    )
    stamps += list(
        Milestone.objects.filter(completed_at__isnull=False)
        .order_by("-completed_at")
        .values_list("completed_at", flat=True)[:limit]
    )
    stamps += list(
        ExperimentEntry.objects.order_by("-created_at").values_list("created_at", flat=True)[:limit]
    )
    hours, weekdays = set(), set()
    for value in stamps:
        local = timezone.localtime(value)
        hours.add(local.hour)
        weekdays.add(local.weekday())
    return hours, weekdays


def _returned_after_gap(days: set[datetime.date]) -> bool:
    """A gap of 30+ days followed by a 7-day run."""
    ordered = sorted(days)
    for i in range(1, len(ordered)):
        if (ordered[i] - ordered[i - 1]).days >= 30:
            run, day = 1, ordered[i]
            while day + datetime.timedelta(days=1) in days:
                run += 1
                day += datetime.timedelta(days=1)
            if run >= 7:
                return True
    return False


def gather_facts(
    stats: dict | None = None, lifetime: int | None = None, streak: int | None = None
) -> dict:
    from django.db.models import Count

    from core.models import Comment, Pet, TodoItem
    from core.pet import _activity_days, _activity_points, pet_stats, streak_days
    from documents.models import Document, Folder
    from literature.models import (
        CitationEdge,
        Highlight,
        LibraryTag,
        ProjectReference,
        Reference,
        SavedView,
    )
    from notes.models import Note, NoteLink, QuickCapture
    from plans.models import Milestone, Phase, ResearchQuestion
    from projects.models import DecisionRecord, Project
    from prompts.models import Prompt
    from research.models import Dataset, Evidence, ExperimentEntry, Hypothesis, Protocol
    from writing.models import Manuscript, ManuscriptFile, ManuscriptRevision, SubmissionEvent

    stats = stats or pet_stats()
    days = _activity_days(limit=400)
    streak = streak_days(days) if streak is None else streak
    lifetime = _activity_points() if lifetime is None else lifetime
    hours, weekdays = _hours_and_weekdays()
    pet = Pet.objects.filter(pk=1).first()
    done_per_project = (
        Milestone.objects.filter(completed_at__isnull=False)
        .values("phase__project")
        .annotate(n=Count("id"))
        .values_list("n", flat=True)
    )
    per_paper = (
        Highlight.objects.values("reference").annotate(n=Count("id")).values_list("n", flat=True)
    )
    per_manuscript = (
        ManuscriptRevision.objects.values("manuscript")
        .annotate(n=Count("id"))
        .values_list("n", flat=True)
    )
    files_per_manuscript = (
        ManuscriptFile.objects.values("manuscript")
        .annotate(n=Count("id"))
        .values_list("n", flat=True)
    )
    events = list(
        SubmissionEvent.objects.order_by("manuscript_id", "date", "id").values_list(
            "manuscript_id", "kind", "date"
        )
    )
    by_ms: dict[int, list[tuple[str, datetime.date]]] = {}
    for mid, kind, date in events:
        by_ms.setdefault(mid, []).append((kind, date))
    rejected_then_accepted = any(
        any(k == "rejected" for k, _ in seq)
        and any(
            k == "accepted" and d >= min(dd for kk, dd in seq if kk == "rejected") for k, d in seq
        )
        for seq in by_ms.values()
    )
    beat_reviewer_two = any(
        [k for k, _ in seq if k in ("reviews_received", "revision_submitted", "accepted")][-3:]
        == ["reviews_received", "revision_submitted", "accepted"]
        or _subsequence([k for k, _ in seq], ["reviews_received", "revision_submitted", "accepted"])
        for seq in by_ms.values()
    )
    published_ids = set(Manuscript.objects.filter(status="published").values_list("id", flat=True))
    clean_publication = any(
        mid in published_ids
        and not any(k == "rejected" for k, _ in by_ms.get(mid, []))
        and any(k == "submitted" for k, _ in by_ms.get(mid, []))
        for mid in published_ids
    )
    return {
        "lifetime": lifetime,
        "streak": streak,
        "min_stat": min(stats.values()) if stats else 0,
        "renamed": bool(pet and pet.name.strip().lower() != "mochi"),
        "night_owl": any(h < 5 for h in hours),
        "early_bird": any(5 <= h < 7 for h in hours),
        "weekend": any(d >= 5 for d in weekdays),
        "captures_done": QuickCapture.objects.filter(processed=True).count(),
        "captures_open": QuickCapture.objects.filter(processed=False).count(),
        "papers": Reference.objects.count(),
        "read": ProjectReference.objects.filter(reading_status__in=["read", "annotated"]).count(),
        "annotated": ProjectReference.objects.filter(reading_status="annotated").count(),
        "highlights": Highlight.objects.count(),
        "max_highlights_on_paper": max(per_paper, default=0),
        "library_tags": LibraryTag.objects.count(),
        "decisions": DecisionRecord.objects.count(),
        "figures": Document.objects.filter(content_type__startswith="image/").count(),
        "folders": Folder.objects.count(),
        "prompts": Prompt.objects.count(),
        "notes": Note.objects.count(),
        "note_links": NoteLink.objects.count(),
        "milestones": Milestone.objects.filter(completed_at__isnull=False).count(),
        "phases_done": Phase.objects.filter(status="done").count(),
        "four_phase_project": Project.objects.annotate(n=Count("phases")).filter(n__gte=4).exists(),
        "experiments": ExperimentEntry.objects.count(),
        "hypotheses": Hypothesis.objects.count(),
        "contradicted": Hypothesis.objects.filter(status="contradicted").count(),
        "evidence": Evidence.objects.count(),
        "datasets": Dataset.objects.count(),
        "protocol_v2": Protocol.objects.filter(version__gte=2).exists(),
        "questions": ResearchQuestion.objects.count(),
        "todos_done": TodoItem.objects.filter(done=True).count(),
        "manuscripts": Manuscript.objects.count(),
        "drafting": Manuscript.objects.exclude(status__in=["idea", "outlining"]).exists(),
        "compiles_ok": Manuscript.objects.filter(compile_status="ok").count()
        + ManuscriptRevision.objects.count(),
        "compiles_failed": Manuscript.objects.filter(compile_status="failed").count(),
        "max_revisions": max(per_manuscript, default=0),
        "submissions": SubmissionEvent.objects.filter(kind="submitted").count(),
        "accepted": SubmissionEvent.objects.filter(kind="accepted").count()
        + Manuscript.objects.filter(status__in=["accepted", "published"]).count(),
        "published": len(published_ids),
        "rejections": SubmissionEvent.objects.filter(kind="rejected").count(),
        "shelved": Manuscript.objects.filter(status="shelved").count(),
        "rejected_then_accepted": rejected_then_accepted,
        "beat_reviewer_two": beat_reviewer_two,
        "clean_publication": clean_publication,
        "citation_edges": CitationEdge.objects.count(),
        "projects_complete": Project.objects.filter(status="complete").count(),
        "projects_with_3_done": sum(1 for n in done_per_project if n >= 3),
        "returned_after_gap": _returned_after_gap(days),
        # batch two (2026-09-07, #388)
        "coloured_tags": LibraryTag.objects.exclude(color="").count(),
        "pdfs": Reference.objects.exclude(pdf="").exclude(pdf__isnull=True).count(),
        "dois": Reference.objects.exclude(doi__isnull=True).exclude(doi="").count(),
        "comments": Comment.objects.count(),
        "documents": Document.objects.count(),
        "projects": Project.objects.count(),
        "saved_views": SavedView.objects.count(),
        "max_files_on_manuscript": max(files_per_manuscript, default=0),
        "days_active": len(days),
        "first_day_age": (timezone.localdate() - min(days)).days if days else 0,
        "todos_done_today": TodoItem.objects.filter(
            done=True, done_at__date=timezone.localdate()
        ).count(),
        "commented_highlights": Highlight.objects.exclude(comment="").count(),
        "evidence_for": Evidence.objects.filter(direction="supports").count(),
        "evidence_against": Evidence.objects.filter(direction="contradicts").count(),
        "lunch_break": any(12 <= h < 14 for h in hours),
        "midnight": any(h == 0 for h in hours),
        # batch three (2026-09-07, #415): the calendar and the dark
        **_seasonal_facts(days),
        "souls_on": bool(pet and pet.souls_mode),
        "souls_days": (
            sum(1 for d in days if d >= pet.souls_since.date())
            if pet and pet.souls_mode and pet.souls_since
            else 0
        ),
    }


def _seasonal_facts(days: set[datetime.date]) -> dict:
    """Dates that only come round once a year (or four): did anything happen on them?"""
    return {
        "new_year": any(d.month == 1 and d.day == 1 for d in days),
        "halloween": any(d.month == 10 and d.day == 31 for d in days),
        "solstice": any((d.month, d.day) in ((6, 21), (12, 21)) for d in days),
        "leap_day": any(d.month == 2 and d.day == 29 for d in days),
        "friday_13": any(d.day == 13 and d.weekday() == 4 for d in days),
    }


def _subsequence(seq: list[str], pattern: list[str]) -> bool:
    it = iter(seq)
    return all(any(x == p for x in it) for p in pattern)


# ----------------------------------------------------------------------------- evaluation
def _done(a: Achievement, facts: dict) -> bool:
    current, target = a.progress(facts)
    return int(current) >= int(target)


def evaluate(facts: dict) -> list[dict]:
    from core.models import AchievementUnlock

    known = dict(AchievementUnlock.objects.values_list("key", "unlocked_at"))
    others = [a for a in CATALOGUE if a is not PLATINUM]
    facts = {
        **facts,
        "_total_others": len(others),
        "_unlocked_others": sum(1 for a in others if _done(a, facts)),
    }
    rows = []
    for a in CATALOGUE:
        current, target = a.progress(facts)
        current = max(0, min(int(current), int(target)))
        unlocked = current >= target
        rows.append(
            {
                "key": a.key,
                "title": a.title if (unlocked or not a.hidden) else "???",
                "description": a.description
                if (unlocked or not a.hidden)
                else "Hidden — you'll know it when it happens.",
                "tier": a.tier,
                "points": a.points,
                "hidden": a.hidden,
                "unlocked": unlocked,
                "unlocked_at": known.get(a.key),
                "progress": {
                    "current": current,
                    "target": int(target),
                    "percent": int(100 * current / target) if target else 100,
                },
            }
        )
    return rows


def record_unlocks(rows: list[dict]) -> list[str]:
    """Remember first-time unlocks; returns the keys unlocked just now."""
    from core.models import AchievementUnlock

    fresh = []
    for row in rows:
        if row["unlocked"] and row["unlocked_at"] is None:
            obj, created = AchievementUnlock.objects.get_or_create(key=row["key"])
            row["unlocked_at"] = obj.unlocked_at
            if created:
                fresh.append(row["key"])
    return fresh


def score(rows: list[dict]) -> int:
    return sum(r["points"] for r in rows if r["unlocked"])


def rank(points: int) -> dict:
    current = RANKS[0]
    nxt = None
    for floor, name in RANKS:
        if points >= floor:
            current = (floor, name)
        elif nxt is None:
            nxt = (floor, name)
    return {
        "name": current[1],
        "floor": current[0],
        "next": nxt[1] if nxt else None,
        "next_at": nxt[0] if nxt else None,
    }


def souls_counters(facts: dict) -> dict:
    """The grim scoreboard: deaths, bonfires, bosses, souls."""
    return {
        "deaths": facts["rejections"] + facts["contradicted"] + facts["compiles_failed"],
        "bonfires": facts["milestones"],
        "bosses": facts["accepted"],
        "souls": facts["lifetime"],
    }


SOULS_LINES = [
    "The bonfire is lit. {bonfires} rested at so far.",
    "{deaths} deaths. Each one taught you something. Rise.",
    "A boss falls only to those who submit. Bosses slain: {bosses}.",
    "{souls} souls gathered. Do not lose them to a shelved draft.",
    "Reviewer 2 waits at the fog gate.",
    "Every contradicted hypothesis is a death. Every death, a lesson.",
    "Don't you dare go hollow. Write the paragraph.",
    "Prepare to write.",
]


def souls_speech(facts: dict) -> list[str]:
    c = souls_counters(facts)
    return [line.format(**c) for line in SOULS_LINES]


def set_souls_mode(on: bool) -> bool:
    from django.core.cache import cache

    from core.models import Pet

    pet, _ = Pet.objects.get_or_create(pk=1, defaults={"name": "Mochi"})
    if bool(on) and not pet.souls_mode:
        pet.souls_since = timezone.now()  # #415: the dark counts from now
    elif not on:
        pet.souls_since = None
    pet.souls_mode = bool(on)
    pet.save(update_fields=["souls_mode", "souls_since", "updated_at"])
    cache.delete("atlas-pet-state")
    return pet.souls_mode


def ledger() -> dict:
    """Everything the Achievements page shows."""
    from core.models import Pet

    facts = gather_facts()
    rows = evaluate(facts)
    record_unlocks(rows)
    total = score(rows)
    pet = Pet.objects.filter(pk=1).first()
    recent_cutoff = timezone.now() - datetime.timedelta(days=1)
    return {
        "achievements": rows,
        "score": total,
        "max_score": sum(a.points for a in CATALOGUE),
        "unlocked": sum(1 for r in rows if r["unlocked"]),
        "total": len(rows),
        "rank": rank(total),
        "tiers": [
            {
                "key": k,
                "points": v,
                "total": sum(1 for a in CATALOGUE if a.tier == k),
                "unlocked": sum(1 for r in rows if r["tier"] == k and r["unlocked"]),
            }
            for k, v in TIERS.items()
        ],
        "souls_mode": bool(pet and pet.souls_mode),
        "souls": souls_counters(facts),
        "recent_unlocks": [
            r["key"]
            for r in rows
            if r["unlocked"] and r["unlocked_at"] and r["unlocked_at"] >= recent_cutoff
        ],
        "next_up": sorted(
            [r for r in rows if not r["unlocked"] and not r["hidden"]],
            key=lambda r: -r["progress"]["percent"],
        )[:5],
    }
