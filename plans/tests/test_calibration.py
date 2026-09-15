"""#519 — calibration: how milestones land against their dates, and the likely dates."""

import datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from plans.calibration import (
    MIN_SAMPLE,
    bucket_of,
    calibration,
    landing_rows,
    likely_date,
    phase_likely_end,
)
from plans.models import MilestoneDateChange
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
D = datetime.date


def _at(day: datetime.date):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(15, 0)))


def _plan():
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project, name="Collection", target_end=D(2026, 11, 20))
    early = MilestoneFactory(
        phase=phase, title="Early", due_date=D(2026, 9, 10), completed_at=_at(D(2026, 9, 8))
    )
    on_day = MilestoneFactory(
        phase=phase, title="On the day", due_date=D(2026, 9, 20), completed_at=_at(D(2026, 9, 20))
    )
    week = MilestoneFactory(
        phase=phase, title="Week", due_date=D(2026, 10, 1), completed_at=_at(D(2026, 10, 6))
    )
    month = MilestoneFactory(
        phase=phase, title="Month", due_date=D(2026, 10, 10), completed_at=_at(D(2026, 10, 30))
    )
    MilestoneFactory(
        phase=phase, title="Undated done", due_date=None, completed_at=_at(D(2026, 10, 2))
    )
    open_near = MilestoneFactory(phase=phase, title="Open near", due_date=D(2026, 11, 10))
    open_far = MilestoneFactory(phase=phase, title="Open far", due_date=D(2026, 11, 18))
    MilestoneFactory(phase=phase, title="Open undated", due_date=None)
    # the month-late one had first been planned a month earlier still
    MilestoneDateChange.objects.create(
        milestone=month,
        from_date=D(2026, 9, 10),
        to_date=D(2026, 10, 10),
        changed_at=timezone.now() - datetime.timedelta(days=40),
    )
    return project, phase, early, on_day, week, month, open_near, open_far


def test_landing_rows_measure_each_completed_dated_milestone():
    project, phase, early, on_day, week, month, *_ = _plan()
    rows = landing_rows(project)
    assert [r["title"] for r in rows] == ["Month", "Week", "On the day", "Early"]
    by = {r["title"]: r for r in rows}
    assert by["Early"]["late"] == -2 and by["Early"]["landed"] == D(2026, 9, 8)
    assert by["On the day"]["late"] == 0
    assert by["Week"]["late"] == 5 and by["Week"]["late_first"] == 5
    assert by["Month"]["late"] == 20 and by["Month"]["late_first"] == 50
    assert by["Month"]["baseline"] == D(2026, 9, 10) and by["Month"]["phase"] == "Collection"


def test_calibration_totals_and_shift():
    project, *_ = _plan()
    cal = calibration(project)
    assert cal["count"] == 4 and cal["on_time"] == 2
    assert cal["median_late"] == 3  # (0 + 5) / 2 rounded up
    assert cal["p80_late"] == 20 and cal["median_late_first"] == 3
    assert cal["buckets"] == {"early": 1, "on_the_day": 1, "week": 1, "month": 1, "longer": 0}
    assert cal["worst"] == {"id": cal["worst"]["id"], "title": "Month", "late": 20}
    assert cal["shift"] == 3
    assert [bucket_of(n) for n in (-1, 0, 7, 8, 30, 31)] == [
        "early",
        "on_the_day",
        "week",
        "month",
        "month",
        "longer",
    ]


def test_too_few_landings_give_no_shift_and_no_worst_when_all_on_time():
    project = ProjectFactory(slug="young")
    phase = PhaseFactory(project=project)
    for day in range(MIN_SAMPLE - 1):
        MilestoneFactory(
            phase=phase,
            due_date=D(2026, 9, 10 + day),
            completed_at=_at(D(2026, 9, 9 + day)),
        )
    cal = calibration(project)
    assert cal["count"] == MIN_SAMPLE - 1 and cal["shift"] is None
    assert cal["worst"] is None and cal["median_late"] == -1
    assert likely_date(D(2026, 10, 1), cal) is None
    empty = calibration(ProjectFactory(slug="void"))
    assert empty["count"] == 0 and empty["median_late"] is None and empty["p80_late"] is None
    assert empty["shift"] is None and empty["on_time"] == 0


