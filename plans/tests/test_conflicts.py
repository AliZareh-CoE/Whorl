"""#513 — dates that contradict dependencies: detection, cascading fix, API, MCP, page."""

import datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from plans.dependencies import date_conflicts, resolve_conflicts, set_blockers
from plans.models import Milestone
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

D = datetime.date


def _chain():
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project)
    ethics = MilestoneFactory(phase=phase, title="Ethics", due_date=D(2026, 10, 1))
    pilot = MilestoneFactory(phase=phase, title="Pilot", due_date=D(2026, 9, 20))  # before ethics
    sample = MilestoneFactory(phase=phase, title="Sample", due_date=D(2026, 10, 2))  # fine now
    undated = MilestoneFactory(phase=phase, title="Undated", due_date=None)
    set_blockers(pilot, [ethics.pk])
    set_blockers(sample, [pilot.pk])
    set_blockers(undated, [sample.pk])
    return project, ethics, pilot, sample, undated


def test_date_conflicts_flag_only_dates_before_an_open_dated_blocker():
    project, ethics, pilot, sample, undated = _chain()
    rows = date_conflicts(project)
    assert [(r["title"], r["blocker_title"], r["suggested"]) for r in rows] == [
        ("Pilot", "Ethics", D(2026, 10, 2))
    ]
    ethics.completed_at = timezone.now()
    ethics.save()
    assert date_conflicts(project) == []  # a completed blocker no longer constrains


def test_resolve_conflicts_cascades_in_dependency_order():
    project, ethics, pilot, sample, undated = _chain()
    changes = resolve_conflicts(project)
    assert [(c["title"], c["from"], c["to"]) for c in changes] == [
        ("Pilot", D(2026, 9, 20), D(2026, 10, 2)),
        ("Sample", D(2026, 10, 2), D(2026, 10, 3)),  # pushed by the pilot's new date
    ]
    assert Milestone.objects.get(pk=undated.pk).due_date is None  # undated stays undated
    assert date_conflicts(project) == [] and resolve_conflicts(project) == []


def test_conflicts_over_the_api(owner):
    project, ethics, pilot, sample, undated = _chain()
    client = APIClient(HTTP_HOST="127.0.0.1")
    assert client.post("/api/v1/projects/deep/plan/reschedule-conflicts/").status_code == 401
    client.credentials(HTTP_X_API_KEY=settings.ATLAS_API_KEY)
    plan = client.get("/api/v1/projects/deep/plan/").json()
    assert [c["title"] for c in plan["conflicts"]] == ["Pilot"]
    assert plan["conflicts"][0]["suggested"] == "2026-10-02"
    out = client.post("/api/v1/projects/deep/plan/reschedule-conflicts/").json()
    assert [c["to"] for c in out["changes"]] == ["2026-10-02", "2026-10-03"]
    assert client.get("/api/v1/projects/deep/plan/").json()["conflicts"] == []
    assert client.post("/api/v1/projects/nope/plan/reschedule-conflicts/").status_code == 404


def test_plan_page_shows_the_conflict_banner():
    plan = (Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Plan.tsx").read_text()
    for needle in (
        'data-testid="conflict-banner"',
        'data-testid="conflict-fix"',
        'data-testid="conflict-chip"',
        "plan/reschedule-conflicts/",
    ):
        assert needle in plan, needle
