"""Plan v2 slice 3 — this week's focus."""

import datetime

import pytest
from django.utils import timezone

from plans import focus
from projects.tests.factories import ProjectFactory

from .factories import MilestoneFactory, PhaseFactory, TaskFactory

pytestmark = pytest.mark.django_db
TODAY = datetime.date(2026, 9, 6)
D = datetime.date


def test_week_focus_buckets_and_order():
    project = ProjectFactory(slug="deep")
    done_phase = PhaseFactory(project=project, order=1, status="done")
    MilestoneFactory(
        phase=done_phase, title="old", due_date=D(2026, 1, 1), completed_at=timezone.now()
    )
    phase = PhaseFactory(project=project, order=2, status="in_progress")
    late = MilestoneFactory(phase=phase, title="late milestone", due_date=D(2026, 9, 1))
    soon = MilestoneFactory(phase=phase, title="due friday", due_date=D(2026, 9, 11))
    MilestoneFactory(phase=phase, title="far away", due_date=D(2026, 10, 30))
    undated = MilestoneFactory(phase=phase, title="undated next")
    late_task = TaskFactory(milestone=soon, title="late task", due_date=D(2026, 9, 4))
    TaskFactory(milestone=soon, title="done task", due_date=D(2026, 9, 4), done=True)
    soon_task = TaskFactory(milestone=soon, title="task this week", due_date=D(2026, 9, 6))
    out = focus.week_focus(project, today=TODAY)
    assert out["week_ends"] == D(2026, 9, 13)
    assert [(i["kind"], i["id"], i["days"]) for i in out["overdue"]] == [
        ("milestone", late.pk, -5),
        ("task", late_task.pk, -2),
    ]
    assert [(i["kind"], i["id"]) for i in out["due_this_week"]] == [
        ("task", soon_task.pk),
        ("milestone", soon.pk),
    ]
    assert (
        out["due_this_week"][0]["milestone"] == "due friday"
        and out["due_this_week"][0]["phase"] == phase.name
    )
    assert [i["id"] for i in out["next_up"]] == [undated.pk] or [
        i["title"] for i in out["next_up"]
    ] == ["far away", "undated next"]
    assert out["current_phase"]["id"] == phase.pk


def test_next_up_caps_at_three_and_skips_listed():
    project = ProjectFactory()
    phase = PhaseFactory(project=project, order=1, status="in_progress")
    MilestoneFactory(phase=phase, title="this week", due_date=D(2026, 9, 8))
    for i in range(5):
        MilestoneFactory(phase=phase, title=f"later {i}")
    out = focus.week_focus(project, today=TODAY)
    assert len(out["next_up"]) == 3 and all(i["title"].startswith("later") for i in out["next_up"])


def test_empty_project():
    project = ProjectFactory()
    out = focus.week_focus(project, today=TODAY)
    assert out["overdue"] == [] and out["due_this_week"] == [] and out["next_up"] == []
    assert out["current_phase"] is None


def test_focus_api(client, settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project, order=1, status="in_progress")
    MilestoneFactory(phase=phase, title="late", due_date=D(2000, 1, 1))
    out = client.get("/api/v1/projects/deep/focus/", HTTP_X_API_KEY="k")
    assert out.status_code == 200 and out.json()["overdue"][0]["title"] == "late"
    overview = client.get("/api/v1/projects/deep/overview/", HTTP_X_API_KEY="k").json()
    assert overview["focus"]["overdue"][0]["title"] == "late"
    assert overview["health"]["state"] in {
        "overdue",
        "behind",
        "on_track",
        "ahead",
        "upcoming",
        "empty",
    }
