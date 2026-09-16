"""#431: Today items can carry a time — API field, MCP parameter, browser parser, sidebar nudge."""

import shutil
import subprocess
from pathlib import Path

import pytest
from django.conf import settings

from core.models import TodoItem

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
BASE = Path(settings.BASE_DIR)


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.mark.django_db
def test_due_at_round_trips_and_clears(client, owner):
    r = client.post(
        "/api/v1/todos/",
        {"text": "Call Sam", "due_at": "2026-09-07T15:00:00+02:00"},
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["due_at"] == "2026-09-07T13:00:00Z"  # stored in UTC, offset honoured
    item = TodoItem.objects.get(pk=body["id"])
    assert item.due_at.isoformat() == "2026-09-07T13:00:00+00:00"
    listed = client.get("/api/v1/todos/", **HEADERS).json()["results"][0]
    assert listed["due_at"] == "2026-09-07T13:00:00Z"
    cleared = client.patch(
        f"/api/v1/todos/{body['id']}/",
        {"due_at": None},
        content_type="application/json",
        **HEADERS,
    )
    assert cleared.status_code == 200 and cleared.json()["due_at"] is None
    plain = client.post(
        "/api/v1/todos/", {"text": "No time"}, content_type="application/json", **HEADERS
    ).json()
    assert plain["due_at"] is None


def test_mcp_client_sends_due_at(monkeypatch):
    from mcp_server import client as mcp_client

    seen = {}
    monkeypatch.setattr(
        mcp_client, "_request", lambda method, path, **kw: seen.update(kw, path=path) or {}
    )
    mcp_client.add_todo("Call Sam", due_at="2026-09-07T15:00:00+02:00")
    assert seen["json"] == {"text": "Call Sam", "due_at": "2026-09-07T15:00:00+02:00"}
    mcp_client.add_todo("Plain")
    assert seen["json"] == {"text": "Plain"}


def test_ui_wiring():
    today = (BASE / "frontend" / "src" / "app" / "pages" / "Today.tsx").read_text()
    for needle in (
        "parseDue",
        'data-testid="due-chip"',
        'data-testid="carried-over"',
        "sets a time",
    ):
        assert needle in today, needle
    layout = (BASE / "frontend" / "src" / "app" / "Layout.tsx").read_text()
    assert "<TodoNudge />" in layout
    nudge = (BASE / "frontend" / "src" / "app" / "TodoNudge.tsx").read_text()
    assert 'data-testid="todo-nudge"' in nudge and "nextDue" in nudge
    bar = (BASE / "frontend" / "src" / "app" / "CommandBar.tsx").read_text()
    assert "parseDue(raw)" in bar
    chunks = " ".join(  # the nudge lives in the Layout (spa.js), the chips in the Today chunk
        p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js")
    )
    assert "todo-nudge" in chunks and "due-chip" in chunks


NODE_CHECK = """
import { parseDue, nextDue, dueState, relativeDue, isLater, dayLabel, formatDue, repeatLabel } from "%s";
const now = new Date(2026, 8, 7, 10, 0, 0);
const t0 = now.getTime();
const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { console.error("FAIL", m, a, b); process.exit(1); } };
let p = parseDue("call Sam at 3pm", now); eq(p.text, "call Sam", "strip"); eq(new Date(p.due_at).getHours(), 15, "3pm");
p = parseDue("Book the scanner by 9:30", now); eq(p.text, "Book the scanner", "colon"); eq([new Date(p.due_at).getHours(), new Date(p.due_at).getMinutes()], [9, 30], "9:30");
p = parseDue("Stand-up at 8am", now); eq(new Date(p.due_at).getDate(), 8, "8am is two hours gone -> tomorrow");
p = parseDue("Email tomorrow at 9am", now); eq(p.text, "Email", "tomorrow stripped"); eq(new Date(p.due_at).getDate(), 8, "tomorrow");
p = parseDue("Read at 3 papers", now); eq(p.due_at, null, "bare 'at 3' is not a time"); eq(p.text, "Read at 3 papers", "untouched");
p = parseDue("Lunch at noon", now); eq(new Date(p.due_at).getHours(), 12, "noon");
p = parseDue("Meet at 12am", now); eq(new Date(p.due_at).getHours(), 0, "12am");
p = parseDue("at 5pm", now); eq(p.text, "at 5pm", "time-only text keeps the raw text");
eq(parseDue("Ping @ 4pm", now).text, "Ping", "@ form");
eq(parseDue("Ping @ 4pm", now).all_day, false, "a clock time is not all-day");
// #546: days without a time (now is Monday 7 Sep 2026)
p = parseDue("Email the lab tomorrow", now); eq(p.text, "Email the lab", "bare tomorrow stripped"); eq([new Date(p.due_at).getDate(), new Date(p.due_at).getHours(), p.all_day], [8, 12, true], "tomorrow noon all-day");
p = parseDue("Review Sam's draft on Friday", now); eq(p.text, "Review Sam's draft", "on Friday stripped"); eq(new Date(p.due_at).getDate(), 11, "Friday");
p = parseDue("Ping Sam Friday", now); eq(p.text, "Ping Sam", "weekday closing the sentence"); eq(new Date(p.due_at).getDate(), 11, "Friday at the end");
p = parseDue("Monday meeting notes", now); eq(p.due_at, null, "a weekday mid-sentence is text"); eq(p.text, "Monday meeting notes", "untouched");
p = parseDue("Slides by next Monday", now); eq(new Date(p.due_at).getDate(), 14, "next Monday said on a Monday is a week away");
p = parseDue("Rebook next week", now); eq(new Date(p.due_at).getDate(), 14, "next week = +7");
p = parseDue("Chase the reviewer in 3 days", now); eq(p.text, "Chase the reviewer", "in 3 days stripped"); eq(new Date(p.due_at).getDate(), 10, "+3");
p = parseDue("Standup on Friday at 9am", now); eq([new Date(p.due_at).getDate(), new Date(p.due_at).getHours(), p.all_day], [11, 9, false], "day + time");
eq(isLater(p.due_at, now), true, "Friday is later"); eq(isLater(new Date(2026, 8, 7, 23, 59).toISOString(), now), false, "tonight is today");
eq(dayLabel(p.due_at, now), "Friday", "day label"); eq(dayLabel(new Date(2026, 8, 8, 12).toISOString(), now), "tomorrow", "tomorrow label");
eq(formatDue(new Date(2026, 8, 8, 12).toISOString(), true, now), "tomorrow", "all-day chip has no clock");
eq(nextDue([{ id: 9, done: false, all_day: true, due_at: new Date(t0 + 30 * 60e3).toISOString() }], t0), null, "the nudge skips all-day items");
// #547: repeat rules, matched before the day phrases (now is Monday 7 Sep 2026)
p = parseDue("Prep the agenda every Monday", now); eq(p.text, "Prep the agenda", "every Monday stripped"); eq([p.repeat, new Date(p.due_at).getDate(), p.all_day], ["weekly", 14, true], "weekly, the coming Monday (a week off when today)");
p = parseDue("Water the plants every day", now); eq([p.repeat, p.due_at], ["daily", null], "daily with no day is today's");
p = parseDue("Stand-up every weekday at 9am", now); eq([p.repeat, new Date(p.due_at).getHours(), p.all_day], ["weekdays", 9, false], "rule + time");
p = parseDue("Backup the drive monthly", now); eq([p.repeat, new Date(p.due_at).getDate()], ["monthly", 7], "monthly with no day anchors today");
p = parseDue("Review the plan weekly on Friday", now); eq([p.repeat, new Date(p.due_at).getDate()], ["weekly", 11], "weekly + a day phrase");
eq(parseDue("Every day counts", now).repeat, "daily", "sentence-initial");
eq(repeatLabel("weekly", new Date(2026, 8, 21, 12).toISOString()), "every Monday", "label"); eq(repeatLabel("monthly", new Date(2026, 9, 3, 12).toISOString()), "monthly on the 3rd", "ordinal"); eq(repeatLabel("", null), "", "none");
const t = now.getTime();
const items = [{ id: 1, done: false, due_at: new Date(t + 3 * 3600e3).toISOString() }, { id: 2, done: false, due_at: new Date(t + 30 * 60e3).toISOString() }, { id: 3, done: true, due_at: new Date(t + 5 * 60e3).toISOString() }, { id: 4, done: false, due_at: new Date(t - 13 * 3600e3).toISOString() }];
eq(nextDue(items, t)?.id, 2, "nearest within two hours, ignoring done and stale");
eq(dueState(items[3].due_at, t), "overdue", "overdue"); eq(relativeDue(items[1].due_at, t), "in 30 min", "relative");
console.log("dueTime OK");
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_parser_under_node(tmp_path):
    """The parser runs in the browser; node's type stripping lets the real file be exercised."""
    src = (BASE / "frontend" / "src" / "app" / "dueTime.ts").resolve().as_posix()
    script = tmp_path / "check.mjs"
    script.write_text(NODE_CHECK % src)
    run = subprocess.run(
        ["node", "--experimental-strip-types", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "dueTime OK" in run.stdout
