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


def test_manuscripts_glance_carries_the_writing_signals():
    """#479: the overview shows what the studio knows — clock, nudge, readiness."""
    import datetime
    from pathlib import Path

    from writing.models import Manuscript, ManuscriptFile, SubmissionEvent

    project = ProjectFactory()
    waiting = Manuscript.objects.create(
        project=project, title="Waiting", status="under_review", target_venue="Slow"
    )
    SubmissionEvent.objects.create(
        manuscript=waiting, kind="submitted", date=datetime.date(2026, 1, 1)
    )
    working = Manuscript.objects.create(project=project, title="Working", status="drafting")
    ManuscriptFile.objects.filter(manuscript=working).delete()
    ManuscriptFile.objects.create(
        manuscript=working, path="main.tex", kind="tex", content="x", is_main=True
    )
    rows = {
        r["title"]: r
        for r in overview.manuscripts_glance(project, today=datetime.date(2026, 9, 13))
    }
    assert rows["Waiting"]["clock"]["label"].endswith("d under review")
    assert rows["Waiting"]["clock"]["nudge"]["due"] is True and rows["Waiting"]["readiness"] is None
    assert "nudge" not in rows["Working"]["clock"]
    assert (
        rows["Working"]["readiness"]["ready"] is False
        and rows["Working"]["readiness"]["fails"] >= 1
    )
    assert "blocking" in rows["Working"]["readiness"]["summary"]
    tsx = Path("frontend/src/app/pages/ProjectOverview.tsx").read_text()
    for needle in ('data-testid="glance-clock"', 'data-testid="glance-readiness"', "nudge?"):
        assert needle in tsx, needle


def test_literature_glance_counts_and_queue_head(client_logged_in):
    """#480: to-read (with the high-priority share), read this month, the next paper up."""
    import datetime
    from pathlib import Path

    from literature.models import ProjectReference
    from literature.tests.factories import ReferenceFactory

    project = ProjectFactory()
    today = datetime.date(2026, 9, 13)
    a = ProjectReference.objects.create(
        project=project, reference=ReferenceFactory(title="Old normal"), reading_status="to_read"
    )
    b = ProjectReference.objects.create(
        project=project,
        reference=ReferenceFactory(title="Urgent"),
        reading_status="to_read",
        priority="high",
    )
    c = ProjectReference.objects.create(
        project=project, reference=ReferenceFactory(title="Done"), reading_status="read"
    )
    out = overview.literature_glance(project, today=today)
    assert out["total"] == 3 and out["to_read"] == 2 and out["high_priority_unread"] == 1
    assert out["by_status"] == {"to_read": 2, "read": 1}
    assert out["read_this_month"] == 1  # c was updated now, i.e. this month
    assert out["next_up"]["title"] == "Urgent" and out["next_up"]["priority"] == "high"
    assert out["last_added"]["title"] == "Done"
    assert a.pk and b.pk and c.pk
    body = client_logged_in.get(f"/api/v1/projects/{project.slug}/overview/").json()
    assert body["literature"]["to_read"] == 2 and body["literature"]["next_up"]["title"] == "Urgent"
    empty = overview.literature_glance(ProjectFactory(), today=today)
    assert empty["total"] == 0 and empty["next_up"] is None and empty["last_added"] is None
    tsx = Path("frontend/src/app/pages/ProjectOverview.tsx").read_text()
    for needle in (
        'data-testid="literature-glance"',
        'data-testid="literature-to-read"',
        'data-testid="literature-next"',
    ):
        assert needle in tsx, needle


def test_notebook_glance_notes_lab_log_and_datasets(client_logged_in):
    """#481: notes (edited this week, unlinked, last edited), the lab log (last entry, quiet
    after two weeks, this month) and the dataset count."""
    from pathlib import Path

    from notes.models import Note, NoteLink
    from research.models import Dataset, ExperimentEntry

    today = datetime.date(2026, 9, 13)
    project = ProjectFactory()
    a = Note.objects.create(project=project, title="Alpha", body="[[Beta]]")
    b = Note.objects.create(project=project, title="Beta")
    c = Note.objects.create(project=project, title="Gamma, alone")
    NoteLink.objects.get_or_create(source=a, target=b)
    Note.objects.filter(pk=c.pk).update(updated_at=timezone.now() - datetime.timedelta(days=30))
    ExperimentEntry.objects.create(project=project, date=datetime.date(2026, 8, 20), title="Old")
    ExperimentEntry.objects.create(project=project, date=datetime.date(2026, 9, 2), title="Pilot")
    Dataset.objects.create(project=project, name="raw", location="/data/raw")
    out = overview.notebook_glance(project, today=today)
    assert out["notes"]["total"] == 3 and out["notes"]["unlinked"] == 1
    assert out["notes"]["edited_this_week"] == 2
    assert out["notes"]["last_edited"]["title"] in ("Alpha", "Beta")
    assert out["notes"]["last_edited"]["days"] == 0
    assert [r["title"] for r in out["notes"]["recent"]][-1] == "Gamma, alone"
    assert out["notes"]["recent"][-1]["days"] == 30 and len(out["notes"]["recent"]) == 3
    ex = out["experiments"]
    assert ex["total"] == 2 and ex["this_month"] == 1 and ex["last"]["title"] == "Pilot"
    assert ex["last"]["days"] == 11 and ex["quiet"] is False
    assert out["datasets"]["total"] == 1
    quiet = overview.notebook_glance(project, today=datetime.date(2026, 9, 20))
    assert quiet["experiments"]["quiet"] is True and quiet["experiments"]["last"]["days"] == 18
    body = client_logged_in.get(f"/api/v1/projects/{project.slug}/overview/").json()
    assert body["notebook"]["notes"]["unlinked"] == 1 and body["notebook"]["datasets"]["total"] == 1
    empty = overview.notebook_glance(ProjectFactory(), today=today)
    assert empty["notes"]["last_edited"] is None and empty["experiments"]["last"] is None
    assert empty["experiments"]["quiet"] is False and empty["datasets"]["total"] == 0
    tsx = Path("frontend/src/app/pages/ProjectOverview.tsx").read_text()
    for needle in (
        'data-testid="notebook-glance"',
        'data-testid={i === 0 ? "notebook-last-note" : undefined}',
        'data-testid="notebook-last-entry"',
        "notebook.experiments.quiet",
    ):
        assert needle in tsx, needle
