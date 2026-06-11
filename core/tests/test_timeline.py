"""[REV] cycle 95: the research timeline data layer + endpoint."""

import datetime

import pytest
from django.utils import timezone

from core.timeline import project_timeline, timeline_markdown

pytestmark = pytest.mark.django_db


class TestProjectTimeline:
    def test_collects_events_across_apps_newest_first(self):
        from notes.tests.factories import NoteFactory
        from plans.tests.factories import MilestoneFactory
        from projects.models import DecisionRecord

        milestone = MilestoneFactory(title="Pilot done", completed_at=timezone.now())
        project = milestone.phase.project
        NoteFactory(project=project, title="First note")
        DecisionRecord.objects.create(
            project=project,
            title="Use mixed models",
            decision="lme4",
            decided_on=datetime.date(2020, 1, 1),
        )
        events = project_timeline(project)
        kinds = {e["kind"] for e in events}
        assert {"milestone", "note", "decision"} <= kinds
        dates = [e["date"] for e in events]
        assert dates == sorted(dates, reverse=True)
        assert events[-1]["label"] == "Use mixed models"  # oldest event last

    def test_incomplete_milestones_and_other_projects_excluded(self):
        from plans.tests.factories import MilestoneFactory

        pending = MilestoneFactory(title="Not yet")
        other = MilestoneFactory(title="Else", completed_at=timezone.now())
        events = project_timeline(pending.phase.project)
        labels = [e["label"] for e in events]
        assert "Not yet" not in labels and other.title not in labels

    def test_paper_read_only_when_later_than_added(self):
        from literature.tests.factories import ProjectReferenceFactory

        link = ProjectReferenceFactory(reading_status="read")
        events = project_timeline(link.project)
        kinds = [e["kind"] for e in events]
        # Created and marked read at the same instant — only the add event shows.
        assert kinds.count("paper_added") == 1 and "paper_read" not in kinds

    def test_markdown_is_oldest_first_and_paste_ready(self):
        from plans.tests.factories import MilestoneFactory

        milestone = MilestoneFactory(title="Data collected", completed_at=timezone.now())
        project = milestone.phase.project
        text = timeline_markdown(project, project_timeline(project))
        assert text.startswith(f"# Timeline — {project.name}")
        assert "milestone: Data collected" in text

    def test_api_endpoint_returns_events_and_markdown(self, client, owner, settings):
        settings.ATLAS_API_KEY = "k"
        from plans.tests.factories import MilestoneFactory

        milestone = MilestoneFactory(title="Shipped", completed_at=timezone.now())
        slug = milestone.phase.project.slug
        data = client.get(f"/api/v1/projects/{slug}/timeline/", HTTP_X_API_KEY="k").json()
        assert any(e["label"] == "Shipped" for e in data["events"])
        assert "Shipped" in data["markdown"]
        assert data["events"][0]["url"].startswith("/")

    def test_mcp_client_get_timeline(self, monkeypatch):
        from mcp_server import client as mcp_client

        monkeypatch.setenv("ATLAS_API_KEY", "k")
        seen = {}

        def fake_request(method, path, **kwargs):
            seen["call"] = (method, path)
            return {"events": [], "markdown": "# Timeline"}

        monkeypatch.setattr(mcp_client, "_request", fake_request)
        assert mcp_client.get_timeline("demo")["markdown"] == "# Timeline"
        assert seen["call"] == ("GET", "/projects/demo/timeline/")
