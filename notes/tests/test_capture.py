"""Inbox v2 slice 1 — smart capture triage."""

from pathlib import Path

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


@pytest.mark.django_db
def test_snooze_parses_keywords_and_hides_the_capture_until_its_day(
    client, settings, django_user_model
):
    from datetime import date

    from notes.capture import open_captures, snooze, snooze_date, snoozed_captures

    wed = date(2026, 9, 16)  # a Wednesday
    assert snooze_date("tomorrow", wed) == date(2026, 9, 17)
    assert snooze_date("monday", wed) == date(2026, 9, 21)
    assert snooze_date("next-week", wed) == date(2026, 9, 23)
    assert snooze_date("weekend", wed) == date(2026, 9, 19)
    assert snooze_date("2026-10-01", wed) == date(2026, 10, 1)
    assert snooze_date("", wed) is None and snooze_date(None, wed) is None
    assert snooze_date("monday", date(2026, 9, 14)) == date(2026, 9, 21)  # on a Monday: next one
    with pytest.raises(ValueError):
        snooze_date("someday", wed)
    with pytest.raises(ValueError):
        snooze_date("2026-09-16", wed)  # not after today

    c = QuickCapture.objects.create(text="Ask the ethics office")
    snooze(c, "next-week", wed)
    assert c.snoozed_until == date(2026, 9, 23)
    assert list(open_captures(today=wed)) == []
    assert list(snoozed_captures(today=wed)) == [c]
    assert list(open_captures(today=date(2026, 9, 23))) == [c]  # its day: back in the inbox
    snooze(c, "", wed)
    assert c.snoozed_until is None and list(open_captures(today=wed)) == [c]

    # API: the action, its validation, and the filters the inbox uses
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("atlas", "a@b.c", "atlas")
    r = client.post(
        f"/api/v1/quick-capture/{c.id}/snooze/",
        {"until": "tomorrow"},
        content_type="application/json",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert r.status_code == 200 and r.json()["snoozed_until"] is not None
    r = client.get(
        "/api/v1/quick-capture/?processed=false&snoozed=false",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert c.id not in [row["id"] for row in r.json()["results"]]
    r = client.get("/api/v1/quick-capture/?snoozed=true", HTTP_X_API_KEY="k", HTTP_HOST="127.0.0.1")
    assert [row["id"] for row in r.json()["results"]] == [c.id]
    r = client.post(
        f"/api/v1/quick-capture/{c.id}/snooze/",
        {"until": "someday"},
        content_type="application/json",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert r.status_code == 400 and "until" in r.json()["detail"]
    r = client.post(
        f"/api/v1/quick-capture/{c.id}/snooze/",
        {"until": ""},
        content_type="application/json",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert r.status_code == 200 and r.json()["snoozed_until"] is None


@pytest.mark.django_db
def test_snoozed_captures_leave_the_untriaged_counts():
    from datetime import timedelta

    from django.utils import timezone

    from core.dashboard import needs_attention

    QuickCapture.objects.create(text="awake")
    QuickCapture.objects.create(
        text="asleep", snoozed_until=timezone.localdate() + timedelta(days=3)
    )
    assert [c.text for c in needs_attention()["inbox"]] == ["awake"]


@pytest.mark.django_db
def test_captures_remember_what_they_became(client, settings, django_user_model):
    """#496: convert records the object, triage stamps the time, the history resolves titles
    in batched lookups and flags objects that were deleted since."""
    from django.utils import timezone

    from notes.capture import became, triage_history

    project = ProjectFactory(name="Attention", slug="attention")
    PhaseFactory(project=project, name="Pilot", status="in_progress")
    c_note = QuickCapture.objects.create(text="idea: Write up the pilot lessons")
    c_ms = QuickCapture.objects.create(text="milestone: Freeze the design")
    c_todo = QuickCapture.objects.create(text="todo: Email the pool")
    c_dec = QuickCapture.objects.create(text="decision: Drop the third block")
    c_filed = QuickCapture.objects.create(text="Filed under attention", project=project)
    c_gone = QuickCapture.objects.create(text="Dismissed")
    cap.convert(c_note, "note", project)
    cap.convert(c_ms, "milestone", project)
    cap.convert(c_todo, "todo", project)
    cap.convert(c_dec, "decision", project)
    for c in (c_filed, c_gone):
        c.processed = True
        c.triaged_at = timezone.now()
        c.save()
    c_note.refresh_from_db()
    assert c_note.became_kind == "note" and c_note.became_id and c_note.triaged_at
    assert became(c_note) == {
        "kind": "note",
        "id": c_note.became_id,
        "app_url": f"/projects/attention/notes/{c_note.became_id}",
    }
    assert became(c_filed) is None and became(c_gone) is None
    Milestone.objects.filter(pk=c_ms.became_id).delete()  # the object may vanish later

    rows = {r["id"]: r for r in triage_history()}
    assert rows[c_note.id]["outcome"] == "converted"
    assert rows[c_note.id]["became"]["title"] == "Write up the pilot lessons"
    assert rows[c_note.id]["became"]["exists"] is True
    assert rows[c_ms.id]["became"]["exists"] is False and rows[c_ms.id]["became"]["title"] == ""
    assert rows[c_todo.id]["became"]["app_url"] == "/today"
    assert rows[c_dec.id]["became"]["app_url"].startswith("/projects/attention/decisions?id=")
    assert rows[c_filed.id]["outcome"] == "filed" and rows[c_filed.id]["project"] == "attention"
    assert rows[c_gone.id]["outcome"] == "dismissed" and rows[c_gone.id]["became"] is None
    assert [r["id"] for r in triage_history(limit=2)] == sorted(rows)[-2:][::-1]

    # API: the history action, its limit guard, `became` on the row, and PATCH stamping
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("atlas", "a@b.c", "atlas")
    r = client.get(
        "/api/v1/quick-capture/history/?limit=3", HTTP_X_API_KEY="k", HTTP_HOST="127.0.0.1"
    )
    assert r.status_code == 200 and len(r.json()["results"]) == 3
    assert (
        client.get(
            "/api/v1/quick-capture/history/?limit=x", HTTP_X_API_KEY="k", HTTP_HOST="127.0.0.1"
        ).status_code
        == 400
    )
    r = client.get(f"/api/v1/quick-capture/{c_note.id}/", HTTP_X_API_KEY="k", HTTP_HOST="127.0.0.1")
    assert r.json()["became"]["kind"] == "note" and r.json()["triaged_at"]
    fresh = QuickCapture.objects.create(text="fresh")
    r = client.patch(
        f"/api/v1/quick-capture/{fresh.id}/",
        {"processed": True},
        content_type="application/json",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert r.status_code == 200 and r.json()["triaged_at"] is not None
    r = client.patch(
        f"/api/v1/quick-capture/{fresh.id}/",
        {"processed": False},
        content_type="application/json",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert r.json()["triaged_at"] is None
    tsx = Path("frontend/src/app/pages/Inbox.tsx").read_text()
    for needle in (
        'data-testid="history-toggle"',
        'data-testid="history-row"',
        'data-testid="history-link"',
        'data-testid="history-put-back"',
        "/quick-capture/history/?limit=30",
    ):
        assert needle in tsx, needle


@pytest.mark.django_db
def test_bulk_triage_files_dismisses_snoozes_and_converts(client, settings, django_user_model):
    """#497: one action over many ids; only untriaged captures change; the classic bulk view
    and the API share the service."""
    from datetime import timedelta

    from django.utils import timezone

    from notes.capture import bulk_triage

    project = ProjectFactory(name="Attention", slug="attention")
    a, b, c, d = (QuickCapture.objects.create(text=f"todo: thing {i}") for i in range(4))
    done = QuickCapture.objects.create(text="already", processed=True)
    out = bulk_triage([a.id, b.id, done.id], "file", project)
    assert out == {"action": "file", "count": 2, "ids": [a.id, b.id]} or set(out["ids"]) == {
        a.id,
        b.id,
    }
    a.refresh_from_db()
    assert a.processed and a.project == project and a.triaged_at
    out = bulk_triage([c.id], "snooze", until="next-week")
    c.refresh_from_db()
    assert out["count"] == 1 and c.snoozed_until == timezone.localdate() + timedelta(days=7)
    assert bulk_triage([c.id], "wake")["count"] == 1
    c.refresh_from_db()
    assert c.snoozed_until is None
    out = bulk_triage([d.id], "todo", project)
    d.refresh_from_db()
    assert out["count"] == 1 and d.became_kind == "todo" and d.processed
    assert TodoItem.objects.filter(pk=d.became_id, text="thing 3").exists()
    assert bulk_triage([c.id], "dismiss")["count"] == 1
    with pytest.raises(ValueError):
        bulk_triage([c.id], "file")  # needs a project
    with pytest.raises(ValueError):
        bulk_triage([c.id], "explode")

    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("atlas", "a@b.c", "atlas")
    e, f = (QuickCapture.objects.create(text=f"more {i}") for i in range(2))
    r = client.post(
        "/api/v1/quick-capture/bulk/",
        {"ids": [e.id, f.id], "action": "file", "project": "attention"},
        content_type="application/json",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert r.status_code == 200 and r.json()["count"] == 2
    r = client.post(
        "/api/v1/quick-capture/bulk/",
        {"ids": [e.id], "action": "snooze", "until": "someday"},
        content_type="application/json",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert r.status_code == 400
    r = client.post(
        "/api/v1/quick-capture/bulk/",
        {"ids": [], "action": "dismiss"},
        content_type="application/json",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert r.status_code == 400

    # the classic bulk view
    client.login(username="atlas", password="atlas")
    g = QuickCapture.objects.create(text="classic")
    r = client.post("/inbox/bulk/", {"ids": [g.id], "action": "dismiss"}, HTTP_HOST="127.0.0.1")
    assert r.status_code == 302
    g.refresh_from_db()
    assert g.processed and g.triaged_at
    tsx = Path("frontend/src/app/pages/Inbox.tsx").read_text()
    for needle in (
        'data-testid="select-capture"',
        'data-testid="bulk-bar"',
        'data-testid="bulk-file"',
        'data-testid="bulk-dismiss"',
        "/quick-capture/bulk/",
    ):
        assert needle in tsx, needle


def test_browser_capture_deep_link_and_bookmarklet_are_wired():
    """#501: /inbox?capture=… captures once and drops the parameter; the Connect page offers
    the bookmarklet that sends a page there."""
    inbox = Path("frontend/src/app/pages/Inbox.tsx").read_text()
    for needle in (
        'searchParams.get("capture")',
        "deepLinkRef",
        'next.delete("capture")',
        "Captured from the browser",
    ):
        assert needle in inbox, needle
    connect = Path("frontend/src/app/pages/Connect.tsx").read_text()
    for needle in (
        'data-testid="connect-bookmarklet"',
        'data-testid="bookmarklet-code"',
        "/inbox?capture=",
        "encodeURIComponent(document.title",
    ):
        assert needle in connect, needle
