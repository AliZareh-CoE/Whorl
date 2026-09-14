"""#516 — plan drift: the due-date log, baselines, slip and the report."""

import datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from plans.drift import baseline_of, drift_report, project_drift, record_move
from plans.models import Milestone, MilestoneDateChange
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
D = datetime.date


def test_saving_a_new_due_date_logs_the_move_and_equal_saves_do_not():
    m = MilestoneFactory(due_date=D(2026, 10, 1))
    assert m.date_changes.count() == 0  # creating a dated milestone is not a move
    m = Milestone.objects.get(pk=m.pk)
    m.save()  # outline round-trips re-save unchanged milestones
    m.title = "Renamed"
    m.save(update_fields=["title", "updated_at"])
    assert m.date_changes.count() == 0
    m.due_date = D(2026, 10, 13)
    m.save()
    change = m.date_changes.get()
    assert (change.from_date, change.to_date) == (D(2026, 10, 1), D(2026, 10, 13))
    m.toggle_completed()  # update_fields without due_date: nothing logged
    assert m.date_changes.count() == 1


def test_moves_within_ten_minutes_fold_and_an_undo_leaves_no_trace():
    m = MilestoneFactory(due_date=D(2026, 10, 1))
    m = Milestone.objects.get(pk=m.pk)
    m.due_date = D(2026, 10, 2)
    m.save()
    m.due_date = D(2026, 10, 5)  # a second nudge on the same instance
    m.save()
    change = m.date_changes.get()
    assert (change.from_date, change.to_date) == (D(2026, 10, 1), D(2026, 10, 5))
    m.due_date = D(2026, 10, 1)  # dragged back to where it started
    m.save()
    assert m.date_changes.count() == 0
    # an old move is not folded into
    MilestoneDateChange.objects.create(
        milestone=m,
        from_date=D(2026, 9, 1),
        to_date=D(2026, 10, 1),
        changed_at=timezone.now() - datetime.timedelta(hours=2),
    )
    assert record_move(m, D(2026, 10, 1), D(2026, 10, 20)) is not None
    assert m.date_changes.count() == 2


def test_baseline_is_the_first_recorded_date():
    m = MilestoneFactory(due_date=None)
    m = Milestone.objects.get(pk=m.pk)
    m.due_date = D(2026, 10, 1)  # dated after creation: that is the baseline, not a slip
    m.save()
    changes = list(m.date_changes.all())
    assert baseline_of(changes, m.due_date) == D(2026, 10, 1)
    assert baseline_of([], None) is None and baseline_of([], D(2026, 1, 1)) == D(2026, 1, 1)
    older = MilestoneDateChange(from_date=D(2026, 9, 1), to_date=D(2026, 9, 5))
    assert baseline_of([older, *changes], m.due_date) == D(2026, 9, 1)


def _plan():
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project, name="Collection")
    pilot = MilestoneFactory(phase=phase, title="Pilot", due_date=D(2026, 10, 21))
    sample = MilestoneFactory(phase=phase, title="Sample", due_date=D(2026, 12, 1))
    early = MilestoneFactory(phase=phase, title="Early", due_date=D(2026, 11, 1))
    MilestoneFactory(phase=phase, title="Undated", due_date=None)
    long_ago = timezone.now() - datetime.timedelta(days=30)
    MilestoneDateChange.objects.bulk_create(
        [
            MilestoneDateChange(
                milestone=pilot,
                from_date=D(2026, 10, 1),
                to_date=D(2026, 10, 9),
                changed_at=long_ago,
            ),
            MilestoneDateChange(
                milestone=pilot,
                from_date=D(2026, 10, 9),
                to_date=D(2026, 10, 21),
                changed_at=long_ago + datetime.timedelta(days=5),
            ),
            MilestoneDateChange(
                milestone=sample,
                from_date=D(2026, 11, 20),
                to_date=D(2026, 12, 1),
                changed_at=long_ago,
            ),
            MilestoneDateChange(
                milestone=early,
                from_date=D(2026, 11, 10),
                to_date=D(2026, 11, 1),
                changed_at=long_ago,
            ),
        ]
    )
    return project, pilot, sample, early


def test_project_drift_totals_and_the_milestone_that_slipped_most():
    project, pilot, sample, early = _plan()
    drift = project_drift(project)
    assert drift["milestones"][pilot.pk]["slipped"] == 20
    assert drift["milestones"][pilot.pk]["moves"] == 2
    assert drift["milestones"][early.pk]["slipped"] == -9  # pulled in
    assert drift["total"] == 20 + 11 - 9 and drift["moved"] == 3
    assert drift["most"]["id"] == pilot.pk and drift["most"]["phase"] == "Collection"
    assert (drift["baseline_end"], drift["current_end"]) == (D(2026, 11, 20), D(2026, 12, 1))
    assert project_drift(ProjectFactory(slug="void")) == {
        "milestones": {},
        "total": 0,
        "moved": 0,
        "most": None,
        "baseline_end": None,
        "current_end": None,
    }
    report = drift_report(project)
    assert [r["title"] for r in report["milestones"]] == ["Pilot", "Sample", "Undated", "Early"]
    assert report["milestones"][0]["history"][0]["from"] == D(2026, 10, 1)


def test_drift_over_the_api(owner):
    project, pilot, sample, early = _plan()
    client = APIClient(HTTP_HOST="127.0.0.1")
    client.credentials(HTTP_X_API_KEY=settings.ATLAS_API_KEY)
    plan = client.get("/api/v1/projects/deep/plan/").json()
    by = {m["title"]: m for m in plan["phases"][0]["milestones"]}
    assert by["Pilot"]["slipped"] == 20 and by["Pilot"]["moves"] == 2
    assert by["Pilot"]["baseline"] == "2026-10-01" and len(by["Pilot"]["history"]) == 2
    assert by["Undated"]["slipped"] is None and by["Undated"]["moves"] == 0
    assert plan["drift"]["total"] == 22 and plan["drift"]["most"]["title"] == "Pilot"
    assert "milestones" not in plan["drift"]
    road = client.get("/api/v1/projects/deep/roadmap/").json()
    rows = {m["title"]: m for m in road["phases"][0]["milestones"]}
    assert rows["Sample"]["baseline"] == "2026-11-20" and rows["Sample"]["slipped"] == 11
    assert "history" not in rows["Sample"]
    report = client.get("/api/v1/projects/deep/plan/drift/").json()
    assert report["total"] == 22 and report["milestones"][0]["title"] == "Pilot"
    assert (
        APIClient(HTTP_HOST="127.0.0.1").get("/api/v1/projects/deep/plan/drift/").status_code == 401
    )
    # a PATCH over the API logs the move like every other save path
    client.patch(f"/api/v1/milestones/{sample.pk}/", {"due_date": "2026-12-05"}, format="json")
    assert client.get("/api/v1/projects/deep/plan/drift/").json()["total"] == 26


def test_plan_drawer_and_roadmap_show_the_drift():
    root = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"
    plan = (root / "Plan.tsx").read_text()
    for needle in ('data-testid="slip-chip"', 'data-testid="plan-drift"', "drift"):
        assert needle in plan, needle
    drawer = (root / "plan" / "MilestoneDrawer.tsx").read_text()
    assert 'data-testid="date-history"' in drawer and "history" in drawer
    road = (root / "plan" / "Roadmap.tsx").read_text()
    assert 'data-testid="ghost-diamond"' in road and "baseline" in road
