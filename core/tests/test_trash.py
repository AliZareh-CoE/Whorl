"""#570 (backlog 344): a Trash for Today — a deleted item waits thirty days out of every list
and count, comes back exactly as it was, keeps its chain, and is swept for good after that."""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from core import todos
from core.models import TodoItem
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


class TestManagers:
    def test_the_default_manager_hides_the_trash_everywhere(self):
        project = ProjectFactory()
        live = TodoItem.objects.create(text="live", project=project)
        gone = TodoItem.objects.create(text="gone", project=project, done=True)
        todos.trash(gone)
        assert list(TodoItem.objects.all()) == [live]
        assert set(TodoItem.all_objects.all()) == {live, gone}
        assert list(project.todo_items.all()) == [live]  # reverse relations too
        assert list(todos.open_today()) == [live]
        from core.achievements import gather_facts  # the done count never sees a trashed row

        assert gather_facts()["todos_done"] == 0

    def test_trash_and_restore_keep_the_row_as_it_was(self):
        stamp = timezone.now() - timedelta(hours=3)
        row = TodoItem.objects.create(
            text="x", done=True, done_at=stamp, repeat="weekly", position=4
        )
        before = row.updated_at
        todos.trash(row)
        row.refresh_from_db()
        assert row.deleted_at is not None and row.updated_at > before  # the ETag moves
        todos.restore(row)
        row.refresh_from_db()
        assert row.deleted_at is None
        assert (row.done, row.done_at, row.repeat, row.position) == (True, stamp, "weekly", 4)

    def test_prune_removes_only_what_waited_thirty_days(self):
        old = TodoItem.objects.create(text="old")
        fresh = TodoItem.objects.create(text="fresh")
        todos.trash(old)
        todos.trash(fresh)
        TodoItem.all_objects.filter(pk=old.pk).update(
            deleted_at=timezone.now() - timedelta(days=todos.TRASH_DAYS + 1)
        )  # etag: ok
        assert todos.prune_trash() == 1
        assert set(TodoItem.all_objects.values_list("text", flat=True)) == {"fresh"}


class TestChainInvariant:
    def _parent(self):
        return TodoItem.objects.create(text="agenda", repeat="daily")

    def test_retick_after_trashing_the_successor_spawns_nothing_new(self):
        parent = self._parent()
        first = parent.mark(True)
        assert first is not None and first.repeat_of_id == parent.pk
        todos.trash(first)
        parent.mark(False)  # the untick takes the (trashed, untouched) occurrence back for good
        assert not TodoItem.all_objects.filter(pk=first.pk).exists()
        again = parent.mark(True)
        successors = TodoItem.all_objects.filter(repeat_of=parent, done=False)
        assert successors.count() == 1 and again.pk == successors.get().pk
        assert successors.get().deleted_at is None

    def test_retick_restores_an_edited_successor_from_the_trash(self):
        parent = self._parent()
        first = parent.mark(True)
        first.text = "agenda (edited)"
        first.save(update_fields=["text", "updated_at"])
        todos.trash(first)
        parent.mark(False)  # edited: the owner's now, it stays (in the Trash)
        first.refresh_from_db()
        assert first.deleted_at is not None
        again = parent.mark(True)
        assert again.pk == first.pk  # restored, not duplicated
        first.refresh_from_db()
        assert first.deleted_at is None
        assert TodoItem.all_objects.filter(repeat_of=parent, done=False).count() == 1


