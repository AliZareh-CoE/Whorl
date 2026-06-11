"""Owner idea #84: the weekly research review data layer."""

import datetime

import pytest
from django.utils import timezone

from core.reviews import weekly_review

pytestmark = pytest.mark.django_db


def _this_week_date():
    today = timezone.localdate()
    return today - datetime.timedelta(days=today.weekday())  # monday


class TestWeeklyReview:
    def test_collects_this_weeks_items(self):
        from notes.tests.factories import NoteFactory
        from plans.tests.factories import MilestoneFactory

        note = NoteFactory(title="This week's note")
        MilestoneFactory(title="Shipped this week", completed_at=timezone.now())
        data = weekly_review()
        assert any(n["title"] == "This week's note" for n in data["notes_written"])
        assert any(m["title"] == "Shipped this week" for m in data["milestones_done"])

    def test_scoped_to_project(self):
        from notes.tests.factories import NoteFactory

        mine = NoteFactory(title="Mine")
        NoteFactory(title="Theirs")  # different project
        data = weekly_review(project=mine.project)
        titles = [n["title"] for n in data["notes_written"]]
        assert "Mine" in titles and "Theirs" not in titles

    def test_last_week_excludes_this_week(self):
        from notes.tests.factories import NoteFactory

        NoteFactory(title="Fresh")
        data = weekly_review(weeks_back=1)
        assert all(n["title"] != "Fresh" for n in data["notes_written"])
        # window is the prior Mon-Sun
        assert data["weeks_back"] == 1

    def test_window_dates_present(self):
        data = weekly_review()
        assert "start" in data and "end" in data


class TestWeeklyReviewAPI:
    def test_endpoint_shape_and_scoping(self, client_logged_in):
        from notes.tests.factories import NoteFactory

        note = NoteFactory(title="API week note")
        data = client_logged_in.get(f"/api/v1/weekly-review/?project={note.project.slug}").json()
        assert {
            "papers_read",
            "notes_written",
            "milestones_done",
            "decisions",
            "experiments",
        } <= set(data)
        assert any(n["title"] == "API week note" for n in data["notes_written"])

    def test_requires_login(self, client):
        assert client.get("/api/v1/weekly-review/").status_code == 401
