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


class TestCitationSyncBot:
    def test_syncs_each_active_project(self, monkeypatch):
        from projects.tests.factories import ProjectFactory

        ProjectFactory(name="Active A", status="active")
        ProjectFactory(name="Done B", status="complete")
        synced = []

        class FakeState:
            message = "2/2 matched; 1 new edge(s)"
            status = "done"

        def fake_sync(project):
            synced.append(project.slug)
            return FakeState()

        monkeypatch.setattr("literature.sync.sync_project_citations", fake_sync)
        result = registry.run_citation_sync()
        assert synced == ["active-a"]
        assert "1 new edge" in result


class TestRunHistory:
    def test_runs_recorded_and_capped(self, monkeypatch):

        monkeypatch.setitem(
            registry.BOTS,
            "deadline-reminder",
            {**registry.BOTS["deadline-reminder"], "run": lambda: "ok"},
        )
        for _ in range(25):
            registry.run_bot("deadline-reminder")
        bot = Bot.objects.get(slug="deadline-reminder")
        assert bot.runs.count() == 20  # capped
        assert all(run.ok for run in bot.runs.all())

    def test_failed_run_marked(self, monkeypatch):
        from bots.models import BotRun

        monkeypatch.setitem(
            registry.BOTS,
            "retraction-watch",
            {**registry.BOTS["retraction-watch"], "run": lambda: 1 / 0},
        )
        registry.run_bot("retraction-watch")
        run = BotRun.objects.get()
        assert not run.ok
        assert "ZeroDivisionError" in run.result

    def test_history_rendered_on_page(self, client_logged_in, monkeypatch):
        monkeypatch.setitem(
            registry.BOTS,
            "deadline-reminder",
            {**registry.BOTS["deadline-reminder"], "run": lambda: "history works"},
        )
        registry.run_bot("deadline-reminder")
        response = client_logged_in.get(reverse("bots:automations"))
        content = response.content.decode()
        assert "Run history" in content
        assert "history works" in content


class TestHistoryChart:
    def test_count_parses_headline_number(self):
        from bots.models import BotRun

        run = BotRun(result="3 new reminder(s).")
        assert run.count == 3
        assert BotRun(result="25 DOI(s) checked, 1 retraction(s) flagged.").count == 25
        assert BotRun(result="no active projects.").count is None

    def test_chart_bars_scale_to_max(self):
        from bots.models import BotRun
        from bots.views import _history_bars

        runs = [  # newest-first, as the prefetch delivers them
            BotRun(result="4 new reminder(s)."),
            BotRun(result="failed: Boom", ok=False),
            BotRun(result="1 new reminder(s)."),
        ]
        bars = _history_bars(runs)
        assert [b["run"].result for b in bars] == [
            "1 new reminder(s).",
            "failed: Boom",
            "4 new reminder(s).",
        ]  # oldest first
        assert bars[2]["pct"] == 100
        assert bars[0]["pct"] == 25
        assert bars[1]["pct"] == 8  # floor keeps zero-count bars visible

    def test_chart_rendered_after_multiple_runs(self, client_logged_in, monkeypatch):
        monkeypatch.setitem(
            registry.BOTS,
            "deadline-reminder",
            {**registry.BOTS["deadline-reminder"], "run": lambda: "2 new reminder(s)."},
        )
        registry.run_bot("deadline-reminder")
        registry.run_bot("deadline-reminder")
        response = client_logged_in.get(reverse("bots:automations"))
        content = response.content.decode()
        assert "Run history chart" in content
        assert "bg-indigo-300" in content

    def test_failed_runs_charted_red(self, client_logged_in, monkeypatch):
        monkeypatch.setitem(
            registry.BOTS,
            "retraction-watch",
            {**registry.BOTS["retraction-watch"], "run": lambda: 1 / 0},
        )
        registry.run_bot("retraction-watch")
        registry.run_bot("retraction-watch")
        response = client_logged_in.get(reverse("bots:automations"))
        assert "bg-red-400" in response.content.decode()


class TestWeeklyDigestBot:
    def test_posts_last_weeks_summary(self):
        import datetime

        from django.utils import timezone

        from bots import registry
        from notes.models import QuickCapture

        # a milestone completed LAST week (Mon-Sun before this one)
        last_week = timezone.now() - datetime.timedelta(days=8)
        from plans.tests.factories import MilestoneFactory

        MilestoneFactory(title="Done last week", completed_at=last_week)
        result = registry.run_weekly_digest()
        assert "milestones" in result
        assert QuickCapture.objects.filter(text__contains="Last week").exists()

    def test_quiet_week_posts_nothing(self):
        from bots import registry
        from notes.models import QuickCapture

        result = registry.run_weekly_digest()
        assert "quiet" in result
        assert not QuickCapture.objects.filter(text__contains="Last week").exists()

    def test_registered_in_bots(self):
        from bots.registry import BOTS

        assert "weekly-digest" in BOTS
