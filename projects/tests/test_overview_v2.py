"""Overview v2 slice 1 — week digest, open questions, manuscripts at a glance, hypotheses."""

import datetime

import pytest
from django.utils import timezone

from plans.tests.factories import MilestoneFactory, PhaseFactory, ResearchQuestionFactory
from projects import overview
from projects.tests.factories import ProjectFactory
from research.models import Hypothesis
from writing.models import Manuscript

pytestmark = pytest.mark.django_db
TODAY = datetime.date(2026, 9, 6)


def test_week_digest_counts_recent_events_only():
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project, order=1)
    MilestoneFactory(phase=phase, title="fresh", completed_at=timezone.now())
    old = MilestoneFactory(phase=phase, title="old")
    old.completed_at = timezone.now() - datetime.timedelta(days=30)
    old.save()
    project.decisions.create(title="Go dual-task", decision="yes", decided_on=TODAY)
    digest = overview.week_digest(project, today=TODAY)
    kinds = {c["kind"]: c["count"] for c in digest["counts"]}
    assert kinds.get("milestone") == 1 and kinds.get("decision") == 1
    assert digest["total"] == 2 and digest["since"] == "2026-08-30"
    assert all(i["date"] >= "2026-08-30" for i in digest["items"])


def test_open_questions_ordering_and_manuscripts_glance():
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project, order=1, name="Pilot")
    answered = ResearchQuestionFactory(project=project, question="Answered?", status="answered")
    open_q = ResearchQuestionFactory(project=project, question="Open?")
    open_q.phases.add(phase)
    ResearchQuestionFactory(project=project, question="Dead?", status="abandoned")
    qs = overview.open_questions(project)
    assert [q["question"] for q in qs] == ["Open?", "Answered?", "Dead?"] and qs[0]["phases"] == [
        "Pilot"
    ]
    assert answered.pk == qs[1]["id"]
    Manuscript.objects.create(
        project=project,
        title="Late",
        status="drafting",
        deadline=datetime.date(2026, 9, 10),
        venue_limits={"references": 1},
    )
    Manuscript.objects.create(project=project, title="Undated", status="idea")
    Manuscript.objects.create(
        project=project, title="Done", status="published", deadline=datetime.date(2026, 1, 1)
    )
    glance = overview.manuscripts_glance(project, today=TODAY)
    assert [m["title"] for m in glance] == ["Late", "Undated"]
    assert glance[0]["days"] == 4 and glance[0]["over"] == [] and glance[1]["days"] is None


def test_hypotheses_summary_and_overview_api(client, settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    Hypothesis.objects.create(project=project, statement="H1", status="testing")
    Hypothesis.objects.create(project=project, statement="H2", status="supported")
    assert overview.hypotheses_summary(project) == {
        "total": 2,
        "by_status": {"testing": 1, "supported": 1},
    }
    out = client.get("/api/v1/projects/deep/overview/", HTTP_X_API_KEY="k").json()
    assert {"week_digest", "questions", "manuscripts", "hypotheses"} <= set(out)
    assert out["hypotheses"]["total"] == 2 and out["week_digest"]["total"] >= 0


@pytest.mark.django_db
def test_themes_weights_phrases_by_how_many_sources_carry_them(client, settings, django_user_model):
    from literature.models import ProjectReference, Reference
    from notes.models import Note
    from projects import overview
    from projects.models import Project

    project = Project.objects.create(name="Attention", slug="attention")
    for i in range(3):
        ref = Reference.objects.create(
            title=f"Perceptual load and selective attention {i}",
            bibtex_key=f"load{i}",
            abstract="Perceptual load determines selective attention under distraction.",
        )
        ProjectReference.objects.create(project=project, reference=ref)
    Note.objects.create(
        project=project, title="Perceptual load overview", body="Notes on perceptual load."
    )
    rows = overview.themes(project)
    assert rows and rows[0]["label"].startswith("perceptual load") and rows[0]["weight"] >= 4
    assert all(set(r) == {"label", "weight"} for r in rows)
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    data = client.get("/api/v1/projects/attention/overview/", HTTP_X_API_KEY="k").json()
    assert data["themes"][0]["label"] == rows[0]["label"]
    empty = Project.objects.create(name="Empty", slug="empty")
    assert overview.themes(empty) == []
