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