class TestApi:
    def test_delete_trashes_and_the_lists_split(self, client):
        row = TodoItem.objects.create(text="probe", done=True, done_at=timezone.now())
        assert client.delete(f"/api/v1/todos/{row.pk}/", **HEADERS).status_code == 204
        row = TodoItem.all_objects.get(pk=row.pk)
        assert row.deleted_at is not None and row.done_at is not None
        live = client.get("/api/v1/todos/?page_size=200", **HEADERS).json()["results"]
        assert all(r["id"] != row.pk for r in live)
        trash = client.get("/api/v1/todos/?trash=true", **HEADERS).json()
        assert [r["id"] for r in trash["results"]] == [row.pk] and trash["results"][0]["deleted_at"]
        assert client.get("/api/v1/todos/?done=true", **HEADERS).json()["count"] == 0

    def test_restore_forever_and_the_guards(self, client):
        row = TodoItem.objects.create(text="probe", position=3)
        client.delete(f"/api/v1/todos/{row.pk}/", **HEADERS)
        r = client.patch(f"/api/v1/todos/{row.pk}/", json.dumps({"done": True}), **JSON)
        assert r.status_code == 409 and "Trash" in r.json()["detail"]
        r = client.post(
            f"/api/v1/todos/{row.pk}/snooze/", json.dumps({"until": "tomorrow"}), **JSON
        )
        assert r.status_code == 409
        r = client.post(f"/api/v1/todos/{row.pk}/restore/", **HEADERS)
        assert r.status_code == 200 and r.json()["deleted_at"] is None and r.json()["position"] == 3
        assert client.post(f"/api/v1/todos/{row.pk}/restore/", **HEADERS).status_code == 200
        assert client.delete(f"/api/v1/todos/{row.pk}/?forever=true", **HEADERS).status_code == 204
        assert not TodoItem.all_objects.filter(pk=row.pk).exists()
        other = TodoItem.objects.create(text="twice")
        client.delete(f"/api/v1/todos/{other.pk}/", **HEADERS)
        assert client.delete(f"/api/v1/todos/{other.pk}/", **HEADERS).status_code == 204  # gone
        assert not TodoItem.all_objects.filter(pk=other.pk).exists()

    def test_clear_done_trashes_and_empty_trash_deletes(self, client):
        TodoItem.objects.create(text="done", done=True, done_at=timezone.now() - timedelta(days=2))
        TodoItem.objects.create(text="open")
        r = client.post("/api/v1/todos/clear-done/", json.dumps({"scope": "earlier"}), **JSON)
        assert r.json() == {"deleted": 1, "trashed": 1}
        assert TodoItem.objects.count() == 1 and TodoItem.all_objects.count() == 2
        r = client.post("/api/v1/todos/empty-trash/", **HEADERS)
        assert r.status_code == 200 and r.json()["deleted"] == 1
        assert TodoItem.all_objects.count() == 1
        assert client.post("/api/v1/todos/empty-trash/").status_code == 401
        assert client.get("/api/v1/todos/?trash=true").status_code == 401

    def test_reorder_never_sees_a_trashed_id(self, client):
        a = TodoItem.objects.create(text="a")
        b = TodoItem.objects.create(text="b")
        todos.trash(b)
        r = client.post("/api/v1/todos/reorder/", json.dumps({"ids": [a.pk, b.pk]}), **JSON)
        assert r.status_code == 400 and "Unknown" in json.dumps(r.json())


class TestSweeps:
    def test_the_huey_task_and_the_desktop_loop_call_the_prune(self):
        from pathlib import Path

        from django.conf import settings

        from core import tasks

        assert tasks.prune_todo_trash_task.func is not None or callable(tasks.prune_todo_trash_task)
        loop = (Path(settings.BASE_DIR) / "core" / "snapshots.py").read_text()
        assert "prune_trash()" in loop and 'log.exception("trash sweep failed")' in loop

    def test_seed_demo_puts_one_row_in_the_trash(self):
        from pathlib import Path

        from django.conf import settings

        src = (Path(settings.BASE_DIR) / "core/management/commands/seed_demo.py").read_text()
        assert (
            "TodoItem.all_objects.get_or_create(" in src
            and '"deleted_at": _tz.now() - _td(days=3)' in src
        )


def test_mcp_client_and_tool():
    from mcp_server import client as c
    from mcp_server import server, toolsets

    names = {t for area in toolsets.AREAS.values() for t in area[1]} | set(toolsets.CORE)
    assert "trash_todo" in names and "get_compile_diagnostics" not in names
    assert not hasattr(c, "get_compile_diagnostics") and callable(c.trash_todo)
    doc = server.trash_todo.__doc__
    assert "thirty days" in doc and "restore" in doc and "forever" in doc
    assert "trash" in server.list_todos.__doc__
