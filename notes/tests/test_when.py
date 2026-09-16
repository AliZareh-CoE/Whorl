"""#500 — dates and times written into a capture."""

from datetime import date, time
from pathlib import Path

import pytest

from notes import capture as cap
from notes.models import QuickCapture
from notes.when import parse_when

WED = date(2026, 9, 16)  # a Wednesday


@pytest.mark.parametrize(
    "text, day, clock, cleaned",
    [
        ("send the IRB form by Friday 3pm", date(2026, 9, 18), time(15, 0), "send the IRB form"),
        ("call Sam tomorrow at 9:30am", date(2026, 9, 17), time(9, 30), "call Sam"),
        ("freeze the design by Oct 1", date(2026, 10, 1), None, "freeze the design"),
        ("freeze the design on October 1st, 2027", date(2027, 10, 1), None, "freeze the design"),
        ("submit abstract 1 Oct", date(2026, 10, 1), None, "submit abstract"),
        ("book the room 2026-11-03 at 14:00", date(2026, 11, 3), time(14, 0), "book the room"),
        ("email the pool in 3 days", date(2026, 9, 19), None, "email the pool"),
        ("email the pool in two weeks", date(2026, 9, 30), None, "email the pool"),
        ("draft the letter next week", date(2026, 9, 23), None, "draft the letter"),
        ("renew the licence next month", date(2026, 10, 1), None, "renew the licence"),
        ("pilot results end of the week", date(2026, 9, 18), None, "pilot results"),
        ("close the books by end of month", date(2026, 9, 30), None, "close the books"),
        ("standup today at noon", WED, time(12, 0), "standup"),
        ("lab meeting Monday", date(2026, 9, 21), None, "lab meeting"),
        ("lab meeting next Monday", date(2026, 9, 21), None, "lab meeting"),  # already next week
        (
            "lab meeting next Friday",
            date(2026, 9, 25),
            None,
            "lab meeting",
        ),  # this one is still ahead
        ("read the Friday talk transcript", None, None, "read the Friday talk transcript"),
        ("meet at 3", None, None, "meet at 3"),
        ("the 2024 preprint", None, None, "the 2024 preprint"),
        ("Feb 30 is not a day", None, None, "Feb 30 is not a day"),
    ],
)
def test_parse_when_reads_the_phrase_and_leaves_the_rest(text, day, clock, cleaned):
    out = parse_when(text, WED)
    assert (out["date"], out["time"], out["text"]) == (day, clock, cleaned)


def test_parse_when_only_reads_the_first_line():
    out = parse_when("idea: pilot notes by Friday\nMonday was slow, the rest tomorrow", WED)
    assert out["date"] == date(2026, 9, 18)
    assert out["text"] == "idea: pilot notes\nMonday was slow, the rest tomorrow"


@pytest.mark.django_db
def test_detect_and_convert_carry_the_date(client, settings, django_user_model):
    from core.models import TodoItem
    from plans.models import Milestone
    from plans.tests.factories import PhaseFactory
    from projects.tests.factories import ProjectFactory

    project = ProjectFactory(slug="attention")
    PhaseFactory(project=project, name="Pilot", status="in_progress")
    c = QuickCapture.objects.create(text="todo: send the form by 2026-10-02 at 3pm")
    hint = cap.detect(c.text)
    assert hint["due"] == "2026-10-02" and hint["due_time"] == "15:00"
    assert hint["title"] == "send the form by 2026-10-02 at 3pm"  # the hint keeps the words
    made = cap.convert(c, "todo", project, tz="Europe/Berlin")
    todo = TodoItem.objects.get(pk=made["id"])
    assert todo.text == "send the form" and made["title"] == "send the form"
    assert todo.due_at.isoformat() == "2026-10-02T13:00:00+00:00"  # 15:00 Berlin (CEST)
    d = QuickCapture.objects.create(text="todo: call the vendor at 9:30am")
    cap.convert(d, "todo", None, tz="+05:30")
    assert (
        TodoItem.objects.get(text="call the vendor").due_at.isoformat().endswith("T04:00:00+00:00")
    )
    e = QuickCapture.objects.create(text="todo: buy stamps 2026-12-24")
    cap.convert(e, "todo", None, tz="nonsense/zone")  # unknown zone: the server's
    stamps = TodoItem.objects.get(text="buy stamps")  # #546: a bare date is an all-day item at noon
    assert stamps.due_at.isoformat() == "2026-12-24T12:00:00+00:00" and stamps.all_day
    f = QuickCapture.objects.create(text="todo: nothing dated here")
    cap.convert(f, "todo", None)
    assert TodoItem.objects.get(text="nothing dated here").due_at is None
    m = QuickCapture.objects.create(text="milestone: freeze the design by 2026-11-15")
    made = cap.convert(m, "milestone", project)
    ms = Milestone.objects.get(pk=made["id"])
    assert ms.title == "freeze the design" and ms.due_date == date(2026, 11, 15)
    assert made["due_date"] == "2026-11-15"
    m2 = QuickCapture.objects.create(text="milestone: analysis frozen by 2026-11-15")
    made = cap.convert(m2, "milestone", project, due=date(2026, 12, 1))  # explicit wins
    assert Milestone.objects.get(pk=made["id"]).due_date == date(2026, 12, 1)

    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("atlas", "a@b.c", "atlas")
    g = QuickCapture.objects.create(text="todo: ship the revision by 2026-10-09 at 17:00")
    r = client.post(
        f"/api/v1/quick-capture/{g.id}/convert/",
        {"target": "todo", "tz": "America/New_York"},
        content_type="application/json",
        HTTP_X_API_KEY="k",
        HTTP_HOST="127.0.0.1",
    )
    assert r.status_code == 201 and r.json()["due_at"] == "2026-10-09T21:00:00+00:00"
    listed = client.get(
        "/api/v1/quick-capture/?processed=false", HTTP_X_API_KEY="k", HTTP_HOST="127.0.0.1"
    ).json()["results"]
    assert all("due" in row["hint"] and "due_time" in row["hint"] for row in listed)
    tsx = Path("frontend/src/app/pages/Inbox.tsx").read_text()
    for needle in ('data-testid="when-chip"', "resolvedOptions().timeZone", "hint.due_time"):
        assert needle in tsx, needle
