"""#547: repeating Today items — "prep the agenda every Monday". Ticking an occurrence spawns
the next one (the done row stays in Done); one open occurrence per chain at any time."""

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


class TestAdvance:
    def test_daily_weekly_monthly(self):
        assert todos.advance(date(2026, 9, 16), "daily") == date(2026, 9, 17)
        assert todos.advance(date(2026, 9, 16), "weekly") == date(2026, 9, 23)
        assert todos.advance(date(2026, 8, 31), "monthly") == date(2026, 9, 30)  # clamped
        assert todos.advance(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
        assert todos.advance(date(2026, 12, 3), "monthly") == date(2027, 1, 3)  # year rolls

    def test_weekdays_skip_the_weekend(self):
        assert todos.advance(date(2026, 9, 17), "weekdays") == date(2026, 9, 18)  # Thu → Fri
        assert todos.advance(date(2026, 9, 18), "weekdays") == date(2026, 9, 21)  # Fri → Mon
        assert todos.advance(date(2026, 9, 19), "weekdays") == date(2026, 9, 21)  # Sat → Mon
        assert todos.advance(date(2026, 9, 20), "weekdays") == date(2026, 9, 21)  # Sun → Mon

    def test_unknown_rule(self):
        with pytest.raises(ValueError):
            todos.advance(date(2026, 9, 16), "fortnightly")


@pytest.mark.django_db
class TestNextDue:
    def test_all_day_advances_from_its_own_day_and_past_today(self):
        today = date(2026, 9, 16)
        item = TodoItem(text="x", repeat="weekly", due_at=at(date(2026, 9, 14)), all_day=True)
        assert todos.next_due(item, today) == at(date(2026, 9, 21))  # Mondays; the coming one
        behind = TodoItem(text="x", repeat="weekly", due_at=at(date(2026, 8, 24)), all_day=True)
        assert todos.next_due(behind, today) == at(date(2026, 9, 21))  # not three stale ones

    def test_timed_keeps_its_clock_time(self):
        today = date(2026, 9, 16)
        item = TodoItem(text="x", repeat="daily", due_at=at(today, 15, 30))
        assert todos.next_due(item, today) == at(date(2026, 9, 17), 15, 30)

    def test_undated_counts_from_today(self):
        today = date(2026, 9, 16)  # Wednesday
        item = TodoItem(text="x", repeat="daily")
        assert todos.next_due(item, today) == at(date(2026, 9, 17))
        item = TodoItem(text="x", repeat="weekdays")
        assert todos.next_due(item, today) == at(date(2026, 9, 17))

    def test_snoozing_moves_the_chain(self):
        # the weekly anchor is the occurrence's own weekday: Monday's item snoozed to Tuesday
        # repeats on Tuesdays from then on
        today = date(2026, 9, 16)
        item = TodoItem(text="x", repeat="weekly", due_at=at(date(2026, 9, 15)), all_day=True)
        assert todos.next_due(item, today).date().weekday() == 1


@pytest.mark.django_db
class TestSpawn:
    def test_tick_spawns_once_untick_takes_it_back(self):
        today = timezone.localdate()
        item = TodoItem.objects.create(
            text="Prep the agenda", position=1, repeat="weekly", due_at=at(today), all_day=True
        )
        spawned = item.mark(True)
        assert spawned is not None and spawned.repeat_of == item and not spawned.done
        assert spawned.text == item.text and spawned.repeat == "weekly" and spawned.all_day
        assert spawned.due_at == at(today + timedelta(days=7))
        assert spawned.position == 2 and spawned in todos.open_later()
        assert item.mark(True) is None  # already done: nothing happens
        item.done = False
        item.save()
        assert todos.spawn_next(item) == spawned  # an open successor is never doubled
        item.done = True
        item.save()
        assert item.mark(False) is None
        assert not TodoItem.objects.filter(pk=spawned.pk).exists()  # untick took it back

    def test_untick_keeps_an_edited_or_ticked_successor(self):
        today = timezone.localdate()
        item = TodoItem.objects.create(text="x", position=1, repeat="daily")
        spawned = item.mark(True)
        spawned.text = "x (edited)"
        spawned.save()
        item.mark(False)
        assert TodoItem.objects.filter(pk=spawned.pk).exists()
        item.mark(True)  # spawns again since the edited one no longer matches? no — open successor
        assert item.repeats.filter(done=False).count() == 1
        second = TodoItem.objects.create(text="y", position=3, repeat="daily", due_at=at(today))
        s2 = second.mark(True)
        s2.mark(True)  # the successor itself ticked (spawning a third)
        second.mark(False)
        assert TodoItem.objects.filter(pk=s2.pk).exists()

    def test_plain_items_never_spawn(self):
        item = TodoItem.objects.create(text="x", position=1)
        assert item.mark(True) is None and TodoItem.objects.count() == 1

    def test_clear_done_keeps_the_successor(self, client, owner):
        item = TodoItem.objects.create(text="x", position=1, repeat="daily")
        spawned = item.mark(True)
        assert client.post("/api/v1/todos/clear-done/", **HEADERS).json() == {"deleted": 1}
        spawned.refresh_from_db()
        assert spawned.repeat_of is None and not spawned.done

    def test_labels(self):
        assert todos.repeat_label(TodoItem(text="x")) == ""
        assert todos.repeat_label(TodoItem(text="x", repeat="daily")) == "every day"
        assert todos.repeat_label(TodoItem(text="x", repeat="weekdays")) == "every weekday"
        monday = TodoItem(text="x", repeat="weekly", due_at=at(date(2026, 9, 21)), all_day=True)
        assert todos.repeat_label(monday) == "every Monday"
        third = TodoItem(text="x", repeat="monthly", due_at=at(date(2026, 10, 3)), all_day=True)
        assert todos.repeat_label(third) == "monthly on the 3rd"
        assert (
            todos._ordinal(11) == "th" and todos._ordinal(22) == "nd" and todos._ordinal(1) == "st"
        )


@pytest.mark.django_db
class TestApi:
    def test_create_tick_and_next(self, client, owner):
        today = timezone.localdate()
        r = client.post(
            "/api/v1/todos/",
            {"text": "Prep the agenda", "due": "monday", "repeat": "weekly"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 201
        row = r.json()
        assert row["repeat"] == "weekly" and row["repeat_label"] == "every Monday"
        assert row["repeat_of"] is None and row["next"] is None
        r = client.patch(
            f"/api/v1/todos/{row['id']}/",
            {"done": True},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 200 and r.json()["done"]
        nxt = r.json()["next"]
        assert nxt and nxt["due_at"] > row["due_at"]
        successor = client.get(f"/api/v1/todos/{nxt['id']}/", **HEADERS).json()
        assert successor["repeat_of"] == row["id"] and successor["repeat"] == "weekly"
        assert client.get("/api/v1/todos/?when=later", **HEADERS).json()["count"] == 1
        r = client.patch(
            f"/api/v1/todos/{row['id']}/",
            {"done": False},
            content_type="application/json",
            **HEADERS,
        )
        assert r.json()["next"] is None
        assert client.get(f"/api/v1/todos/{nxt['id']}/", **HEADERS).status_code == 404
        # a weekly rule with no day counts from today, all-day
        r = client.post(
            "/api/v1/todos/",
            {"text": "Water the plants", "repeat": "weekly"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.json()["all_day"] and r.json()["due_at"] == today.isoformat() + "T12:00:00Z"
        r = client.post(
            "/api/v1/todos/",
            {"text": "Bad", "repeat": "fortnightly"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 400 and "repeat" in r.json()

    def test_patch_repeat_on_an_existing_item(self, client, owner):
        item = TodoItem.objects.create(text="x", position=1)
        r = client.patch(
            f"/api/v1/todos/{item.id}/",
            {"repeat": "monthly"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.json()["repeat"] == "monthly" and r.json()["all_day"]  # anchored today
        r = client.patch(
            f"/api/v1/todos/{item.id}/",
            {"repeat": ""},
            content_type="application/json",
            **HEADERS,
        )
        assert r.json()["repeat"] == "" and r.json()["repeat_label"] == ""


def test_mcp_client(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mcp_client, "_request", lambda method, path, **kw: seen.update(kw, path=path) or {}
    )
    mcp_client.add_todo("Prep the agenda", due="monday", repeat="weekly")
    assert seen["json"] == {"text": "Prep the agenda", "due": "monday", "repeat": "weekly"}
    mcp_client.add_todo("Plain")
    assert seen["json"] == {"text": "Plain"}


def test_ui_wiring():
    today = (BASE / "frontend" / "src" / "app" / "pages" / "Today.tsx").read_text()
    for needle in (
        'data-testid="repeat-chip"',
        'data-testid="repeat-row"',
        'data-testid="repeat-option"',
        "setRepeat",
        "“every Monday” a rule",
    ):
        assert needle in today, needle
    due = (BASE / "frontend" / "src" / "app" / "dueTime.ts").read_text()
    assert "const EVERY" in due and "export function repeatLabel" in due
    assert due.index("EVERY.exec(text)") < due.index("parseDay(text, now)")  # rule before day
    bar = (BASE / "frontend" / "src" / "app" / "CommandBar.tsx").read_text()
    assert "repeat, project: slug" in bar
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "repeat-chip" in chunks and "repeat-row" in chunks
