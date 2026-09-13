"""Dashboard v2 slice 1 — this week everywhere, per-project health, heatmap in the API."""

import datetime

import pytest
from django.utils import timezone

from core.dashboard import project_health, week_everywhere
from core.models import TodoItem
from plans.tests.factories import MilestoneFactory, PhaseFactory, TaskFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
TODAY = datetime.date(2026, 9, 6)
D = datetime.date


def test_week_everywhere_merges_projects_and_orders():
    a = ProjectFactory(slug="a", name="A", status="active")
    b = ProjectFactory(slug="b", name="B", status="active")
    paused = ProjectFactory(slug="p", status="paused")
    pa, pb, pp = (
        PhaseFactory(project=a, order=1),
        PhaseFactory(project=b, order=1),
        PhaseFactory(project=paused, order=1),
    )
    MilestoneFactory(phase=pa, title="late A", due_date=D(2026, 9, 1))
    soon_b = MilestoneFactory(phase=pb, title="soon B", due_date=D(2026, 9, 9))
    TaskFactory(milestone=soon_b, title="task B", due_date=D(2026, 9, 7))
    MilestoneFactory(phase=pb, title="far B", due_date=D(2026, 10, 1))
    MilestoneFactory(phase=pp, title="paused", due_date=D(2026, 9, 2))
    MilestoneFactory(phase=pa, title="done", due_date=D(2026, 9, 2), completed_at=timezone.now())
    out = week_everywhere(today=TODAY)
    assert [(i["title"], i["project"], i["days"]) for i in out["overdue"]] == [("late A", "a", -5)]
    assert [(i["title"], i["kind"]) for i in out["due_this_week"]] == [
        ("task B", "task"),
        ("soon B", "milestone"),
    ]
    assert out["due_this_week"][0]["color"] == b.color and out["week_ends"] == D(2026, 9, 13)


def test_project_health_and_dashboard_api(client, settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep", status="active")
    phase = PhaseFactory(
        project=project,
        order=1,
        status="in_progress",
        target_start=D(2026, 8, 1),
        target_end=D(2026, 9, 30),
    )
    for i in range(3):
        MilestoneFactory(phase=phase, title=f"m{i}")
    TodoItem.objects.create(text="write intro")
    TodoItem.objects.create(text="done thing", done=True)
    from core.dashboard import active_projects

    health = project_health(active_projects())
    assert health["deep"]["state"] in {"behind", "on_track", "ahead", "upcoming", "overdue"}
    out = client.get("/api/v1/dashboard/", HTTP_X_API_KEY="k").json()
    assert {"week", "todos_open", "heatmap"} <= set(out)
    assert out["todos_open"] == 1 and out["active"][0]["health"]["state"] == health["deep"]["state"]
    assert [t["text"] for t in out["todos"]] == ["write intro"]  # #300: the open ones, in order
    assert len(out["heatmap"]) >= 26 and {"date", "count", "level"} <= set(out["heatmap"][0][0])
    assert out["week"]["overdue"] == [] and isinstance(out["week"]["due_this_week"], list)


def test_reading_queue_everywhere_orders_by_priority_then_age(client_logged_in):
    """#486: to-read links across planning/active projects only, high priority first, then the
    oldest; counts and the API/TSX surfaces."""
    from pathlib import Path

    from core.dashboard import reading_queue_everywhere
    from literature.models import ProjectReference
    from literature.tests.factories import ReferenceFactory

    a = ProjectFactory(name="Alpha", status="active")
    b = ProjectFactory(name="Beta", status="planning")
    paused = ProjectFactory(name="Paused", status="paused")
    old = ProjectReference.objects.create(
        project=a, reference=ReferenceFactory(title="Old normal"), reading_status="to_read"
    )
    ProjectReference.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=30)
    )
    ProjectReference.objects.create(
        project=b,
        reference=ReferenceFactory(title="Urgent"),
        reading_status="to_read",
        priority="high",
    )
    ProjectReference.objects.create(
        project=a,
        reference=ReferenceFactory(title="Fresh low"),
        reading_status="to_read",
        priority="low",
    )
    ProjectReference.objects.create(
        project=a, reference=ReferenceFactory(title="Done"), reading_status="read", priority="high"
    )
    ProjectReference.objects.create(
        project=paused,
        reference=ReferenceFactory(title="Parked"),
        reading_status="to_read",
        priority="high",
    )
    out = reading_queue_everywhere(today=timezone.localdate())
    assert out["to_read"] == 3 and out["high_priority"] == 1 and out["projects"] == 2
    assert [r["title"] for r in out["next"]] == ["Urgent", "Old normal", "Fresh low"]
    assert out["next"][0]["project"] == "Beta" and out["next"][0]["project_slug"] == b.slug
    assert out["next"][1]["waiting_days"] == 30 and out["next"][2]["waiting_days"] == 0
    assert reading_queue_everywhere(limit=1)["next"][0]["title"] == "Urgent"
    body = client_logged_in.get("/api/v1/dashboard/").json()
    assert body["reading"]["to_read"] == 3 and body["reading"]["next"][0]["title"] == "Urgent"
    empty = reading_queue_everywhere()
    assert empty["to_read"] == 3  # same data; the shape holds with nothing too
    tsx = Path("frontend/src/app/pages/Dashboard.tsx").read_text()
    for needle in (
        'data-testid="reading-next"',
        'data-testid="reading-row"',
        "reading.high_priority",
        "/library/${r.id}",
    ):
        assert needle in tsx, needle
