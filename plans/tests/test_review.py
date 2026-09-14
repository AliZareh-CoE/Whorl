"""#517 — the plan review: the queue, the state and the record."""

import datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from plans.dependencies import set_blockers
from plans.models import MilestoneDateChange, PlanReview
from plans.review import finish_review, review_queue, review_state
from plans.tests.factories import MilestoneFactory, PhaseFactory, TaskFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
D = datetime.date
TODAY = D(2026, 10, 10)


def _plan():
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project, name="Collection")
    late = MilestoneFactory(phase=phase, title="Late", due_date=D(2026, 10, 1))
    later = MilestoneFactory(phase=phase, title="Later", due_date=D(2026, 10, 7))
    soon = MilestoneFactory(phase=phase, title="Soon", due_date=D(2026, 10, 20))
    far = MilestoneFactory(phase=phase, title="Far", due_date=D(2026, 10, 15))
    undated = MilestoneFactory(phase=phase, title="Undated", due_date=None)
    MilestoneFactory(phase=phase, title="Done", due_date=D(2026, 9, 1), completed_at=timezone.now())
    set_blockers(soon, [far.pk])  # Soon (Oct 20) waits for Far (Oct 15): 4 d of slack for Far
    set_blockers(later, [soon.pk])  # Later (Oct 7) waits for Soon (Oct 20): a conflict
    TaskFactory(milestone=late, done=True)
    TaskFactory(milestone=late, done=False)
    MilestoneDateChange.objects.create(
        milestone=late,
        from_date=D(2026, 9, 20),
        to_date=D(2026, 10, 1),
        changed_at=timezone.now() - datetime.timedelta(days=20),
    )
    return project, late, later, soon, far, undated


def test_queue_walks_overdue_first_then_by_date_then_undated():
    project, late, later, soon, far, undated = _plan()
    rows = review_queue(project, today=TODAY)
    assert [r["title"] for r in rows] == ["Late", "Later", "Far", "Soon", "Undated"]
    by = {r["title"]: r for r in rows}
    assert by["Late"]["days"] == -9 and by["Late"]["overdue"] is True
    assert by["Late"]["open_tasks"] == 1 and by["Late"]["tasks"] == 2
    assert by["Late"]["slipped"] == 11 and by["Late"]["moves"] == 1
    assert by["Later"]["blocked"] is True and by["Later"]["blocked_by"] == ["Soon"]
    assert by["Later"]["conflict"] is True
    assert by["Far"]["slack"] == 4 and by["Far"]["blocked"] is False
    assert by["Undated"]["days"] is None and by["Undated"]["overdue"] is False


def test_review_state_never_recent_and_due():
    project, *_ = _plan()
    state = review_state(project, today=TODAY)
    assert state["last"] is None and state["days_since"] is None
    assert state["due"] is True and state["open"] == 5 and state["summary"] is None
    PlanReview.objects.create(
        project=project,
        reviewed_at=timezone.now() - datetime.timedelta(days=2),
        kept=3,
        moved=1,
    )
    recent = review_state(project)
    assert recent["days_since"] == 2 and recent["due"] is False
    assert recent["summary"] == {"kept": 3, "completed": 0, "moved": 1, "skipped": 0, "note": ""}
    project.plan_reviews.all().delete()
    PlanReview.objects.create(
        project=project, reviewed_at=timezone.now() - datetime.timedelta(days=8)
    )
    assert review_state(project)["due"] is True  # a week-old sitting no longer counts
    # a plan with nothing open is never due
    empty = ProjectFactory(slug="empty")
    assert review_state(empty)["due"] is False and review_state(empty)["open"] == 0


def test_finish_review_records_the_sitting():
    project, *_ = _plan()
    state = finish_review(project, kept=2, completed=1, moved=1, skipped=1, note="  risky  ")
    assert state["days_since"] == 0 and state["due"] is False
    review = project.plan_reviews.get()
    assert (review.kept, review.completed, review.moved, review.skipped) == (2, 1, 1, 1)
    assert review.note == "risky"


def test_review_over_the_api(owner):
    project, late, later, soon, far, undated = _plan()
    anon = APIClient(HTTP_HOST="127.0.0.1")
    assert anon.get("/api/v1/projects/deep/plan/review/").status_code == 401
    client = APIClient(HTTP_HOST="127.0.0.1")
    client.credentials(HTTP_X_API_KEY=settings.ATLAS_API_KEY)
    out = client.get("/api/v1/projects/deep/plan/review/").json()
    assert out["state"]["due"] is True and out["state"]["last"] is None
    assert [r["title"] for r in out["queue"]][:2] == ["Late", "Later"]
    assert out["queue"][0]["blocked_by"] == [] and out["queue"][1]["blocked_by"] == ["Soon"]
    plan = client.get("/api/v1/projects/deep/plan/").json()
    assert plan["review"]["due"] is True and plan["review"]["open"] == 5
    assert (
        client.post("/api/v1/projects/deep/plan/review/", {"kept": -1}, format="json").status_code
        == 400
    )
    # Audit #30: a count past the column's range is a 400, not a database error
    assert (
        client.post(
            "/api/v1/projects/deep/plan/review/", {"kept": 2**40}, format="json"
        ).status_code
        == 400
    )
    state = client.post(
        "/api/v1/projects/deep/plan/review/", {"kept": 4, "moved": 1, "note": "ok"}, format="json"
    ).json()
    assert state["days_since"] == 0 and state["due"] is False and state["summary"]["kept"] == 4
    assert client.get("/api/v1/projects/deep/plan/").json()["review"]["due"] is False
    assert client.get("/api/v1/projects/nope/plan/review/").status_code == 404


def test_plan_page_carries_the_review():
    root = Path(settings.BASE_DIR) / "frontend" / "src" / "app"
    plan = (root / "pages" / "Plan.tsx").read_text()
    for needle in ('data-testid="review-open"', 'data-testid="review-chip"', "reviewedLabel"):
        assert needle in plan, needle
    review = (root / "pages" / "plan" / "Review.tsx").read_text()
    for needle in (
        'data-testid="review-card"',
        'data-testid="review-finish"',
        'data-testid="review-progress"',
        "/plan/review/",
    ):
        assert needle in review, needle
    assert '"Plan review"' in (root / "shortcuts.tsx").read_text()
