"""#491 — the daily brief."""

import datetime
from pathlib import Path

import pytest

from core.brief import daily_brief
from core.models import TodoItem
from literature.models import ProjectReference
from literature.tests.factories import ReferenceFactory
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory
from writing.models import Manuscript

pytestmark = pytest.mark.django_db
TODAY = datetime.date(2026, 9, 13)


def test_daily_brief_reads_like_a_morning_note(client_logged_in):
    project = ProjectFactory(name="Attention", status="active")
    phase = PhaseFactory(project=project, name="Pilot", status="in_progress")
    MilestoneFactory(
        phase=phase, title="Data collected", due_date=TODAY - datetime.timedelta(days=4)
    )
    MilestoneFactory(phase=phase, title="Ethics filed", due_date=TODAY + datetime.timedelta(days=3))
    TodoItem.objects.create(text="Email the lab", project=project)
    ProjectReference.objects.create(
        project=project,
        reference=ReferenceFactory(title="Load theory", year=2010),
        reading_status="to_read",
        priority="high",
    )
    Manuscript.objects.create(
        project=project,
        title="Paper A",
        status="drafting",
        deadline=TODAY + datetime.timedelta(days=9),
    )
    out = daily_brief(today=TODAY)
    md = out["markdown"]
    assert md.startswith("# Brief — Sunday, September 13\n")
    assert "## Needs you\n- Overdue: Data collected (Attention, due 2026-09-09)" in md
    assert "## On your list\n- [ ] Email the lab · Attention" in md
    assert "## This week, everywhere" in md and "- Ethics filed — Attention · due in 3 d" in md
    assert "## Next to read (1 unread)\n- Load theory (" in md
    assert "2010) — Attention · high priority" in md
    assert "## Writing (1 live)\n- Paper A — drafting · Attention · deadline in 9 d" in md
    assert "## Projects\n- Attention — Pilot · 0/2 milestones" in md
    assert "## This month" in md and "papers read" in md
    assert out["needs"] >= 1 and out["todos"] == 1 and out["reading"] == 1 and out["writing"] == 1
    assert daily_brief(today=TODAY)["date"] == "2026-09-13"
    r = client_logged_in.get("/api/v1/dashboard/brief/")
    assert r.status_code == 200 and r.json()["markdown"].startswith("# Brief — ")


def test_daily_brief_on_an_empty_atlas():
    out = daily_brief(today=TODAY)
    md = out["markdown"]
    assert "## Needs you\n- Nothing — all clear." in md
    assert "## On your list" not in md and "## Writing" not in md and "## Projects" not in md
    assert "(= last month)" in md and out["needs"] == 0


def test_dashboard_offers_the_brief():
    tsx = Path("frontend/src/app/pages/Dashboard.tsx").read_text()
    for needle in (
        "Copy today's brief",
        "/dashboard/brief/",
        "navigator.clipboard.writeText",
        'data-testid="daily-brief"',
    ):
        assert needle in tsx, needle
