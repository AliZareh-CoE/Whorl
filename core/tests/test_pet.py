"""Owner idea #12: the Atlas pet — derived state, no nagging."""

import pytest
from django.urls import reverse
from django.utils import timezone

from core.pet import pet_state

pytestmark = pytest.mark.django_db


class TestPetState:
    def test_fresh_database_is_a_sleeping_egg(self):
        state = pet_state()
        assert state["stage"] == "egg"
        assert state["mood"] == "sleeping"
        assert state["name"] == "Mochi"

    def test_recent_activity_wakes_and_evolves_it(self):
        from plans.tests.factories import MilestoneFactory

        MilestoneFactory.create_batch(4, completed_at=timezone.now())  # 12 pts this week
        state = pet_state()
        assert state["stage"] == "hatchling"  # 12 lifetime
        assert state["mood"] == "thriving"  # 12 weekly
        assert state["to_next_stage"] == 28

    def test_old_activity_counts_for_stage_not_mood(self, monkeypatch):
        from plans.tests.factories import MilestoneFactory

        old = timezone.now() - timezone.timedelta(days=30)
        milestones = MilestoneFactory.create_batch(4, completed_at=old)
        # force created_at back too (auto_now_add)
        for m in milestones:
            type(m).objects.filter(pk=m.pk).update(completed_at=old)
        state = pet_state()
        assert state["stage"] == "hatchling"
        assert state["mood"] == "sleeping"

    def test_state_is_cached(self, django_assert_num_queries):
        pet_state()  # warm
        with django_assert_num_queries(0):
            pet_state()


class TestPetPage:
    def test_page_renders(self, client_logged_in):
        response = client_logged_in.get(reverse("core:pet"))
        content = response.content.decode()
        assert "Mochi" in content
        assert "never nags" in content

    def test_rename(self, client_logged_in):
        response = client_logged_in.post(reverse("core:pet"), {"name": "Kepler"})
        assert response.status_code == 302
        assert pet_state()["name"] == "Kepler"

    def test_sidebar_widget_everywhere(self, client_logged_in):
        response = client_logged_in.get(reverse("core:dashboard"))
        assert b"Mochi" in response.content


class TestPetSpeech:
    def test_always_has_a_line(self):
        from core.pet import pet_speech

        assert isinstance(pet_speech(), str) and pet_speech()

    def test_overdue_milestones_mentioned_gently(self):
        import datetime

        from django.utils import timezone

        from core.pet import _speech_candidates
        from plans.tests.factories import MilestoneFactory

        MilestoneFactory(due_date=timezone.localdate() - datetime.timedelta(days=2))
        MilestoneFactory(due_date=timezone.localdate() - datetime.timedelta(days=9))
        lines = _speech_candidates(timezone.localtime())
        assert any("past due" in line for line in lines)
        assert not any("hurry" in line.lower() for line in lines)

    def test_stable_within_the_hour(self):
        from django.utils import timezone

        from core.pet import pet_speech

        now = timezone.localtime()
        assert pet_speech(now) == pet_speech(now)

    def test_speech_rendered_in_sidebar_and_pet_page(self, client_logged_in):
        from django.core.cache import cache
        from django.urls import reverse

        cache.delete("atlas-pet-state")
        response = client_logged_in.get(reverse("core:dashboard"))
        content = response.content.decode()
        assert "pet-body" in content  # the inline-SVG pet (Owner idea #27), not an emoji
        assert "“" in content  # the sidebar speech line
        page = client_logged_in.get(reverse("core:pet")).content.decode()
        assert "pet-body" in page


class TestBuddyPersonality:
    """Owner idea #23: Buddy-style stats, rotating lines, and reaction one-liners."""

    def test_state_includes_stats_lines_and_reactions(self):
        from core.pet import REACTION_LINES, pet_state

        state = pet_state()
        assert set(state["stats"]) == {"wisdom", "focus", "curiosity", "grit"}
        assert all(0 <= v <= 10 for v in state["stats"].values())
        assert state["dominant_stat"] in state["stats"]
        assert isinstance(state["speech_lines"], list) and state["speech_lines"]
        assert state["speech"] == state["speech_lines"][0]
        assert set(state["reactions"]) == set(REACTION_LINES)
        for kind, line in state["reactions"].items():
            assert line in REACTION_LINES[kind]

    def test_stats_grow_with_work(self):
        from django.utils import timezone

        from core.pet import pet_stats
        from plans.tests.factories import MilestoneFactory

        assert pet_stats()["focus"] == 0
        MilestoneFactory(completed_at=timezone.now())
        assert pet_stats()["focus"] == 1

    def test_level_curve_caps_at_ten(self):
        from core.pet import _level

        assert _level(0) == 0
        assert _level(1) == 1
        assert _level(99) == 9
        assert _level(100) == 10
        assert _level(10_000) == 10


class TestHabitSignals:
    """#419: streak, unusual hour and today's writing show up in Mochi's lines."""

    def _note_at(self, project, when, title):
        from notes.models import Note

        note = Note.objects.create(project=project, title=title, body="x")
        Note.objects.filter(pk=note.pk).update(created_at=when, updated_at=when)
        return note

    def test_streak_and_words_lines(self):
        import datetime as dt

        from django.utils import timezone

        from core.pet import _speech_candidates
        from projects.tests.factories import ProjectFactory
        from writing.models import Manuscript
        from writing.progress import record_words

        project = ProjectFactory()
        now = timezone.localtime()
        for i in range(4):
            self._note_at(project, now - dt.timedelta(days=i), f"day {i}")
        ms = Manuscript.objects.create(project=project, title="Paper")
        record_words(ms, 100, now.date() - dt.timedelta(days=1))
        record_words(ms, 340, now.date())
        lines = _speech_candidates(now)
        assert any("days running" in line for line in lines)
        assert any("+240 words today" in line for line in lines)

    def test_unusual_hour_line(self):
        import datetime as dt

        from django.utils import timezone

        from core.pet import _speech_candidates
        from projects.tests.factories import ProjectFactory

        project = ProjectFactory()
        now = timezone.localtime()
        for offset in (5, 6, 7):  # three usual hours, none of them now
            when = (now - dt.timedelta(days=10)).replace(hour=(now.hour + offset) % 24)
            self._note_at(project, when, f"note {offset}")
        assert any("Not your usual hour" in line for line in _speech_candidates(now))
        # activity at this hour makes it usual: the line goes away
        self._note_at(project, now - dt.timedelta(days=3), "now-ish")
        assert not any("Not your usual hour" in line for line in _speech_candidates(now))
