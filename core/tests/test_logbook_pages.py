"""#571: the Logbook is paged and `?page_size=` is honoured — backlog 345.

DRF's stock paginator has `page_size_query_param = None`, so every `?page_size=200` the SPA
sent was ignored and every list was capped at 50 rows (the Report asked for 500 references
and got 50). `AtlasPagination` makes the parameter real, up to 500. The Today page fetches
`when=current` (open items + today's ticks) and pages the Logbook with `when=logbook`."""

from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

from api.pagination import AtlasPagination
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


def test_pagination_class_is_the_default(settings):
    assert settings.REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"] == "api.pagination.AtlasPagination"
    assert AtlasPagination.page_size_query_param == "page_size"
    assert AtlasPagination.max_page_size == 500
    assert AtlasPagination().get_page_size(type("R", (), {"query_params": {}})()) == 50


@pytest.mark.django_db
class TestPageSize:
    def test_page_size_is_honoured_past_fifty(self, client, owner):
        TodoItem.objects.bulk_create([TodoItem(text=f"row {i}", position=i) for i in range(60)])
        body = client.get("/api/v1/todos/?page_size=200", **HEADERS).json()
        assert body["count"] == 60
        assert len(body["results"]) == 60 and body["next"] is None

    def test_default_and_cap(self, client, owner):
        TodoItem.objects.bulk_create([TodoItem(text=f"row {i}", position=i) for i in range(60)])
        default = client.get("/api/v1/todos/", **HEADERS).json()
        assert len(default["results"]) == 50 and default["next"]
        assert len(client.get("/api/v1/todos/?page_size=junk", **HEADERS).json()["results"]) == 50
        # over the cap → the cap (DRF's `cutoff`), not an error
        assert len(client.get("/api/v1/todos/?page_size=9999", **HEADERS).json()["results"]) == 60
        paginator = AtlasPagination()
        request = type("R", (), {"query_params": {"page_size": "9999"}})()
        assert paginator.get_page_size(request) == 500


def _record(days: int):
    now = timezone.now()
    rows = [TodoItem(text="today", position=0, done=True, done_at=now)]
    rows += [
        TodoItem(text=f"day {d}", position=d, done=True, done_at=now - timedelta(days=d))
        for d in range(1, days + 1)
    ]
    rows.append(TodoItem(text="unstamped", position=999, done=True, done_at=None))
    rows.append(TodoItem(text="open", position=1000))
    TodoItem.objects.bulk_create(rows)


@pytest.mark.django_db
class TestWhen:
    def test_logbook_pages_newest_first_with_unstamped_last(self, client, owner):
        _record(60)
        page1 = client.get("/api/v1/todos/?when=logbook", **HEADERS).json()
        assert page1["count"] == 61  # 60 earlier days + the unstamped row; not today, not open
        texts = [t["text"] for t in page1["results"]]
        assert texts[:3] == ["day 1", "day 2", "day 3"] and len(texts) == 50 and page1["next"]
        page2 = client.get("/api/v1/todos/?when=logbook&page=2", **HEADERS).json()
        texts2 = [t["text"] for t in page2["results"]]
        assert texts2 == [f"day {d}" for d in range(51, 61)] + ["unstamped"]
        assert page2["next"] is None

    def test_current_is_everything_but_the_logbook(self, client, owner):
        _record(3)
        body = client.get("/api/v1/todos/?when=current&page_size=500", **HEADERS).json()
        assert sorted(t["text"] for t in body["results"]) == ["open", "today"]

    def test_the_trash_stays_out_of_both(self, client, owner):
        from core.todos import trash

        _record(2)
        trash(TodoItem.objects.get(text="day 1"))
        trash(TodoItem.objects.get(text="open"))
        logbook = client.get("/api/v1/todos/?when=logbook", **HEADERS).json()
        assert [t["text"] for t in logbook["results"]] == ["day 2", "unstamped"]
        current = client.get("/api/v1/todos/?when=current", **HEADERS).json()
        assert [t["text"] for t in current["results"]] == ["today"]


def test_ui_wiring():
    today = (BASE / "frontend" / "src" / "app" / "pages" / "Today.tsx").read_text()
    for needle in (
        'queryKey: ["todos", "current"], queryFn: () => api<Page<Todo>>("/todos/?when=current&page_size=500")',
        'queryKey: ["todos", "logbook"]',
        "`/todos/?when=logbook&page=${pageParam}`",
        'data-testid="logbook-more"',
        "Show older · ${logRemaining} more",
        "Logbook · {logTotal}",
        # a delete from the Logbook keeps its undo: the remove mutation reads both caches
        'getQueryData<InfiniteData<Page<Todo>>>(["todos", "logbook"])',
        "return { gone: [...live, ...log].find((t) => t.id === id) ?? null };",
        "logbookQuery.hasNextPage ? null : ([...logbook].reverse().find((t) => t.done_at)?.done_at ?? null)",
    ):
        assert needle in today, needle
    # every exact-key read/write of the main query moved with it — only the prefix
    # invalidation in refresh() still names ["todos"] alone (it reaches "current",
    # "logbook" and the nudge's "open")
    assert today.count('["todos"]') == 1
    assert today.index("const logbookQuery") < today.index("if (error) return")
    nudge = (BASE / "frontend" / "src" / "app" / "TodoNudge.tsx").read_text()
    assert 'queryKey: ["todos", "open"]' in nudge
    assert '"/todos/?done=false&page_size=500"' in nudge
    # every other page that asks for more than fifty rows now gets them — nothing to change there
    report = (BASE / "frontend" / "src" / "app" / "pages" / "Report.tsx").read_text()
    assert "page_size=500" in report
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "logbook-more" in chunks and "when=current" in chunks
