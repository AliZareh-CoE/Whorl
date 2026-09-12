"""Achievements ledger (owner, 2026-09-07): fun, steady, hard and souls tiers."""

import datetime

import pytest
from django.utils import timezone

from core import achievements as ach
from core.models import AchievementUnlock, Pet

pytestmark = pytest.mark.django_db


def test_catalogue_is_large_and_consistent():
    keys = [a.key for a in ach.CATALOGUE]
    assert len(keys) == len(set(keys))
    assert len(keys) >= 50
    tiers = {a.tier for a in ach.CATALOGUE}
    assert tiers == {"fun", "steady", "hard", "souls"}
    assert sum(1 for a in ach.CATALOGUE if a.hidden) >= 5
    assert sum(1 for a in ach.CATALOGUE if a.tier == "souls") >= 8
    # the original ten still exist under their old keys
    for key in (
        "first_light",
        "hatched",
        "bookworm",
        "closer",
        "scribe",
        "lab_rat",
        "week_long",
        "month_long",
        "well_rounded",
        "sage",
    ):
        assert key in ach.BY_KEY


def test_empty_database_unlocks_nothing_and_hides_secrets():
    rows = ach.evaluate(ach.gather_facts())
    assert not any(r["unlocked"] for r in rows)
    hidden = next(r for r in rows if r["key"] == "night_owl")
    assert hidden["title"] == "???" and "Hidden" in hidden["description"]
    assert all(0 <= r["progress"]["percent"] <= 100 for r in rows)


def test_facts_drive_unlocks_and_progress():
    from projects.tests.factories import ProjectFactory
    from research.models import Hypothesis

    project = ProjectFactory()
    Hypothesis.objects.create(project=project, statement="x", status="contradicted")
    for i in range(3):
        project.decisions.create(title=f"d{i}", decision="because")
    Pet.objects.update_or_create(pk=1, defaults={"name": "Nox"})
    rows = {r["key"]: r for r in ach.evaluate(ach.gather_facts())}
    assert rows["you_died"]["unlocked"] and rows["you_died"]["title"] == "You died"
    assert rows["named_it"]["unlocked"]
    assert rows["on_the_record"]["progress"] == {"current": 3, "target": 5, "percent": 60}


def test_record_unlocks_persists_first_sightings():
    from projects.tests.factories import ProjectFactory

    project = ProjectFactory()
    project.notes.create(title="n", body="")
    rows = ach.evaluate(ach.gather_facts())
    fresh = ach.record_unlocks(rows)
    assert "first_light" in fresh
    assert AchievementUnlock.objects.filter(key="first_light").exists()
    assert ach.record_unlocks(ach.evaluate(ach.gather_facts())) == []  # not new any more


def test_submission_story_achievements():
    from projects.tests.factories import ProjectFactory
    from writing.models import Manuscript, SubmissionEvent

    project = ProjectFactory()
    m = Manuscript.objects.create(project=project, title="Paper", status="published")
    d = datetime.date(2026, 1, 1)
    for i, kind in enumerate(
        [
            "submitted",
            "rejected",
            "submitted",
            "reviews_received",
            "revision_submitted",
            "accepted",
            "published",
        ]
    ):
        SubmissionEvent.objects.create(manuscript=m, kind=kind, date=d + datetime.timedelta(days=i))
    facts = ach.gather_facts()
    assert facts["rejected_then_accepted"] and facts["beat_reviewer_two"]
    assert not facts["clean_publication"]  # a rejection happened
    rows = {r["key"]: r for r in ach.evaluate(facts)}
    assert (
        rows["git_gud"]["unlocked"]
        and rows["reviewer_two"]["unlocked"]
        and rows["published"]["unlocked"]
    )
    assert not rows["no_hit_run"]["unlocked"]


def test_returned_after_gap_detection():
    today = datetime.date(2026, 9, 7)
    days = {today - datetime.timedelta(days=i) for i in range(8)}  # a week-long run
    days.add(today - datetime.timedelta(days=60))  # …after a long silence
    assert ach._returned_after_gap(days)
    assert not ach._returned_after_gap({today, today - datetime.timedelta(days=1)})


def test_score_rank_and_souls_counters():
    rows = [
        {"points": 5, "unlocked": True},
        {"points": 50, "unlocked": True},
        {"points": 25, "unlocked": False},
    ]
    assert ach.score(rows) == 55
    assert ach.rank(0)["name"] == "Undergrad" and ach.rank(0)["next"] == "Grad student"
    assert ach.rank(55)["name"] == "Grad student"
    assert ach.rank(900) == {"name": "Ashen One", "floor": 800, "next": None, "next_at": None}
    facts = {
        "rejections": 2,
        "contradicted": 1,
        "compiles_failed": 1,
        "milestones": 7,
        "accepted": 1,
        "lifetime": 40,
    }
    assert ach.souls_counters(facts) == {"deaths": 4, "bonfires": 7, "bosses": 1, "souls": 40}
    lines = ach.souls_speech(facts)
    assert any("4 deaths" in line for line in lines)


