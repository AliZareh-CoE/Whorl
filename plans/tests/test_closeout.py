"""#521 — phase close-out: the report card and the closing decision."""

import datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from plans.closeout import close_phase, phase_report
from plans.models import MilestoneDateChange, Phase, ResearchQuestion
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
D = datetime.date
TODAY = D(2026, 10, 10)


def _at(day):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(15, 0)))


def _phase(all_done=True):
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(
        project=project,
        name="Pilot",
        objective="Freeze the design.",
        target_start=D(2026, 8, 1),
        target_end=D(2026, 9, 20),
        status=Phase.Status.IN_PROGRESS,
    )
    early = MilestoneFactory(
        phase=phase, title="Early", due_date=D(2026, 9, 1), completed_at=_at(D(2026, 8, 30))
    )
    late = MilestoneFactory(
        phase=phase, title="Late", due_date=D(2026, 9, 18), completed_at=_at(D(2026, 9, 27))
    )
    MilestoneDateChange.objects.create(
        milestone=late,
        from_date=D(2026, 9, 10),
        to_date=D(2026, 9, 18),
        changed_at=timezone.now() - datetime.timedelta(days=30),
    )
    if not all_done:
        MilestoneFactory(phase=phase, title="Open", due_date=D(2026, 10, 1))
    q = ResearchQuestion.objects.create(project=project, question="Does load matter?")
    q.phases.add(phase)
    return project, phase, early, late


def test_report_measures_the_phase():
    project, phase, early, late = _phase()
    report = phase_report(phase, today=TODAY)
    assert (report["planned_end"], report["actual_end"], report["overrun"]) == (
        D(2026, 9, 20),
        D(2026, 9, 27),
        7,
    )
    assert report["counts"] == {"total": 2, "done": 2, "open": 0, "on_time": 1}
    assert report["median_late"] == 4 and report["drift"] == 8 and report["moves"] == 1
    rows = {r["title"]: r for r in report["milestones"]}
    assert rows["Early"]["late"] == -2 and rows["Early"]["bucket"] == "early"
    assert rows["Late"]["late"] == 9 and rows["Late"]["late_first"] == 17
    assert rows["Late"]["baseline"] == D(2026, 9, 10) and rows["Late"]["moves"] == 1
    assert report["questions"][0]["question"] == "Does load matter?"
    assert report["closable"] is True
    md = report["markdown"]
    assert "## Phase report — Pilot" in md and "| Late | 2026-09-10 | 2026-09-18 |" in md
    assert "2/2 done, 1 on time" in md and "overrun: 7 d late" in md and "> Freeze" in md


def test_open_milestones_and_done_phases_are_not_closable():
    project, phase, *_ = _phase(all_done=False)
    report = phase_report(phase, today=TODAY)
    assert report["closable"] is False and report["counts"]["open"] == 1
    rows = {r["title"]: r for r in report["milestones"]}
    assert rows["Open"]["landed"] is None and rows["Open"]["late"] is None
    assert "| Open | 2026-10-01 | 2026-10-01 | open | — |" in report["markdown"]
    phase.milestones.filter(title="Open").delete()
    phase.status = Phase.Status.DONE
    phase.save()
    assert phase_report(phase, today=TODAY)["closable"] is False
    empty = PhaseFactory(project=project, name="Empty")
    blank = phase_report(empty, today=TODAY)
    assert blank["closable"] is False and blank["planned_end"] is None
    assert blank["overrun"] is None and blank["median_late"] is None


def test_close_phase_files_a_decision():
    project, phase, *_ = _phase()
    out = close_phase(phase, lessons="  Recruit two weeks earlier.  ", today=TODAY)
    phase.refresh_from_db()
    assert phase.status == Phase.Status.DONE
    assert out["report"]["status"] == "done" and out["report"]["closable"] is False
    decision = project.decisions.get(pk=out["decision_id"])
    assert decision.title == "Phase closed: Pilot" and decision.decided_on == TODAY
    assert decision.decision == "Recruit two weeks earlier."
    assert "## Phase report — Pilot" in decision.context
    # no lessons: the decision says what the numbers say
    other = PhaseFactory(project=project, name="Quick", target_end=D(2026, 9, 1))
    MilestoneFactory(phase=other, due_date=D(2026, 8, 30), completed_at=_at(D(2026, 8, 25)))
    out = close_phase(other, today=TODAY)
    assert project.decisions.get(pk=out["decision_id"]).decision == (
        "Closed with 1/1 milestones done, 7 d under."
    )


def test_close_out_over_the_api(owner):
    project, phase, *_ = _phase()
    anon = APIClient(HTTP_HOST="127.0.0.1")
    assert anon.get(f"/api/v1/phases/{phase.pk}/report/").status_code == 401
    client = APIClient(HTTP_HOST="127.0.0.1")
    client.credentials(HTTP_X_API_KEY=settings.ATLAS_API_KEY)
    report = client.get(f"/api/v1/phases/{phase.pk}/report/").json()
    assert report["overrun"] == 7 and report["closable"] is True
    assert report["milestones"][1]["landed"] == "2026-09-27"
    plan = client.get("/api/v1/projects/deep/plan/").json()
    assert plan["phases"][0]["closable"] is True
    assert client.get("/api/v1/phases/999999/report/").status_code == 404
    assert (
        client.post(
            f"/api/v1/phases/{phase.pk}/close/", {"lessons": "x" * 5000}, format="json"
        ).status_code
        == 400
    )
    out = client.post(
        f"/api/v1/phases/{phase.pk}/close/", {"lessons": "Start recruiting earlier."}, format="json"
    ).json()
    assert out["report"]["status"] == "done" and out["decision_id"]
    assert client.get("/api/v1/projects/deep/plan/").json()["phases"][0]["closable"] is False
    decision = client.get(f"/api/v1/decisions/{out['decision_id']}/").json()
    assert decision["title"] == "Phase closed: Pilot"
    # closing again would file a second decision: refused
    again = client.post(f"/api/v1/phases/{phase.pk}/close/", {"lessons": "x"}, format="json")
    assert again.status_code == 400 and project.decisions.count() == 1


def test_plan_page_carries_the_close_out():
    root = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"
    plan = (root / "Plan.tsx").read_text()
    for needle in ('data-testid="close-nudge"', "Phase report", "PhaseReport"):
        assert needle in plan, needle
    panel = (root / "plan" / "PhaseReport.tsx").read_text()
    for needle in (
        'data-testid="phase-report"',
        'data-testid="phase-close"',
        'data-testid="report-lessons"',
        "/report/",
        "/close/",
    ):
        assert needle in panel, needle
