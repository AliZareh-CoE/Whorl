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


def test_writing_everywhere_sorts_live_manuscripts_by_urgency(client_logged_in):
    """#487: live papers across planning/active projects — nearest deadline first, then a
    paper whose editor deserves a nudge, then the rest; shelved/published and paused projects
    stay out; clock/readiness ride along; API + TSX surfaces."""
    from pathlib import Path

    from core.dashboard import writing_everywhere
    from writing.models import Manuscript, SubmissionEvent

    today = timezone.localdate()
    a = ProjectFactory(name="Alpha", status="active")
    b = ProjectFactory(name="Beta", status="planning")
    paused = ProjectFactory(name="Paused", status="paused")
    soon = Manuscript.objects.create(
        project=b, title="Due soon", status="drafting", deadline=today + datetime.timedelta(days=5)
    )
    waiting = Manuscript.objects.create(
        project=a, title="Waiting", status="under_review", target_venue="Slow J"
    )
    SubmissionEvent.objects.create(
        manuscript=waiting, kind="submitted", date=today - datetime.timedelta(days=200)
    )
    idea = Manuscript.objects.create(project=a, title="Idea", status="idea")
    Manuscript.objects.create(project=a, title="Shelved", status="shelved")
    Manuscript.objects.create(project=paused, title="Parked", status="drafting")
    out = writing_everywhere(today=today)
    assert out["live"] == 3
    assert [r["title"] for r in out["rows"]] == ["Due soon", "Waiting", "Idea"]
    assert out["rows"][0]["project"] == "Beta" and out["rows"][0]["days"] == 5
    assert out["rows"][0]["readiness"] is not None  # drafting → pre-flight shown
    assert out["rows"][1]["clock"]["nudge"]["due"] is True and out["rows"][1]["readiness"] is None
    assert idea.pk == out["rows"][2]["id"] and out["rows"][2]["project_slug"] == a.slug
    assert len(writing_everywhere(today=today, limit=1)["rows"]) == 1
    body = client_logged_in.get("/api/v1/dashboard/").json()
    assert body["writing"]["live"] == 3 and body["writing"]["rows"][0]["title"] == "Due soon"
    assert soon.pk == body["writing"]["rows"][0]["id"]
    tsx = Path("frontend/src/app/pages/Dashboard.tsx").read_text()
    for needle in (
        'data-testid="writing-everywhere"',
        'data-testid="writing-row"',
        "/manuscripts/${m.id}",
        "m.clock.nudge?.due",
        "m.readiness",
    ):
        assert needle in tsx, needle


def test_pulses_everywhere_bins_per_project_and_flags_quiet_ones(client_logged_in):
    """#489: grouped queries bin every project's events into twelve Monday-based weeks; a
    project flat for three weeks is a needs-attention row."""
    from pathlib import Path

    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from core.dashboard import active_projects, pulses_everywhere, quiet_projects
    from projects.models import DecisionRecord

    today = D(2026, 9, 13)  # Sunday; this week starts 09-07, the window 06-22
    busy = ProjectFactory(name="Busy", status="active")
    drifting = ProjectFactory(name="Drifting", status="active")
    ProjectFactory(name="Paused", status="paused")
    phase = PhaseFactory(project=busy, order=1)
    for delta in (0, 1, 20):
        m = MilestoneFactory(phase=phase, title=f"m{delta}")
        m.completed_at = timezone.make_aware(
            datetime.datetime.combine(today - datetime.timedelta(days=delta), datetime.time(12))
        )
        m.save()
    DecisionRecord.objects.create(
        project=drifting, title="Old", decision="x", decided_on=today - datetime.timedelta(days=30)
    )
    DecisionRecord.objects.create(
        project=busy, title="Ancient", decision="x", decided_on=D(2026, 1, 1)
    )  # outside the window: counted nowhere, but not the last activity either
    rows = active_projects()
    with CaptureQueriesContext(connection) as ctx:
        pulses = pulses_everywhere([r["project"] for r in rows], today=today)
    assert len(ctx.captured_queries) <= 9  # grouped, not per project
    b, d = pulses[busy.pk], pulses[drifting.pk]
    assert len(b["weeks"]) == 12 and b["weeks"][-1] == 2 and b["weeks"][-3] == 1 and b["total"] == 3
    assert b["quiet_weeks"] == 0 and b["last_activity"] == "2026-09-13" and b["days_since"] == 0
    assert d["total"] == 1 and d["quiet_weeks"] == 4 and d["last_activity"] == "2026-08-14"
    quiet = quiet_projects(rows, pulses)
    assert [q["slug"] for q in quiet] == [drifting.slug] and quiet[0]["quiet_weeks"] == 4
    assert quiet[0]["url"] == f"/projects/{drifting.slug}"
    assert pulses_everywhere([], today=today) == {}
    body = client_logged_in.get("/api/v1/dashboard/").json()
    by_slug = {p["slug"]: p for p in body["active"]}
    assert len(by_slug[busy.slug]["pulse"]["weeks"]) == 12
    assert [q["slug"] for q in body["attention"]["quiet"]] == [drifting.slug]
    tsx = Path("frontend/src/app/pages/Dashboard.tsx").read_text()
    for needle in (
        'data-testid="project-pulse"',
        'data-testid="attention-quiet"',
        "pulse.quiet_weeks >= 3",
        "attention.quiet",
    ):
        assert needle in tsx, needle


