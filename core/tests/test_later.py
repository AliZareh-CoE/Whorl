"""#546: the Today list has a Later — an item for a later day waits until that day; snooze
pushes one there; the boundary is shared by the page, the API, the dashboard and the brief."""

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.utils import timezone

from core import todos
from core.models import TodoItem
from mcp_server import client as mcp_client

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
BASE = Path(settings.BASE_DIR)
UTC = ZoneInfo("UTC")


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


def at(day: date, hour: int = 12, minute: int = 0) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC).replace(hour=hour, minute=minute)


@pytest.mark.django_db
class TestBoundary:
    def test_today_holds_undated_due_today_and_overdue_items(self):
        today = timezone.localdate()
        plain = TodoItem.objects.create(text="plain", position=1)
        later_today = TodoItem.objects.create(text="tonight", position=2, due_at=at(today, 23, 30))
        yesterday = TodoItem.objects.create(
            text="late", position=3, due_at=at(today - timedelta(days=1)), all_day=True
        )
        tomorrow = TodoItem.objects.create(
            text="tomorrow", position=4, due_at=at(today + timedelta(days=1), 0, 0)
        )
        done = TodoItem.objects.create(text="done", position=5, done=True)
        assert list(todos.open_today()) == [plain, later_today, yesterday]
        assert list(todos.open_later()) == [tomorrow]
        assert done not in todos.open_today() and done not in todos.open_later()

    def test_later_orders_by_day_then_position(self):
        today = timezone.localdate()
        b = TodoItem.objects.create(text="b", position=1, due_at=at(today + timedelta(days=3)))
        a = TodoItem.objects.create(text="a", position=2, due_at=at(today + timedelta(days=1)))
        c = TodoItem.objects.create(text="c", position=3, due_at=at(today + timedelta(days=1)))
        assert list(todos.open_later()) == [a, c, b]


@pytest.mark.django_db
class TestSnooze:
    def test_plain_item_becomes_all_day_at_noon(self):
        today = date(2026, 9, 16)  # a Wednesday
        item = TodoItem.objects.create(text="x", position=1)
        todos.snooze(item, "tomorrow", today=today)
        item.refresh_from_db()
        assert item.all_day and item.due_at == at(date(2026, 9, 17))
        todos.snooze(item, "monday", today=today)
        item.refresh_from_db()
        assert item.due_at == at(date(2026, 9, 21)) and item.all_day
        todos.snooze(item, "2026-10-02", today=today)
        item.refresh_from_db()
        assert item.due_at == at(date(2026, 10, 2))

    def test_timed_item_keeps_its_clock_time(self):
        today = date(2026, 9, 16)
        item = TodoItem.objects.create(text="call", position=1, due_at=at(today, 15, 30))
        todos.snooze(item, "next-week", today=today)
        item.refresh_from_db()
        assert item.due_at == at(date(2026, 9, 23), 15, 30) and not item.all_day

    def test_wake_brings_it_back_to_today(self):
        today = date(2026, 9, 16)
        all_day = TodoItem.objects.create(
            text="a", position=1, due_at=at(date(2026, 9, 18)), all_day=True
        )
        todos.snooze(all_day, "", today=today)
        all_day.refresh_from_db()
        assert all_day.due_at is None and not all_day.all_day
        timed = TodoItem.objects.create(text="t", position=2, due_at=at(date(2026, 9, 18), 9, 0))
        todos.snooze(timed, None, today=today)
        timed.refresh_from_db()
        assert timed.due_at == at(today, 9, 0) and not timed.all_day

    def test_rejects_the_past_and_nonsense(self):
        item = TodoItem.objects.create(text="x", position=1)
        with pytest.raises(ValueError):
            todos.snooze(item, "someday")
        with pytest.raises(ValueError):
            todos.snooze(item, "2020-01-01")


