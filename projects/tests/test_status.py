"""#482 — the paste-ready status update."""

import datetime
from pathlib import Path

import pytest
from django.utils import timezone

from plans.tests.factories import MilestoneFactory, PhaseFactory, ResearchQuestionFactory
from projects.status import status_update
from projects.tests.factories import ProjectFactory
from writing.models import Manuscript, SubmissionEvent

pytestmark = pytest.mark.django_db
TODAY = datetime.date(2026, 9, 13)


def _project():
    project = ProjectFactory(name="Attention")
    phase = PhaseFactory(project=project, name="Pilot", status="in_progress")
    MilestoneFactory(
        phase=phase,
        title="Paradigm built",
        completed_at=timezone.now() - datetime.timedelta(days=2),
    )
    MilestoneFactory(
        phase=phase, title="Data collected", due_date=TODAY - datetime.timedelta(days=4)
    )
    MilestoneFactory(
        phase=phase, title="Analysis frozen", due_date=TODAY + datetime.timedelta(days=20)
    )
    ResearchQuestionFactory(project=project, question="Is load strategic?", status="open")
    ResearchQuestionFactory(project=project, question="Settled", status="answered")
    m = Manuscript.objects.create(
        project=project, title="Paper A", status="under_review", target_venue="JEP:G"
    )
    SubmissionEvent.objects.create(
        manuscript=m, kind="submitted", date=TODAY - datetime.timedelta(days=30)
    )
    return project


def test_status_update_reads_like_a_weekly_note():
    project = _project()
    out = status_update(project, days=7, today=TODAY)
    md = out["markdown"]
    assert md.startswith("# Attention — status, 2026-09-06 → 2026-09-13\n")
    assert "**Phase:** Pilot (" in md and ") · project 1/3 milestones" in md
    assert "**Manuscript:** Paper A — under review, at JEP:G, 30 d under review" in md
    assert "## Done in the last 7 days" in md and "**Milestones**\n- Paradigm built (Pilot)" in md
    assert "## Next" in md and "- Data collected — Pilot · overdue 4 d" in md
    assert "- Analysis frozen — Pilot · due in 20 d" in md
    assert "## Open questions\n- Is load strategic?" in md and "Settled" not in md
    assert "## Blockers\n- Data collected — overdue 4 d" in md
    assert out["since"] == "2026-09-06" and out["days"] == 7
    assert out["done"] == 1 and out["next"] == 2 and out["blockers"] == 1


def test_status_update_window_and_empty_project():
    project = _project()
    out = status_update(project, days=1, today=TODAY)
    assert out["done"] == 0 and "- Nothing logged in this window." in out["markdown"]
    assert status_update(project, days=500, today=TODAY)["days"] == 90
    bare = status_update(ProjectFactory(name="Bare"), today=TODAY)
    md = bare["markdown"]
    assert "**Plan:** no phases yet" in md and "the plan needs its next milestones" in md
    assert "## Open questions" not in md and "## Blockers" not in md


def test_status_update_api(client_logged_in):
    project = _project()
    r = client_logged_in.get(f"/api/v1/projects/{project.slug}/status-update/?days=14")
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 14 and body["markdown"].startswith("# Attention — status, 2026-08-30")
    assert (
        client_logged_in.get(f"/api/v1/projects/{project.slug}/status-update/?days=x").status_code
        == 400
    )
    assert (
        client_logged_in.get(f"/api/v1/projects/{project.slug}/status-update/").json()["days"] == 7
    )


def test_overview_menu_offers_the_status_update():
    tsx = Path("frontend/src/app/pages/ProjectOverview.tsx").read_text()
    for needle in (
        "Copy status update",
        "/status-update/",
        "navigator.clipboard.writeText",
        "noticeDialog",
    ):
        assert needle in tsx, needle