def test_pet_state_and_ledger_api(client_logged_in):
    state = client_logged_in.get("/api/v1/pet/").json()
    assert state["souls_mode"] is False and "rank" in state and "souls" in state
    assert len(state["achievements"]) >= 50
    on = client_logged_in.post(
        "/api/v1/pet/", {"souls_mode": True}, content_type="application/json"
    ).json()
    assert on["souls_mode"] is True and Pet.objects.get(pk=1).souls_mode
    assert on["speech"]  # the grim lines still speak
    ledger = client_logged_in.get("/api/v1/achievements/").json()
    assert ledger["total"] >= 50 and ledger["max_score"] > 500
    assert {t["key"] for t in ledger["tiers"]} == {"fun", "steady", "hard", "souls"}
    assert len(ledger["next_up"]) == 5 and ledger["souls_mode"] is True


def test_recent_unlocks_window(client_logged_in):
    AchievementUnlock.objects.create(key="first_light")
    AchievementUnlock.objects.filter(key="first_light").update(
        unlocked_at=timezone.now() - datetime.timedelta(days=3)
    )
    from projects.tests.factories import ProjectFactory

    ProjectFactory().notes.create(title="n", body="")
    ledger = client_logged_in.get("/api/v1/achievements/").json()
    assert "first_light" not in ledger["recent_unlocks"]  # old sighting, not new


def test_batch_two_progress_functions():
    """#388: the new combined-progress achievements read the facts they claim to."""
    by_key = {a.key: a for a in ach.CATALOGUE}
    assert len(ach.CATALOGUE) >= 85 and len(by_key) == len(ach.CATALOGUE)  # unique keys
    facts = {
        "evidence_for": 12,
        "evidence_against": 4,
        "rejections": 40,
        "contradicted": 50,
        "compiles_failed": 30,
        "compiles_ok": 5,
    }
    assert by_key["balanced_ledger"].progress(facts) == (4, 10)
    assert by_key["died_a_hundred"].progress(facts) == (120, 100)
    assert by_key["estus"].progress(facts) == (5, 20)
    assert by_key["anniversary"].hidden and by_key["dragonslayer"].tier == "souls"


def test_batch_two_facts_exist(db):
    facts = ach.gather_facts()
    for key in (
        "coloured_tags",
        "pdfs",
        "dois",
        "comments",
        "documents",
        "projects",
        "saved_views",
        "max_files_on_manuscript",
        "days_active",
        "first_day_age",
        "todos_done_today",
        "commented_highlights",
        "evidence_for",
        "evidence_against",
        "lunch_break",
        "midnight",
    ):
        assert key in facts, key


def test_batch_three_seasonal_souls_and_platinum(db):
    """#415: seasonal secrets read the calendar, souls trophies count only while the mode is
    on, and the platinum is every other trophy."""
    import datetime as dt

    facts = ach._seasonal_facts(
        {dt.date(2026, 1, 1), dt.date(2026, 2, 13), dt.date(2024, 2, 29), dt.date(2026, 12, 21)}
    )
    assert facts == {
        "new_year": True,
        "halloween": False,
        "solstice": True,
        "leap_day": True,
        "friday_13": True,  # 2026-02-13 is a Friday
    }
    assert ach._seasonal_facts(set()) == {k: False for k in facts}
    by_key = ach.BY_KEY
    assert by_key["no_bonfire"].tier == "souls" and by_key["the_dark_soul"].hidden
    assert by_key["platinum"] is ach.PLATINUM and ach.CATALOGUE[-1] is ach.PLATINUM
    # souls_since: set when the mode goes on, cleared when it goes off
    from core.models import Pet

    ach.set_souls_mode(True)
    pet = Pet.objects.get(pk=1)
    assert pet.souls_since is not None
    since = pet.souls_since
    ach.set_souls_mode(True)
    assert Pet.objects.get(pk=1).souls_since == since  # re-enabling keeps the original date
    live = ach.gather_facts()
    assert live["souls_on"] is True and live["souls_days"] == 0
    ach.set_souls_mode(False)
    assert Pet.objects.get(pk=1).souls_since is None
    # the platinum counts the rest: with nothing done it is 0/N; when everything else is
    # done it is N/N
    rows = ach.evaluate(ach.gather_facts())
    plat = next(r for r in rows if r["key"] == "platinum")
    assert plat["progress"] == {
        "current": 0,
        "target": len(ach.CATALOGUE) - 1,
        "percent": 0,
    }
    everything = {**ach.gather_facts(), **{k: 10**6 for k in _count_keys()}}
    rows = ach.evaluate(everything)
    unlocked_others = sum(1 for r in rows if r["unlocked"] and r["key"] != "platinum")
    plat = next(r for r in rows if r["key"] == "platinum")
    assert plat["progress"]["current"] == unlocked_others
    assert plat["unlocked"] == (unlocked_others == len(ach.CATALOGUE) - 1)


def _count_keys() -> set[str]:
    """Every fact key any achievement reads as a number (found by probing the lambdas)."""
    keys: set[str] = set()

    class Probe(dict):
        def get(self, key, default=None):
            keys.add(key)
            return 10**6

        def __getitem__(self, key):
            keys.add(key)
            return 10**6

    for a in ach.CATALOGUE:
        try:
            a.progress(Probe())
        except Exception:  # noqa: BLE001 - a probe, not a contract
            pass
    return keys