@pytest.mark.django_db
class TestApi:
    def test_when_filter_and_snooze_action(self, client, owner):
        today = timezone.localdate()
        now_item = TodoItem.objects.create(text="now", position=1)
        ahead = TodoItem.objects.create(
            text="ahead", position=2, due_at=at(today + timedelta(days=2)), all_day=True
        )
        rows = client.get("/api/v1/todos/?when=today", **HEADERS).json()["results"]
        assert [r["text"] for r in rows] == ["now"]
        rows = client.get("/api/v1/todos/?when=later", **HEADERS).json()["results"]
        assert [(r["text"], r["all_day"]) for r in rows] == [("ahead", True)]
        r = client.post(
            f"/api/v1/todos/{now_item.id}/snooze/",
            {"until": "tomorrow"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 200 and r.json()["all_day"]
        assert r.json()["due_at"].startswith((today + timedelta(days=1)).isoformat())
        assert client.get("/api/v1/todos/?when=today", **HEADERS).json()["count"] == 0
        r = client.post(
            f"/api/v1/todos/{ahead.id}/snooze/",
            {"until": ""},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 200 and r.json()["due_at"] is None
        r = client.post(
            f"/api/v1/todos/{ahead.id}/snooze/",
            {"until": "someday"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 400 and "tomorrow" in r.json()["detail"]

    def test_create_with_a_day(self, client, owner):
        today = timezone.localdate()
        r = client.post(
            "/api/v1/todos/",
            {"text": "Ask Priya", "due": "tomorrow"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 201 and r.json()["all_day"]
        assert r.json()["due_at"] == (today + timedelta(days=1)).isoformat() + "T12:00:00Z"
        assert "due" not in r.json()
        r = client.post(
            "/api/v1/todos/",
            {"text": "Bad", "due": "someday"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 400 and "due" in r.json()
        # the browser's own shape: due_at + all_day round-trip; clearing due_at clears all_day
        r = client.post(
            "/api/v1/todos/",
            {"text": "Typed", "due_at": at(today + timedelta(days=3)).isoformat(), "all_day": True},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 201 and r.json()["all_day"]
        r = client.patch(
            f"/api/v1/todos/{r.json()['id']}/",
            {"due_at": None},
            content_type="application/json",
            **HEADERS,
        )
        assert r.json()["due_at"] is None and r.json()["all_day"] is False

    def test_dashboard_and_brief_count_only_today(self, client, owner):
        today = timezone.localdate()
        TodoItem.objects.create(text="today's", position=1)
        TodoItem.objects.create(
            text="friday's", position=2, due_at=at(today + timedelta(days=2)), all_day=True
        )
        data = client.get("/api/v1/dashboard/", **HEADERS).json()
        assert data["todos_open"] == 1 and [t["text"] for t in data["todos"]] == ["today's"]
        assert data["todos"][0]["all_day"] is False
        brief = client.get("/api/v1/dashboard/brief/", **HEADERS).json()
        assert "today's" in brief["markdown"] and "friday's" not in brief["markdown"]
        assert brief["todos"] == 1


@pytest.mark.django_db
def test_a_capture_with_a_bare_date_becomes_an_all_day_item():
    from notes import capture as cap
    from notes.models import QuickCapture

    c = QuickCapture.objects.create(text="todo: review the draft on 2026-10-02")
    made = cap.convert(c, "todo", None, tz="Europe/Berlin")
    todo = TodoItem.objects.get(pk=made["id"])
    assert todo.all_day and made["all_day"]
    assert todo.due_at == datetime(2026, 10, 2, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    assert todo in todos.open_later(today=date(2026, 9, 16))


def test_mcp_client(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mcp_client, "_request", lambda method, path, **kw: seen.update(kw, path=path) or {}
    )
    mcp_client.list_todos(when="later")
    assert seen["path"] == "/todos/" and seen["params"] == {"done": "false", "when": "later"}
    mcp_client.add_todo("Ask Priya", due="monday")
    assert seen["json"] == {"text": "Ask Priya", "due": "monday"}
    mcp_client.snooze_todo(4, "next-week")
    assert seen["path"] == "/todos/4/snooze/" and seen["json"] == {"until": "next-week"}
    mcp_client.snooze_todo(4, "")
    assert seen["json"] == {"until": ""}


def test_mcp_tool_and_toolset():
    from mcp_server import toolsets
    from mcp_server.server import mcp

    names = {t.name for t in mcp._tool_manager.list_tools()}
    assert "snooze_todo" in names
    assert "snooze_todo" in toolsets.AREAS["inbox"][1]
    assert "snooze_todo" not in toolsets.CORE


def test_ui_wiring():
    today = (BASE / "frontend" / "src" / "app" / "pages" / "Today.tsx").read_text()
    for needle in (
        'data-testid="later-section"',
        'data-testid="later-day"',
        'data-testid="later-row"',
        'data-testid="snooze-button"',
        'data-testid="snooze-menu"',
        'data-testid="snooze-date"',
        'data-testid="wake-button"',
        'e.key === "s"',
        "isLater(t.due_at)",
        "“on Friday” a day",
    ):
        assert needle in today, needle
    due = (BASE / "frontend" / "src" / "app" / "dueTime.ts").read_text()
    assert "export function isLater" in due and "export function dayLabel" in due
    assert "!t.all_day" in due  # the nudge skips all-day items
    bar = (BASE / "frontend" / "src" / "app" / "CommandBar.tsx").read_text()
    assert "all_day" in bar and "In Later" in bar
    dash = (BASE / "frontend" / "src" / "app" / "pages" / "Dashboard.tsx").read_text()
    assert "formatDue(t.due_at, t.all_day)" in dash
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "later-section" in chunks and "snooze-menu" in chunks
