"""The owner's Today list: a plain to-do list that is never lost, over the API and MCP."""

import pytest
from django.urls import reverse

from core.models import TodoItem
from projects.tests.factories import ProjectFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.mark.django_db
def test_add_tick_untick_clear(client, owner):
    r = client.post(
        "/api/v1/todos/", {"text": "Email the lab"}, content_type="application/json", **HEADERS
    )
    assert r.status_code == 201
    first = r.json()
    r = client.post(
        "/api/v1/todos/", {"text": "Skim two papers"}, content_type="application/json", **HEADERS
    )
    second = r.json()
    assert second["position"] > first["position"]  # new items go to the bottom
    done = client.patch(
        f"/api/v1/todos/{first['id']}/", {"done": True}, content_type="application/json", **HEADERS
    ).json()
    assert done["done"] and done["done_at"]
    open_only = client.get("/api/v1/todos/?done=false", **HEADERS).json()["results"]
    assert [t["text"] for t in open_only] == ["Skim two papers"]
    everything = client.get("/api/v1/todos/", **HEADERS).json()["results"]
    assert [t["done"] for t in everything] == [False, True]  # open first, then done
    undone = client.patch(
        f"/api/v1/todos/{first['id']}/", {"done": False}, content_type="application/json", **HEADERS
    ).json()
    assert not undone["done"] and undone["done_at"] is None
    client.patch(
        f"/api/v1/todos/{first['id']}/", {"done": True}, content_type="application/json", **HEADERS
    )
    assert client.post("/api/v1/todos/clear-done/", **HEADERS).json() == {"deleted": 1}
    assert TodoItem.objects.count() == 1


@pytest.mark.django_db
def test_todo_can_be_tagged_with_a_project_and_filtered(client, owner):
    project = ProjectFactory()
    client.post(
        "/api/v1/todos/",
        {"text": "Book scanner", "project": project.slug},
        content_type="application/json",
        **HEADERS,
    )
    client.post(
        "/api/v1/todos/", {"text": "Water plants"}, content_type="application/json", **HEADERS
    )
    rows = client.get(f"/api/v1/todos/?project={project.slug}", **HEADERS).json()["results"]
    assert [t["text"] for t in rows] == ["Book scanner"]
    rows = client.get("/api/v1/todos/?q=plants", **HEADERS).json()["results"]
    assert [t["text"] for t in rows] == ["Water plants"]


@pytest.mark.django_db
def test_model_mark_stamps_done_at():
    item = TodoItem.objects.create(text="x")
    item.mark(True)
    assert item.done and item.done_at is not None
    item.mark(False)
    assert not item.done and item.done_at is None


@pytest.mark.django_db
def test_today_page_is_served_by_the_spa_shell(client, owner):
    client.force_login(owner)
    response = client.get("/today")
    assert response.status_code == 200 and b'id="root"' in response.content


def test_frontend_wiring():
    from pathlib import Path

    from django.conf import settings

    base = Path(settings.BASE_DIR)
    assert 'path="today"' in (base / "frontend" / "src" / "app" / "main.tsx").read_text()
    assert 'to="/today"' in (base / "frontend" / "src" / "app" / "Layout.tsx").read_text()
    page = (base / "frontend" / "src" / "app" / "pages" / "Today.tsx").read_text()
    assert "/todos/clear-done/" in page and "What needs doing?" in page
    chunks = " ".join(
        p.read_text(errors="ignore") for p in (base / "static" / "js" / "islands").glob("Today*.js")
    )
    assert "What needs doing?" in chunks


def test_reverse_of_unrelated_login_still_works():
    assert reverse("login")


def test_palette_offers_todo_verb_and_recent_jumps():
    """Backlog #300/#284: `todo:` in ⌘K adds to the Today list (scoped to the open project);
    the palette remembers the last places it navigated to."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "frontend/src/app/CommandBar.tsx").read_text()
    assert 'startsWith("todo:")' in src
    assert 'api("/todos/"' in src and "project: slug ?? null" in src
    assert "atlas-recent-jumps" in src and "pushJump(" in src
