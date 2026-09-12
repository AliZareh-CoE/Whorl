"""Notes v2 slice 3 — templates and Markdown export with a bibliography."""

import datetime

import pytest

from literature.reading import add_highlight
from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from notes import templates
from notes.models import Note
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
KEY = "k"
HEADERS = {"HTTP_X_API_KEY": KEY}
TODAY = datetime.date(2026, 9, 6)


@pytest.fixture
def world(settings, django_user_model):
    settings.ATLAS_API_KEY = KEY
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    ref = ReferenceFactory(
        bibtex_key="lavie2010attention",
        title="Attention, distraction and cognitive control under load",
        authors=[{"family": "Lavie", "given": "Nilli"}],
        year=2010,
        venue="Current Directions",
        doi="10.1/xyz",
    )
    ProjectReferenceFactory(project=project, reference=ref)
    return project, ref


def test_literature_note_carries_metadata_and_highlights(world):
    project, ref = world
    add_highlight(
        ref, "Perceptual load gates distractors.", page=3, project=project, comment="core claim"
    )
    note = templates.create_from_template("literature", project, reference=ref)
    assert note.title.startswith("Lavie 2010 — Attention, distraction")
    assert note.body.startswith("@lavie2010attention\n")
    assert (
        "Nilli Lavie · 2010 · Current Directions" in note.body and "doi.org/10.1/xyz" in note.body
    )
    assert (
        "## Highlights" in note.body
        and "> Perceptual load gates distractors.\n> — (p.3)" in note.body
    )
    assert "core claim" in note.body and "See also [[Highlights — lavie2010attention]]" in note.body
    assert list(note.references.all()) == [ref]
    # a second literature note for the same paper gets a distinct title
    again = templates.create_from_template("literature", project, reference=ref)
    assert again.title.endswith("(2)")


def test_daily_note_pulls_the_week_focus_and_is_unique_per_day(world):
    project, _ = world
    phase = PhaseFactory(project=project, order=1, status="in_progress")
    MilestoneFactory(phase=phase, title="Late thing", due_date=datetime.date(2026, 9, 1))
    MilestoneFactory(phase=phase, title="Soon thing", due_date=datetime.date(2026, 9, 9))
    note = templates.create_from_template("daily", project, today=TODAY)
    assert note.title == "2026-09-06" and "# Sunday, 06 September 2026" in note.body
    assert "- [ ] Late thing — 5 d late" in note.body and "- [ ] Soon thing — in 3 d" in note.body
    assert templates.create_from_template("daily", project, today=TODAY) == note
    assert Note.objects.filter(project=project).count() == 1


def test_other_templates_and_errors(world):
    project, _ = world
    meeting = templates.create_from_template("meeting", project, today=TODAY)
    assert meeting.title == "Meeting — 2026-09-06" and "## Actions" in meeting.body
    experiment = templates.create_from_template("experiment", project, today=TODAY)
    assert experiment.title == "Experiment — 2026-09-06" and "## Hypothesis" in experiment.body
    with pytest.raises(ValueError):
        templates.render_template("literature", project)
    with pytest.raises(ValueError):
        templates.render_template("nope", project)


def test_export_with_bibliography(world):
    project, ref = world
    note = Note.objects.create(
        project=project, title="Hub", body="Cites @lavie2010attention and [[Other]]."
    )
    note.references.add(ref)
    out = templates.export_note(note, "apa")
    assert out["references"] == 1 and out["markdown"].startswith(
        "# Hub\n\nCites @lavie2010attention and [[Other]]."
    )
    assert "## References" in out["markdown"] and "Lavie, N. (2010)" in out["markdown"]
    assert templates.export_note(note, "bogus")["style"] == "apa"
    empty = Note.objects.create(project=project, title="Empty", body="")
    assert "## References" not in templates.export_note(empty)["markdown"]


def test_templates_api(client, world):
    project, ref = world
    kinds = [t["kind"] for t in client.get("/api/v1/notes/templates/", **HEADERS).json()]
    assert kinds == ["blank", "literature", "daily", "meeting", "experiment"]
    bad = client.post(
        "/api/v1/notes/from-template/",
        {"project": "deep", "kind": "literature"},
        content_type="application/json",
        **HEADERS,
    )
    assert bad.status_code == 400
    made = client.post(
        "/api/v1/notes/from-template/",
        {"project": "deep", "kind": "literature", "reference": ref.pk},
        content_type="application/json",
        **HEADERS,
    )
    assert (
        made.status_code == 201
        and made.json()["references_detail"][0]["bibtex_key"] == "lavie2010attention"
    )
    export = client.get(f"/api/v1/notes/{made.json()['id']}/export/?style=ieee", **HEADERS).json()
    assert export["style"] == "ieee" and "## References" in export["markdown"]
