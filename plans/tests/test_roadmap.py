"""Plan v2 slice 2 — roadmap data: windows, health, forecast."""

import datetime

import pytest
from django.utils import timezone

from plans import roadmap
from projects.tests.factories import ProjectFactory

from .factories import MilestoneFactory, PhaseFactory

pytestmark = pytest.mark.django_db
TODAY = datetime.date(2026, 9, 6)
D = datetime.date


def _done(phase, title, when, **kw):
    return MilestoneFactory(
        phase=phase,
        title=title,
        completed_at=timezone.make_aware(datetime.datetime.combine(when, datetime.time(12))),
        **kw,
    )


def test_windows_are_inferred_from_milestones_and_neighbours():
    project = ProjectFactory()
    p1 = PhaseFactory(
        project=project, order=1, target_start=D(2026, 8, 1), target_end=D(2026, 8, 31)
    )
    p2 = PhaseFactory(project=project, order=2)  # no dates, no milestones → after p1, 6 weeks
    p3 = PhaseFactory(project=project, order=3)
    MilestoneFactory(phase=p3, due_date=D(2026, 12, 1))
    MilestoneFactory(phase=p3, due_date=D(2026, 11, 1))
    rows = roadmap.project_roadmap(project, today=TODAY)["phases"]
    assert (rows[0]["start"], rows[0]["end"], rows[0]["inferred"]) == (
        D(2026, 8, 1),
        D(2026, 8, 31),
        False,
    )
    assert (rows[1]["start"], rows[1]["end"], rows[1]["inferred"]) == (
        D(2026, 9, 1),
        D(2026, 10, 13),
        True,
    )
    assert (rows[2]["start"], rows[2]["end"]) == (D(2026, 10, 14), D(2026, 12, 1))
    assert p1.pk == rows[0]["id"] and p2.pk == rows[1]["id"]


def test_health_states():
    project = ProjectFactory()
    behind = PhaseFactory(
        project=project,
        order=1,
        status="in_progress",
        target_start=D(2026, 8, 1),
        target_end=D(2026, 9, 30),
    )
    for i in range(4):
        MilestoneFactory(phase=behind, title=f"m{i}")
    ahead = PhaseFactory(
        project=project,
        order=2,
        status="in_progress",
        target_start=D(2026, 8, 1),
        target_end=D(2026, 12, 31),
    )
    _done(ahead, "a", D(2026, 8, 10))
    _done(ahead, "b", D(2026, 8, 20))
    MilestoneFactory(phase=ahead, title="c")
    upcoming = PhaseFactory(
        project=project, order=3, target_start=D(2026, 10, 1), target_end=D(2026, 10, 31)
    )
    MilestoneFactory(phase=upcoming)
    late = PhaseFactory(
        project=project,
        order=4,
        status="in_progress",
        target_start=D(2026, 6, 1),
        target_end=D(2026, 7, 1),
    )
    MilestoneFactory(phase=late)
    done = PhaseFactory(
        project=project,
        order=5,
        status="done",
        target_start=D(2026, 1, 1),
        target_end=D(2026, 2, 1),
    )
    empty = PhaseFactory(
        project=project, order=6, target_start=D(2026, 9, 1), target_end=D(2026, 9, 30)
    )
    blocked = PhaseFactory(
        project=project,
        order=7,
        status="blocked",
        target_start=D(2026, 9, 1),
        target_end=D(2026, 9, 30),
    )
    MilestoneFactory(phase=blocked)
    rows = {r["id"]: r for r in roadmap.project_roadmap(project, today=TODAY)["phases"]}
    assert rows[behind.pk]["state"] == "behind" and "0/4 done" in rows[behind.pk]["label"]
    assert rows[ahead.pk]["state"] == "ahead"
    # pace: 10 days per milestone, 1 remaining → forecast 10 days out
    assert rows[ahead.pk]["forecast_end"] == D(2026, 9, 16)
    assert (
        rows[upcoming.pk]["state"] == "upcoming" and rows[upcoming.pk]["label"] == "starts in 25 d"
    )
    assert rows[late.pk]["state"] == "overdue"
    assert rows[done.pk]["state"] == "done" and rows[empty.pk]["state"] == "empty"
    assert rows[blocked.pk]["state"] == "blocked"


def test_range_and_milestone_rows():
    project = ProjectFactory()
    phase = PhaseFactory(
        project=project, order=1, target_start=D(2026, 9, 1), target_end=D(2026, 9, 30)
    )
    MilestoneFactory(phase=phase, title="late one", due_date=D(2026, 9, 1))
    out = roadmap.project_roadmap(project, today=TODAY)
    assert out["range_start"] == D(2026, 9, 1) and out["range_end"] == D(2026, 9, 30)
    m = out["phases"][0]["milestones"][0]
    assert m["title"] == "late one" and m["overdue"] is True and m["done"] is False


def test_empty_project():
    project = ProjectFactory()
    out = roadmap.project_roadmap(project, today=TODAY)
    assert out["phases"] == [] and out["range_end"] == TODAY + datetime.timedelta(weeks=12)


def test_roadmap_api(client, settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(
        project=project, order=1, target_start=D(2026, 9, 1), target_end=D(2026, 9, 30)
    )
    out = client.get("/api/v1/projects/deep/roadmap/", HTTP_X_API_KEY="k")
    assert out.status_code == 200 and out.json()["phases"][0]["id"] == phase.pk
    assert out.json()["phases"][0]["start"] == "2026-09-01"
