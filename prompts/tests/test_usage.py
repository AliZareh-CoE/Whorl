"""#563: a prompt remembers how often and when last it was copied — `record_use` after a
successful render, `use_count` / `last_used_at` on the API, the gallery's Recent strip."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from prompts import services
from prompts.models import Prompt

pytestmark = pytest.mark.django_db
BASE = Path(__file__).resolve().parents[2]
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


class TestRecordUse:
    def test_increments_and_stamps_without_touching_updated_at(self):
        prompt = Prompt.objects.create(title="P", body="Hello {{who|world}}")
        Prompt.objects.filter(pk=prompt.pk).update(  # etag: ok — a fixture, an old edit
            updated_at=timezone.now() - timedelta(days=3)
        )
        prompt.refresh_from_db()
        edited = prompt.updated_at
        assert prompt.use_count == 0 and prompt.last_used_at is None
        services.record_use(prompt)
        services.record_use(prompt)
        prompt.refresh_from_db()
        assert prompt.use_count == 2
        assert prompt.last_used_at is not None
        assert timezone.now() - prompt.last_used_at < timedelta(seconds=5)
        assert prompt.updated_at == edited  # "used" is not "edited"

    def test_returns_the_fresh_row(self):
        prompt = Prompt.objects.create(title="P", body="x")
        out = services.record_use(prompt)
        assert out.use_count == 1 and isinstance(out.use_count, int)


class TestApi:
    def test_render_counts_a_use_and_carries_it_back(self, client):
        prompt = Prompt.objects.create(title="P", body="Hello {{who|world}}")
        url = f"/api/v1/prompts/{prompt.pk}/render/"
        r = client.post(url, json.dumps({}), **JSON)
        assert r.status_code == 200
        assert r.json()["text"] == "Hello world"
        assert r.json()["use_count"] == 1 and r.json()["last_used_at"]
        r = client.post(url, json.dumps({"values": {"who": "Ali"}}), **JSON)
        assert r.json()["use_count"] == 2
        detail = client.get(f"/api/v1/prompts/{prompt.pk}/", **HEADERS).json()
        assert detail["use_count"] == 2 and detail["last_used_at"]
        rows = client.get("/api/v1/prompts/", **HEADERS).json()["results"]
        assert rows[0]["use_count"] == 2

    def test_failed_render_does_not_count(self, client):
        prompt = Prompt.objects.create(title="P", body="{{paper:reference}}")
        url = f"/api/v1/prompts/{prompt.pk}/render/"
        assert (
            client.post(url, json.dumps({"values": {"paper": 999999}}), **JSON).status_code == 404
        )
        assert client.post(url, json.dumps({"values": [1]}), **JSON).status_code == 400
        prompt.refresh_from_db()
        assert prompt.use_count == 0 and prompt.last_used_at is None

    def test_usage_is_read_only_on_write(self, client):
        r = client.post(
            "/api/v1/prompts/",
            json.dumps({"title": "New", "body": "x", "use_count": 40}),
            **JSON,
        )
        assert r.status_code == 201 and r.json()["use_count"] == 0
        r = client.patch(f"/api/v1/prompts/{r.json()['id']}/", json.dumps({"use_count": 9}), **JSON)
        assert r.status_code == 200 and r.json()["use_count"] == 0


def test_gallery_has_a_recent_strip_and_use_chips():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Prompts.tsx").read_text()
    for needle in (
        'data-testid="prompt-recent"',
        'data-testid="prompt-uses"',
        "last_used_at",
        "use_count",
    ):
        assert needle in src, needle
    chunk = (BASE / "static" / "js" / "islands" / "Prompts-chunk.js").read_text()
    assert "prompt-recent" in chunk and "prompt-uses" in chunk


def test_seed_demo_gives_the_recent_strip_something_to_show(client_logged_in):
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)
    used = Prompt.objects.filter(use_count__gt=0)
    assert used.count() == 2 and all(p.last_used_at for p in used)
    # a re-seed keeps real usage: bump one, seed again, the bump survives
    top = used.order_by("-use_count").first()
    services.record_use(top)
    call_command("seed_demo", verbosity=0)
    top.refresh_from_db()
    assert top.use_count == 13