def test_likely_dates_follow_the_shift():
    project, phase, *_rest = _plan()
    cal = calibration(project)
    today = D(2026, 10, 10)
    assert likely_date(D(2026, 11, 10), cal, today) == D(2026, 11, 13)
    assert likely_date(None, cal, today) is None
    # a likely date already behind us is no prediction — a 30-day-overdue milestone says nothing
    assert likely_date(D(2026, 9, 10), cal, today) is None
    assert likely_date(D(2026, 10, 8), cal, today) == D(2026, 10, 11)  # still ahead once shifted
    assert phase_likely_end(list(phase.milestones.all()), cal, today) == D(2026, 11, 21)
    assert phase_likely_end([], cal, today) is None
    assert likely_date(D(2026, 11, 10), cal) == D(2026, 11, 13)  # today defaults to the clock


def test_calibration_over_the_api(owner):
    project, phase, early, on_day, week, month, open_near, open_far = _plan()
    anon = APIClient(HTTP_HOST="127.0.0.1")
    assert anon.get("/api/v1/projects/deep/plan/calibration/").status_code == 401
    client = APIClient(HTTP_HOST="127.0.0.1")
    client.credentials(HTTP_X_API_KEY=settings.ATLAS_API_KEY)
    report = client.get("/api/v1/projects/deep/plan/calibration/").json()
    assert report["count"] == 4 and report["shift"] == 3 and report["min_sample"] == MIN_SAMPLE
    assert report["landings"][0]["title"] == "Month" and report["landings"][0]["late"] == 20
    assert report["landings"][0]["landed"] == "2026-10-30"
    plan = client.get("/api/v1/projects/deep/plan/").json()
    assert plan["calibration"]["count"] == 4 and plan["calibration"]["shift"] == 3
    rows = {m["title"]: m for m in plan["phases"][0]["milestones"]}
    assert (
        rows["Open near"]["likely"] == "2026-11-13" and rows["Open far"]["likely"] == "2026-11-21"
    )
    assert rows["Open undated"]["likely"] is None and rows["Month"]["likely"] is None
    MilestoneFactory(phase=phase, title="Long overdue", due_date=D(2026, 1, 5))
    plan = client.get("/api/v1/projects/deep/plan/").json()
    assert {m["title"]: m for m in plan["phases"][0]["milestones"]}["Long overdue"][
        "likely"
    ] is None
    assert plan["phases"][0]["likely_end"] == "2026-11-21"
    assert plan["phases"][0]["target_end"] == "2026-11-20"
    assert client.get("/api/v1/projects/nope/plan/calibration/").status_code == 404
    # #520: the roadmap and the review queue carry the same likely dates
    road = client.get("/api/v1/projects/deep/roadmap/").json()
    rows = {m["title"]: m for m in road["phases"][0]["milestones"]}
    assert rows["Open near"]["likely"] == "2026-11-13" and rows["Month"]["likely"] is None
    assert road["phases"][0]["likely_end"] == "2026-11-21"
    assert road["range_end"] >= "2026-11-21"
    queue = client.get("/api/v1/projects/deep/plan/review/").json()["queue"]
    by = {r["title"]: r for r in queue}
    assert by["Open far"]["likely"] == "2026-11-21" and by["Open undated"]["likely"] is None


def test_plan_page_shows_the_calibration():
    root = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"
    plan = (root / "Plan.tsx").read_text()
    for needle in (
        'data-testid="plan-calibration"',
        'data-testid="likely-chip"',
        'data-testid="likely-end"',
        "calibration",
    ):
        assert needle in plan, needle
    drawer = (root / "plan" / "MilestoneDrawer.tsx").read_text()
    assert 'data-testid="likely-line"' in drawer and "likely" in drawer
    road = (root / "plan" / "Roadmap.tsx").read_text()  # #520
    assert 'data-testid="likely-mark"' in road and "likely_end" in road
    assert '"likely"' in (root / "plan" / "Review.tsx").read_text()
