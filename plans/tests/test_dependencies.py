"""#512 — milestone dependencies: rules, flags, payloads, ordering, API, editor wiring."""

from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from plans.dependencies import (
    DependencyError,
    blocked_map,
    is_blocked,
    open_blockers,
    set_blockers,
    unblocked_by,
)
from plans.roadmap import project_roadmap
from plans.selectors import upcoming_milestones
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def _chain():
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project)
    ethics = MilestoneFactory(phase=phase, title="Ethics", due_date="2026-10-01")
    pilot = MilestoneFactory(phase=phase, title="Pilot", due_date="2026-09-20")
    sample = MilestoneFactory(phase=phase, title="Full sample", due_date="2026-09-25")
    set_blockers(pilot, [ethics.pk])
    set_blockers(sample, [ethics.pk, pilot.pk])
    return project, phase, ethics, pilot, sample


def test_set_blockers_refuses_self_foreign_and_loops():
    project, phase, ethics, pilot, sample = _chain()
    with pytest.raises(DependencyError, match="itself"):
        set_blockers(pilot, [pilot.pk])
    other = MilestoneFactory(phase=PhaseFactory(project=ProjectFactory(slug="other")))
    with pytest.raises(DependencyError, match="one project"):
        set_blockers(pilot, [other.pk])
    with pytest.raises(DependencyError, match="loop"):
        set_blockers(ethics, [sample.pk])  # sample ← pilot ← ethics ← sample
    with pytest.raises(DependencyError, match="Unknown"):
        set_blockers(pilot, [999999])
    assert [b.pk for b in set_blockers(pilot, [])] == [] and pilot.blocked_by.count() == 0


def test_blocked_flags_follow_completion():
    project, phase, ethics, pilot, sample = _chain()
    assert is_blocked(pilot) and is_blocked(sample) and not is_blocked(ethics)
    assert [m.pk for m in unblocked_by(ethics)] == [pilot.pk]  # sample still waits on pilot
    assert blocked_map(project) == {
        pilot.pk: [{"id": ethics.pk, "title": "Ethics"}],
        sample.pk: [{"id": ethics.pk, "title": "Ethics"}, {"id": pilot.pk, "title": "Pilot"}],
    }
    ethics.completed_at = timezone.now()
    ethics.save()
    assert not is_blocked(pilot) and [m.pk for m in open_blockers(sample)] == [pilot.pk]
    assert [m.pk for m in unblocked_by(pilot)] == [sample.pk]


def test_upcoming_and_roadmap_sort_blocked_milestones_last():
    project, phase, ethics, pilot, sample = _chain()
    # by due date alone pilot (20th) would come first; it waits on ethics (1 Oct)
    assert [m.title for m in upcoming_milestones(project)] == ["Ethics", "Pilot", "Full sample"]
    rows = project_roadmap(project)["phases"][0]["milestones"]
    assert {r["title"]: r["blocked"] for r in rows} == {
        "Ethics": False,
        "Pilot": True,
        "Full sample": True,
    }


def test_dependencies_over_the_api(owner):
    project, phase, ethics, pilot, sample = _chain()
    client = APIClient(HTTP_HOST="127.0.0.1")
    assert client.get(f"/api/v1/milestones/{pilot.pk}/").status_code == 401
    client.credentials(HTTP_X_API_KEY=settings.ATLAS_API_KEY)
    row = client.get(f"/api/v1/milestones/{pilot.pk}/").json()
    assert row["blocked_by"] == [ethics.pk] and row["blocks"] == [sample.pk] and row["blocked"]
    loop = client.patch(
        f"/api/v1/milestones/{ethics.pk}/", {"blocked_by": [sample.pk]}, format="json"
    )
    assert loop.status_code == 400 and "loop" in loop.json()["blocked_by"][0]
    foreign = MilestoneFactory(phase=PhaseFactory(project=ProjectFactory(slug="far")))
    assert (
        client.patch(
            f"/api/v1/milestones/{pilot.pk}/", {"blocked_by": [foreign.pk]}, format="json"
        ).status_code
        == 400
    )
    ok = client.patch(f"/api/v1/milestones/{pilot.pk}/", {"blocked_by": []}, format="json")
    assert ok.status_code == 200 and ok.json()["blocked"] is False
    plan = client.get("/api/v1/projects/deep/plan/").json()
    by_title = {m["title"]: m for m in plan["phases"][0]["milestones"]}
    assert by_title["Full sample"]["blocked"] and by_title["Full sample"]["blocked_by"] == [
        {"id": ethics.pk, "title": "Ethics"},
        {"id": pilot.pk, "title": "Pilot"},
    ]
    assert by_title["Ethics"]["blocks"] == [sample.pk] and by_title["Pilot"]["blocked"] is False
    # completing a blocker over the API frees the dependant
    client.patch(
        f"/api/v1/milestones/{ethics.pk}/",
        {"completed_at": timezone.now().isoformat()},
        format="json",
    )
    client.patch(
        f"/api/v1/milestones/{pilot.pk}/",
        {"completed_at": timezone.now().isoformat()},
        format="json",
    )
    assert client.get(f"/api/v1/milestones/{sample.pk}/").json()["blocked"] is False


def test_plan_page_shows_locks_and_the_drawer_edits_dependencies():
    root = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"
    plan = (root / "Plan.tsx").read_text()
    for needle in ('data-testid="blocked-chip"', "Unblocked:", "options={"):
        assert needle in plan, needle
    drawer = (root / "plan" / "MilestoneDrawer.tsx").read_text()
    for needle in (
        'data-testid="blocked-by"',
        'data-testid="blocked-by-add"',
        'data-testid="blocker-chip"',
        "blocked_by: ids",
    ):
        assert needle in drawer, needle
