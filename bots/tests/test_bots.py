import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from bots import registry
from bots.models import Bot
from notes.models import QuickCapture

pytestmark = pytest.mark.django_db


class TestDeadlineReminderBot:
    def test_creates_reminders_for_imminent_deadlines(self):
        from plans.tests.factories import MilestoneFactory
        from writing.tests.factories import ManuscriptFactory

        today = timezone.localdate()
        MilestoneFactory(title="Due soon", due_date=today + datetime.timedelta(days=2))
        MilestoneFactory(title="Far away", due_date=today + datetime.timedelta(days=30))
        MilestoneFactory(
            title="Already done",
            due_date=today + datetime.timedelta(days=1),
            completed_at=timezone.now(),
        )
        ManuscriptFactory(title="Paper due", deadline=today + datetime.timedelta(days=5))
        result = registry.run_deadline_reminder()
        assert result == "2 new reminder(s)."
        texts = list(QuickCapture.objects.values_list("text", flat=True))
        assert any("Due soon" in t for t in texts)
        assert any("Paper due" in t for t in texts)
        assert not any("Far away" in t for t in texts)

    def test_reminders_dedupe_across_runs(self):
        from plans.tests.factories import MilestoneFactory

        MilestoneFactory(
            title="Once only", due_date=timezone.localdate() + datetime.timedelta(days=1)
        )
        registry.run_deadline_reminder()
        result = registry.run_deadline_reminder()
        assert result == "0 new reminder(s)."
        assert QuickCapture.objects.count() == 1


class TestRetractionWatchBot:
    def test_flags_retractions_to_inbox(self, monkeypatch):
        from literature.tests.factories import ReferenceFactory

        ref = ReferenceFactory(doi="10.1/bad")
        monkeypatch.setattr(
            "literature.services.check_retractions",
            lambda refs: [
                {
                    "check": "retraction",
                    "level": "error",
                    "message": f"“{ref.bibtex_key}” appears to be RETRACTED",
                    "references": [ref],
                }
            ],
        )
        result = registry.run_retraction_watch()
        assert "1 retraction(s) flagged" in result
        assert QuickCapture.objects.filter(text__contains="RETRACTED").exists()


class TestRunner:
    def test_run_bot_records_state_and_survives_crash(self, monkeypatch):
        monkeypatch.setitem(
            registry.BOTS,
            "deadline-reminder",
            {**registry.BOTS["deadline-reminder"], "run": lambda: 1 / 0},
        )
        result = registry.run_bot("deadline-reminder")
        assert result.startswith("failed: ZeroDivisionError")
        state = Bot.objects.get(slug="deadline-reminder")
        assert state.last_run_at is not None
        assert "ZeroDivisionError" in state.last_result

    def test_run_enabled_bots_skips_disabled(self, monkeypatch):
        Bot.objects.create(slug="deadline-reminder", enabled=True)
        Bot.objects.create(slug="retraction-watch", enabled=False)
        ran = registry.run_enabled_bots()
        assert len(ran) == 1
        assert ran[0].startswith("deadline-reminder:")


class TestViews:
    def test_page_lists_bots(self, client_logged_in):
        response = client_logged_in.get(reverse("bots:automations"))
        content = response.content.decode()
        assert "Deadline reminder" in content
        assert "Retraction watch" in content

    def test_toggle_and_run_now(self, client_logged_in):
        response = client_logged_in.post(reverse("bots:toggle", args=["deadline-reminder"]))
        assert response.status_code == 302
        assert Bot.objects.get(slug="deadline-reminder").enabled

        response = client_logged_in.post(reverse("bots:run_now", args=["deadline-reminder"]))
        assert response.status_code == 302
        assert Bot.objects.get(slug="deadline-reminder").last_run_at is not None

    def test_unknown_bot_rejected(self, client_logged_in):
        response = client_logged_in.post(reverse("bots:toggle", args=["nope"]), follow=True)
        assert b"Unknown bot" in response.content


def test_overdue_milestones_also_remind():
    from plans.tests.factories import MilestoneFactory

    MilestoneFactory(title="Slipped", due_date=timezone.localdate() - datetime.timedelta(days=4))
    result = registry.run_deadline_reminder()
    assert result == "1 new reminder(s)."
    assert QuickCapture.objects.filter(text__contains="OVERDUE").exists()
