"""Plan v2 slice 1 — the plan as a Markdown outline (round-trip, preview, apply)."""

import datetime

import pytest
from django.utils import timezone

from plans import outline
from plans.models import Milestone, Phase, Task
from projects.tests.factories import ProjectFactory

from .factories import MilestoneFactory, PhaseFactory, TaskFactory

pytestmark = pytest.mark.django_db

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture
def plan():
    project = ProjectFactory(slug="deep")
    p1 = PhaseFactory(
        project=project,
        name="Literature review",
        order=1,
        status="in_progress",
        objective="Map the debate.\nPick a paradigm.",
        target_start=datetime.date(2026, 9, 1),
        target_end=datetime.date(2026, 10, 15),
    )
    m1 = MilestoneFactory(
        phase=p1, title="Annotated bibliography", due_date=datetime.date(2026, 9, 20)
    )
    MilestoneFactory(phase=p1, title="Paradigm chosen", completed_at=timezone.now())
    TaskFactory(milestone=m1, title="Pull citing papers", done=True)
    TaskFactory(milestone=m1, title="Rate on the matrix", due_date=datetime.date(2026, 9, 10))
    PhaseFactory(project=project, name="Pilot", order=2)
    return project


def test_export_shape(plan):
    md = outline.plan_to_markdown(plan)
    p1, m1, t1 = (
        Phase.objects.get(name="Literature review"),
        Milestone.objects.get(title="Annotated bibliography"),
        Task.objects.get(title="Pull citing papers"),
    )
    assert (
        md.splitlines()[0]
        == f"# Literature review  [in_progress]  (2026-09-01 → 2026-10-15)  {{#{p1.pk}}}"
    )
    assert "> Map the debate.\n> Pick a paradigm." in md
    assert f"- [ ] Annotated bibliography  (due 2026-09-20)  {{#{m1.pk}}}" in md
    assert f"  - [x] Pull citing papers  {{#{t1.pk}}}" in md
    assert "  - [ ] Rate on the matrix  (due 2026-09-10)" in md
    assert "- [x] Paradigm chosen" in md and "\n# Pilot  [not_started]  {#" in md


def test_round_trip_is_a_no_op(plan):
    md = outline.plan_to_markdown(plan)
    summary = outline.preview(plan, md)
    assert summary["created"] == [] and summary["deleted"] == [] and summary["renamed"] == []
    assert (summary["phases"], summary["milestones"], summary["tasks"]) == (2, 2, 2)
    before = set(Milestone.objects.values_list("pk", "completed_at"))
    outline.apply(plan, md)
    assert set(Milestone.objects.values_list("pk", "completed_at")) == before
    assert outline.plan_to_markdown(plan) == md


def test_parse_accepts_loose_syntax_and_reports_errors():
    specs = outline.parse_outline(
        "# Setup [In Progress] (2026-01-01 -> )\n"
        "> why\n"
        "* [ ] First thing (2026-02-01)\n"
        "\t- second task without checkbox\n"
        "- plain milestone\n"
        "# Done phase [complete]\n"
    )
    assert specs[0].status == "in_progress" and specs[0].start == datetime.date(2026, 1, 1)
    assert specs[0].end is None and specs[0].objective == "why"
    assert specs[0].milestones[0].due == datetime.date(2026, 2, 1)
    assert specs[0].milestones[0].tasks[0].title == "second task without checkbox"
    assert specs[0].milestones[1].title == "plain milestone"
    assert specs[1].status == "done"
    with pytest.raises(outline.OutlineError) as exc:
        outline.parse_outline("- [ ] orphan\n# ok [weird]\n- [ ] x (due 2026-13-40)\nnonsense\n")
    lines = [e["line"] for e in exc.value.errors]
    assert lines == [1, 2, 3, 4]


def test_apply_creates_renames_reorders_and_deletes(plan):
    p1 = Phase.objects.get(name="Literature review")
    p2 = Phase.objects.get(name="Pilot")
    m1 = Milestone.objects.get(title="Annotated bibliography")
    md = (
        f"# Pilot study  [blocked]  {{#{p2.pk}}}\n"
        "- [ ] Ethics approval  (due 2026-11-01)\n"
        "  - [ ] Draft the consent form\n"
        f"# Literature review  [done]  {{#{p1.pk}}}\n"
        f"- [x] Bibliography of 30 papers  {{#{m1.pk}}}\n"
        "  - [x] Rate on the matrix\n"
    )
    summary = outline.preview(plan, md)
    assert "phase “Pilot” → “Pilot study”" in summary["renamed"]
    assert "milestone “Annotated bibliography” → “Bibliography of 30 papers”" in summary["renamed"]
    assert "milestone “Ethics approval”" in summary["created"]
    assert "milestone “Paradigm chosen”" in summary["deleted"]
    assert "task “Pull citing papers”" in summary["deleted"]
    assert "task “Rate on the matrix”" in summary["deleted"]  # no id → new task, old one goes
    outline.apply(plan, md)
    p2.refresh_from_db()
    p1.refresh_from_db()
    m1.refresh_from_db()
    assert (p2.name, p2.order, p2.status) == ("Pilot study", 1, "blocked")
    assert (p1.order, p1.status) == (2, "done")
    assert m1.title == "Bibliography of 30 papers" and m1.completed_at is not None
    assert not Milestone.objects.filter(title="Paradigm chosen").exists()
    assert Task.objects.get(title="Rate on the matrix").done is True
    ethics = Milestone.objects.get(title="Ethics approval")
    assert ethics.phase == p2 and ethics.due_date == datetime.date(2026, 11, 1)
    assert ethics.tasks.get().title == "Draft the consent form"


def test_apply_keeps_completion_timestamp_when_still_done(plan):
    done = Milestone.objects.get(title="Paradigm chosen")
    stamp = done.completed_at
    md = outline.plan_to_markdown(plan).replace("[x] Paradigm chosen", "[x] Paradigm chosen!")
    outline.apply(plan, md)
    done.refresh_from_db()
    assert done.title == "Paradigm chosen!" and done.completed_at == stamp
    outline.apply(
        plan, outline.plan_to_markdown(plan).replace("[x] Paradigm chosen!", "[ ] Paradigm chosen!")
    )
    done.refresh_from_db()
    assert done.completed_at is None


def test_outline_api(client, settings, plan, django_user_model):
    settings.ATLAS_API_KEY = KEY
    django_user_model.objects.create_superuser("owner", password="pw")
    got = client.get("/api/v1/projects/deep/outline/", **HEADERS)
    assert got.status_code == 200 and got.json()["markdown"].startswith("# Literature review")
    bad = client.post(
        "/api/v1/projects/deep/outline/",
        {"markdown": "nonsense line", "dry_run": True},
        content_type="application/json",
        **HEADERS,
    )
    assert bad.status_code == 400 and bad.json()["errors"][0]["line"] == 1
    dry = client.post(
        "/api/v1/projects/deep/outline/",
        {"markdown": "# Only phase\n- [ ] One milestone", "dry_run": True},
        content_type="application/json",
        **HEADERS,
    )
    assert dry.status_code == 200 and dry.json()["applied"] is False
    assert Phase.objects.filter(project=plan).count() == 2
    real = client.post(
        "/api/v1/projects/deep/outline/",
        {"markdown": "# Only phase\n- [ ] One milestone"},
        content_type="application/json",
        **HEADERS,
    )
    assert real.status_code == 200 and real.json()["applied"] is True
    assert list(Phase.objects.filter(project=plan).values_list("name", flat=True)) == ["Only phase"]
    assert real.json()["markdown"].startswith("# Only phase  [not_started]  {#")
