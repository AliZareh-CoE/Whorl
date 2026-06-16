"""iCalendar (.ics) deadline export (Backlog #9 — the calendar half)."""

from datetime import date

import pytest

from core.calendar import _escape, _fold, build_project_ics
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    settings.ATLAS_API_KEY = KEY


def test_escape_handles_special_chars():
    assert _escape("a, b; c\\d\ne") == "a\\, b\\; c\\\\d\\ne"
    assert _escape("") == ""


def test_fold_breaks_long_lines_at_75_octets():
    folded = _fold("SUMMARY:" + "x" * 200)
    for piece in folded.split("\r\n"):
        assert len(piece.encode("utf-8")) <= 75
    # continuations are marked with a leading space
    assert "\r\n " in folded


def test_build_ics_includes_milestones_and_deadlines():
    project = ProjectFactory()
    phase = PhaseFactory(project=project)
    MilestoneFactory(phase=phase, title="Pilot data", due_date=date(2026, 7, 1))
    ManuscriptFactory(project=project, title="NeurIPS paper", deadline=date(2026, 5, 15))

    ics = build_project_ics(project)

    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.endswith("END:VCALENDAR\r\n")
    assert "DTSTART;VALUE=DATE:20260701" in ics
    assert "SUMMARY:Milestone: Pilot data" in ics
    assert "DTSTART;VALUE=DATE:20260515" in ics
    assert "SUMMARY:Deadline: NeurIPS paper" in ics
    # two events
    assert ics.count("BEGIN:VEVENT") == 2


def test_build_ics_skips_items_without_dates_and_other_projects():
    project = ProjectFactory()
    other = ProjectFactory()
    phase = PhaseFactory(project=project)
    MilestoneFactory(phase=phase, due_date=None)  # no date → skipped
    MilestoneFactory(phase=PhaseFactory(project=other), due_date=date(2026, 7, 1))  # other project
    ManuscriptFactory(project=project, deadline=None)  # no deadline → skipped

    ics = build_project_ics(project)
    assert ics.count("BEGIN:VEVENT") == 0


def test_completed_milestone_marked_confirmed_with_check():
    from django.utils import timezone

    project = ProjectFactory()
    phase = PhaseFactory(project=project)
    MilestoneFactory(
        phase=phase, title="Done thing", due_date=date(2026, 7, 1), completed_at=timezone.now()
    )
    ics = build_project_ics(project)
    assert "SUMMARY:✓ Milestone: Done thing" in ics
    assert "STATUS:CONFIRMED" in ics


def test_escaped_summary_in_feed():
    project = ProjectFactory()
    phase = PhaseFactory(project=project)
    MilestoneFactory(phase=phase, title="A, B; C", due_date=date(2026, 7, 1))
    ics = build_project_ics(project)
    assert "SUMMARY:Milestone: A\\, B\\; C" in ics


def test_calendar_endpoint_serves_text_calendar(client):
    project = ProjectFactory()
    phase = PhaseFactory(project=project)
    MilestoneFactory(phase=phase, title="Endpoint check", due_date=date(2026, 7, 1))

    resp = client.get(f"/api/v1/projects/{project.slug}/calendar.ics/", **HEADERS)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/calendar"
    assert resp["Content-Disposition"] == f'inline; filename="{project.slug}.ics"'
    body = resp.content.decode()
    assert "BEGIN:VCALENDAR" in body
    assert "SUMMARY:Milestone: Endpoint check" in body


def test_calendar_endpoint_requires_api_key(client):
    project = ProjectFactory()
    assert client.get(f"/api/v1/projects/{project.slug}/calendar.ics/").status_code == 401
