"""[REV] cycle 145: the dashboard's Needs-attention lead — the answer, not data."""

import datetime

import pytest
from django.utils import timezone

from core.dashboard import needs_attention
from notes.models import QuickCapture
from plans.tests.factories import MilestoneFactory, PhaseFactory
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


class TestNeedsAttention:
    def test_overdue_milestone_is_flagged(self):
        m = MilestoneFactory(due_date=TODAY - datetime.timedelta(days=3))
        attention = needs_attention()
        assert m in attention["overdue"]
        assert not attention["empty"]

    def test_completed_and_future_milestones_are_not_overdue(self):
        MilestoneFactory(
            due_date=TODAY - datetime.timedelta(days=3),
            completed_at=timezone.now(),
        )
        MilestoneFactory(due_date=TODAY + datetime.timedelta(days=3))
        assert needs_attention()["overdue"] == []

    def test_archived_project_milestones_are_ignored(self):
        phase = PhaseFactory(project__status="archived")
        MilestoneFactory(phase=phase, due_date=TODAY - datetime.timedelta(days=3))
        assert needs_attention()["overdue"] == []

    def test_deadline_inside_window_is_flagged(self):
        ms = ManuscriptFactory(deadline=TODAY + datetime.timedelta(days=10))
        far = ManuscriptFactory(deadline=TODAY + datetime.timedelta(days=60))
        published = ManuscriptFactory(
            deadline=TODAY + datetime.timedelta(days=2), status="published"
        )
        deadlines = needs_attention()["deadlines"]
        assert ms in deadlines
        assert far not in deadlines
        assert published not in deadlines

    def test_untriaged_inbox_items_surface_processed_do_not(self):
        keep = QuickCapture.objects.create(text="check that preprint")
        QuickCapture.objects.create(text="done already", processed=True)
        inbox = needs_attention()["inbox"]
        assert keep in inbox
        assert len(inbox) == 1

    def test_all_clear_reports_empty(self):
        attention = needs_attention()
        assert attention["empty"]


class TestDashboardLead:
    def test_dashboard_shows_needs_attention(self, client_logged_in):
        phase = PhaseFactory(project__status="active")
        MilestoneFactory(
            phase=phase,
            title="Pilot data collected",
            due_date=TODAY - datetime.timedelta(days=2),
        )
        response = client_logged_in.get("/classic/")
        content = response.content.decode()
        assert response.status_code == 200
        assert "Needs attention" in content
        assert "Pilot data collected" in content

    def test_dashboard_all_clear_line(self, client_logged_in):
        PhaseFactory(project__status="active")  # an active project, nothing urgent
        response = client_logged_in.get("/classic/")
        assert "All clear" in response.content.decode()