def test_stats_trend_bins_six_months_with_the_current_month_last(client_logged_in):
    """#490: one series per stat over six months, same definitions as the tiles, last month
    as `previous`; API + TSX surfaces."""
    from pathlib import Path

    from core.dashboard import monthly_stats, stats_trend
    from notes.models import Note
    from writing.models import Manuscript, WordCountSample

    today = D(2026, 9, 13)
    project = ProjectFactory()
    phase = PhaseFactory(project=project, order=1)
    for day in (D(2026, 9, 2), D(2026, 8, 20), D(2026, 8, 3), D(2026, 4, 1), D(2026, 3, 31)):
        m = MilestoneFactory(phase=phase, title=f"m{day}")
        m.completed_at = timezone.make_aware(datetime.datetime.combine(day, datetime.time(12)))
        m.save()
    n = Note.objects.create(project=project, title="Now")
    Note.objects.filter(pk=n.pk).update(
        created_at=timezone.make_aware(datetime.datetime(2026, 7, 4, 9, 0))
    )
    paper = Manuscript.objects.create(project=project, title="P", status="drafting")
    for day, words in (
        (D(2026, 7, 1), 100),
        (D(2026, 8, 1), 400),
        (D(2026, 8, 15), 300),
        (D(2026, 9, 1), 350),
    ):
        WordCountSample.objects.create(manuscript=paper, date=day, words=words)
    out = stats_trend(today=today)
    assert out["months"] == ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    assert out["series"]["milestones_done"] == [1, 0, 0, 0, 2, 1]  # March is outside
    assert out["series"]["notes_written"] == [0, 0, 0, 1, 0, 0]
    assert out["series"]["words_written"] == [0, 0, 0, 0, 300, 50]  # only positive deltas
    assert out["previous"]["milestones_done"] == 2 and out["previous"]["words_written"] == 300
    assert out["series"]["milestones_done"][-1] == monthly_stats(today=today)["milestones_done"]
    body = client_logged_in.get("/api/v1/dashboard/").json()
    assert len(body["trends"]["months"]) == 6 and "papers_read" in body["trends"]["series"]
    tsx = Path("frontend/src/app/pages/Dashboard.tsx").read_text()
    for needle in (
        'data-testid="stat-trend"',
        'data-testid="stat-delta"',
        "trends?.series",
        "trends?.previous",
    ):
        assert needle in tsx, needle


def test_day_activity_lists_one_day_across_projects(client_logged_in):
    """#492: the readable events of one day, every project, with links; the API validates
    the date; the heatmap cells are buttons that open the day panel."""
    from pathlib import Path

    from core.dashboard import day_activity
    from notes.models import Note
    from projects.models import DecisionRecord

    day = D(2026, 9, 8)
    a = ProjectFactory(name="Alpha")
    b = ProjectFactory(name="Beta")
    phase = PhaseFactory(project=a, order=1)
    m = MilestoneFactory(phase=phase, title="Pilot done")
    m.completed_at = timezone.make_aware(datetime.datetime.combine(day, datetime.time(10)))
    m.save()
    DecisionRecord.objects.create(project=b, title="Go dual-task", decision="yes", decided_on=day)
    DecisionRecord.objects.create(
        project=b, title="Other day", decision="no", decided_on=day - datetime.timedelta(days=1)
    )
    n = Note.objects.create(project=a, title="Same-day note")
    Note.objects.filter(pk=n.pk).update(
        created_at=timezone.make_aware(datetime.datetime.combine(day, datetime.time(15)))
    )
    out = day_activity(day)
    assert out["date"] == "2026-09-08" and out["count"] == 3
    labels = {(e["kind"], e["label"], e["project"]) for e in out["events"]}
    assert labels == {
        ("milestone", "Pilot done", "Alpha"),
        ("note", "Same-day note", "Alpha"),
        ("decision", "Go dual-task", "Beta"),
    }
    assert all(e["url"] and e["project_slug"] for e in out["events"])
    assert day_activity(D(2020, 1, 1))["count"] == 0
    r = client_logged_in.get("/api/v1/dashboard/day/?date=2026-09-08")
    assert r.status_code == 200 and r.json()["count"] == 3
    assert client_logged_in.get("/api/v1/dashboard/day/?date=nope").status_code == 400
    assert client_logged_in.get("/api/v1/dashboard/day/").status_code == 200
    tsx = Path("frontend/src/app/pages/Dashboard.tsx").read_text()
    for needle in (
        'data-testid="heatmap-day"',
        'data-testid="day-panel"',
        "/dashboard/day/?date=",
        "setSelectedDay",
    ):
        assert needle in tsx, needle
