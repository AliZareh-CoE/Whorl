"""#550: the Done section as a logbook — today's ticks stay in view, earlier days fold into a
Logbook grouped by day, and clearing empties the Logbook without erasing today's record."""

from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

from core import todos
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


def _rows():
    now = timezone.now()
    today = TodoItem.objects.create(text="today", position=1, done=True, done_at=now)
    yesterday = TodoItem.objects.create(
        text="yesterday", position=2, done=True, done_at=now - timedelta(days=1)
    )
    unstamped = TodoItem.objects.create(text="unstamped", position=3, done=True)  # an undo
    open_row = TodoItem.objects.create(text="open", position=4)
    return today, yesterday, unstamped, open_row


@pytest.mark.django_db
def test_boundaries():
    today, yesterday, unstamped, open_row = _rows()
    assert list(TodoItem.objects.filter(todos.done_today_q())) == [today]
    assert set(TodoItem.objects.filter(todos.logbook_q())) == {yesterday, unstamped}
    assert open_row not in TodoItem.objects.filter(todos.logbook_q())
    # the two boundaries and the open list partition the table
    assert TodoItem.objects.filter(todos.today_q()).count() == 1


@pytest.mark.django_db
class TestClear:
    def test_default_clears_every_done_row(self, client, owner):
        _rows()
        assert client.post("/api/v1/todos/clear-done/", **HEADERS).json() == {"deleted": 3}
        assert TodoItem.objects.filter(done=True).count() == 0

    def test_earlier_keeps_today(self, client, owner):
        today, *_ = _rows()
        r = client.post(
            "/api/v1/todos/clear-done/",
            {"scope": "earlier"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.json() == {"deleted": 2}
        assert list(TodoItem.objects.filter(done=True)) == [today]
        assert TodoItem.objects.filter(done=False).count() == 1

    def test_junk_scope(self, client, owner):
        r = client.post(
            "/api/v1/todos/clear-done/",
            {"scope": "yesterday"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 400 and "scope" in r.json()


def test_ui_wiring():
    today = (BASE / "frontend" / "src" / "app" / "pages" / "Today.tsx").read_text()
    for needle in (
        'data-testid="done-today"',
        'data-testid="done-today-count"',
        'data-testid="logbook-toggle"',
        'data-testid="logbook-day"',
        'data-testid="logbook-row"',
        'data-testid="logbook-locked"',
        'data-testid="clear-logbook"',
        'JSON.stringify({ scope: "earlier" })',
        'localStorage.getItem("atlas-today-logbook")',
        "const canUntick = !t.repeat;",
        'dayLabel(t.done_at) === "today"',
    ):
        assert needle in today, needle
    # the toggle's state hook sits above the error return (React #310 otherwise)
    assert today.index("const [logbookOpen") < today.index("if (error) return")
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "logbook-toggle" in chunks and "clear-logbook" in chunks
