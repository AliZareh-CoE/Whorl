"""Inbox v2 slice 1 — smart capture triage."""

import pytest

from core.models import TodoItem
from literature.tests.factories import ReferenceFactory
from notes import capture as cap
from notes.models import Note, QuickCapture
from plans.models import Milestone
from plans.tests.factories import PhaseFactory
from projects.models import DecisionRecord
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def test_detect_hints():
    d = cap.detect("Read https://doi.org/10.1038/nature14539 (LeCun).")
    assert (
        d["suggested"] == "paper"
        and d["doi"] == "10.1038/nature14539"
        and d["url"].startswith("https://doi.org")
    )
    assert cap.detect("arXiv:2101.00001v2 looks relevant")["arxiv_id"] == "2101.00001v2"
    assert cap.detect("todo: email the ethics board")["suggested"] == "todo"
    assert cap.detect("Decision: go with the dual-task paradigm")["suggested"] == "decision"
    assert cap.detect("idea: what if load is strategic?")["suggested"] == "note"
    assert cap.detect("milestone: pilot analysed")["suggested"] == "milestone"
    assert cap.detect("Buy coffee")["suggested"] == "todo"
    assert cap.detect("x" * 300)["suggested"] == "note"
    assert cap.detect("todo: email the ethics board")["title"] == "email the ethics board"


def test_convert_note_todo_milestone_decision():
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project, order=1, status="in_progress", name="Pilot")
    c1 = QuickCapture.objects.create(
        text="idea: load might be strategic\nsee https://example.org/x"
    )
    out = cap.convert(c1, "note", project)
    note = Note.objects.get(pk=out["id"])
    assert note.title == "load might be strategic" and "https://example.org/x" in note.body
    c1.refresh_from_db()
    assert c1.processed and c1.project == project
    c2 = QuickCapture.objects.create(text="todo: email the ethics board")
    out = cap.convert(c2, "todo")
    assert (
        TodoItem.objects.get(pk=out["id"]).text == "email the ethics board"
        and out["app_url"] == "/today"
    )
    c3 = QuickCapture.objects.create(text="milestone: pilot analysed")
    out = cap.convert(c3, "milestone", project)
    m = Milestone.objects.get(pk=out["id"])
    assert m.phase == phase and m.title == "pilot analysed" and out["phase"] == "Pilot"
    c4 = QuickCapture.objects.create(text="Decision: dual-task paradigm\nBecause it isolates load.")
    out = cap.convert(c4, "decision", project)
    d = DecisionRecord.objects.get(pk=out["id"])
    assert d.title == "dual-task paradigm" and d.decision == "Because it isolates load."
    with pytest.raises(ValueError):
        cap.convert(QuickCapture.objects.create(text="x"), "note")  # needs a project
    with pytest.raises(ValueError):
        cap.convert(QuickCapture.objects.create(text="no id here"), "paper")


def test_convert_paper_uses_the_identifier(monkeypatch):
    project = ProjectFactory(slug="deep")
    ref = ReferenceFactory(doi="10.1038/nature14539", title="Deep learning")
    monkeypatch.setattr(
        "literature.services.add_reference_by_identifier", lambda ident: (ref, False)
    )
    c = QuickCapture.objects.create(text="Read https://doi.org/10.1038/nature14539 (LeCun).")
    out = cap.convert(c, "paper", project)
    assert out["kind"] == "reference" and out["id"] == ref.pk and out["created"] is False
    assert project.project_references.filter(reference=ref).exists()


def test_convert_api_and_hint(client, settings, django_user_model, monkeypatch):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    ProjectFactory(slug="deep")
    c = QuickCapture.objects.create(text="todo: write the intro")
    listed = client.get("/api/v1/quick-capture/", HTTP_X_API_KEY="k").json()["results"]
    assert listed[0]["hint"]["suggested"] == "todo"
    out = client.post(
        f"/api/v1/quick-capture/{c.pk}/convert/",
        {"target": "todo"},
        content_type="application/json",
        HTTP_X_API_KEY="k",
    )
    assert out.status_code == 201 and out.json()["kind"] == "todo"
    bad = client.post(
        f"/api/v1/quick-capture/{c.pk}/convert/",
        {"target": "note"},
        content_type="application/json",
        HTTP_X_API_KEY="k",
    )
    assert bad.status_code == 400


def test_suggest_project_from_the_capture_words(client, settings, django_user_model):
    """#494: the project whose vocabulary the capture shares most is suggested; a name word
    weighs three; ties and weak matches give nothing; the hint carries it; the row uses it."""
    from pathlib import Path

    from notes.capture import project_index, suggest_project
    from notes.models import Note, QuickCapture
    from plans.tests.factories import ResearchQuestionFactory
    from projects.tests.factories import ProjectFactory

    attention = ProjectFactory(name="Attention and Working Memory", status="active")
    ResearchQuestionFactory(project=attention, question="Does load reduce vigilance?")
    Note.objects.create(project=attention, title="Load theory overview")
    sleep = ProjectFactory(name="Sleep and Consolidation", status="active")
    Note.objects.create(project=sleep, title="Slow-wave replay notes")
    ProjectFactory(name="Archived thing", status="archived")
    index = project_index()
    assert [r["name"] for r in index] == [attention.name, sleep.name]
    hit = suggest_project("Skim the two new load-theory papers on vigilance", index)
    assert hit and hit["slug"] == attention.slug and hit["score"] >= 2
    assert "load" in hit["terms"] and "vigilance" in hit["terms"]
    by_name = suggest_project("todo: email the sleep lab", index)
    assert by_name and by_name["slug"] == sleep.slug and by_name["score"] == 3  # a name word
    assert suggest_project("Buy coffee", index) is None
    assert suggest_project("", index) is None
    assert suggest_project("attention", []) is None
    ResearchQuestionFactory(project=sleep, question="Does load matter for replay?")
    assert suggest_project("load", project_index()) is None  # a tie says nothing
    user = django_user_model.objects.create_user("u", "u@example.com", "pw")
    client.force_login(user)
    QuickCapture.objects.create(text="Skim the two new load-theory papers on vigilance")
    body = client.get("/api/v1/quick-capture/").json()
    rows = body["results"] if isinstance(body, dict) else body
    assert rows[0]["hint"]["project"]["slug"] == attention.slug
    tsx = Path("frontend/src/app/pages/Inbox.tsx").read_text()
    for needle in ('data-testid="suggested-project"', "c.hint.project?.slug"):
        assert needle in tsx, needle
