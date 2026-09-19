"""#565: a prompt's history — every copy files a `PromptUse` row (what it was filled with: ids
and labels, never the rendered text), the last 50 kept; `last_use` on the serializer, `GET
/prompts/{id}/uses/`, MCP `get_prompt(history=True)`, the gallery's History panel."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

from literature.models import Reference
from mcp_server import client as mcp_client
from prompts import services
from prompts.models import Prompt, PromptUse

pytestmark = pytest.mark.django_db
BASE = Path(settings.BASE_DIR)
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _paper():
    return Reference.objects.create(
        title="Attention under load", bibtex_key="theeuwes2012", year=2012, authors=[]
    )


class TestRecordUse:
    def test_files_a_row_with_the_resolved_variables(self):
        prompt = Prompt.objects.create(title="P", body="{{paper:reference}} for {{venue|X}}")
        ref = _paper()
        rendered = services.render_with_data(prompt, {"paper": ref.pk})
        use = services.record_use(prompt, rendered["variables"])
        assert PromptUse.objects.filter(prompt=prompt).count() == 1
        assert use.variables[0] == {
            "name": "paper",
            "kind": "reference",
            "default": "",
            "value": str(ref.pk),
            "label": "Attention under load",
        }
        assert use.variables[1]["value"] == "" and use.variables[1]["default"] == "X"
        assert "Attention" not in json.dumps(use.variables[1])  # no rendered text stored

    def test_bare_call_files_an_empty_row_and_keeps_updated_at(self):
        prompt = Prompt.objects.create(title="P", body="x")
        Prompt.objects.filter(pk=prompt.pk).update(  # etag: ok — a fixture, an old edit
            updated_at=timezone.now() - timedelta(days=3)
        )
        prompt.refresh_from_db()
        edited = prompt.updated_at
        services.record_use(prompt)
        prompt.refresh_from_db()
        assert prompt.uses.count() == 1 and prompt.uses.first().variables == []
        assert prompt.updated_at == edited

    def test_keeps_the_last_fifty(self):
        prompt = Prompt.objects.create(title="P", body="{{topic}}")
        for n in range(53):
            services.record_use(prompt, [{"name": "topic", "kind": "text", "value": str(n)}])
        assert prompt.uses.count() == services.KEEP_USES == 50
        assert prompt.uses.first().variables[0]["value"] == "52"
        prompt.refresh_from_db()
        assert prompt.use_count == 53  # the count stays all-time

    def test_stored_values_are_capped_and_junk_is_dropped(self):
        prompt = Prompt.objects.create(title="P", body="{{topic}}")
        use = services.record_use(
            prompt, [{"name": "topic", "kind": "text", "value": "x" * 1000}, "junk", 3]
        )
        assert len(use.variables) == 1 and len(use.variables[0]["value"]) == services.STORED_CAP


class TestApi:
    def test_render_files_a_use_and_the_list_carries_the_newest(
        self, client, django_assert_max_num_queries
    ):
        prompt = Prompt.objects.create(title="P", body="{{paper:reference}} / {{venue|X}}")
        ref = _paper()
        assert client.get(f"/api/v1/prompts/{prompt.pk}/", **HEADERS).json()["last_use"] is None
        r = client.post(
            f"/api/v1/prompts/{prompt.pk}/render/",
            json.dumps({"values": {"paper": ref.pk, "venue": "ICLR"}}),
            **JSON,
        )
        assert r.status_code == 200
        use = r.json()["use"]
        assert use["variables"][0]["label"] == "Attention under load"
        assert use["variables"][1]["value"] == "ICLR"
        client.post(f"/api/v1/prompts/{prompt.pk}/render/", json.dumps({}), **JSON)
        for n in range(6):
            Prompt.objects.create(title=f"Other {n}", body="x")
        with django_assert_max_num_queries(8):
            rows = client.get("/api/v1/prompts/", **HEADERS).json()["results"]
        mine = next(p for p in rows if p["id"] == prompt.pk)
        assert mine["last_use"]["variables"][1]["value"] == ""  # the newest: defaults
        assert mine["last_use"]["id"] > use["id"]
        assert all(p["last_use"] is None for p in rows if p["id"] != prompt.pk)

    def test_uses_endpoint_lists_newest_first(self, client):
        prompt = Prompt.objects.create(title="P", body="{{topic}}")
        for n in range(3):
            services.record_use(prompt, [{"name": "topic", "kind": "text", "value": str(n)}])
        assert client.get(f"/api/v1/prompts/{prompt.pk}/uses/").status_code == 401
        out = client.get(f"/api/v1/prompts/{prompt.pk}/uses/", **HEADERS).json()["uses"]
        assert [u["variables"][0]["value"] for u in out] == ["2", "1", "0"]
        assert set(out[0]) == {"id", "created_at", "variables"}

    def test_failed_render_files_nothing(self, client):
        prompt = Prompt.objects.create(title="P", body="{{paper:reference}}")
        client.post(
            f"/api/v1/prompts/{prompt.pk}/render/",
            json.dumps({"values": {"paper": 999999}}),
            **JSON,
        )
        assert prompt.uses.count() == 0


def test_mcp_get_prompt_history(monkeypatch):
    calls = []

    def fake(method, path, **kw):
        calls.append((method, path))
        if path.endswith("/uses/"):
            return {"uses": [{"id": 1, "created_at": "t", "variables": []}]}
        return {"id": 3, "last_use": None} if method == "GET" else {"text": "T", "use": {}}

    monkeypatch.setattr(mcp_client, "_request", fake)
    assert "uses" not in mcp_client.get_prompt(3)
    out = mcp_client.get_prompt(3, history=True)
    assert out["uses"][0]["id"] == 1 and calls[-1] == ("GET", "/prompts/3/uses/")
    server = (BASE / "mcp_server" / "server.py").read_text()
    assert (
        "def get_prompt(prompt_id: int, values: dict | None = None, history: bool = False) -> dict:"
        in server
    )


def test_gallery_shows_the_history_and_refills_from_it():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Prompts.tsx").read_text()
    for needle in (
        'data-testid="prompt-last-use"',
        'data-testid="prompt-history"',
        'data-testid="prompt-use-again"',
        "/uses/`",
        "valuesFromUse(",
        "last_use: r.use",
    ):
        assert needle in src, needle
    chunk = (BASE / "static" / "js" / "islands" / "Prompts-chunk.js").read_text()
    assert "prompt-history" in chunk and "prompt-use-again" in chunk


def test_seed_demo_files_a_history_once(client_logged_in):
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)
    used = Prompt.objects.filter(use_count__gt=0)
    assert used.count() == 2
    counts = {p.title: p.uses.count() for p in used}
    assert all(c == 3 for c in counts.values()), counts
    top = used.order_by("-use_count").first()
    first = top.uses.first()
    paper = next(v for v in first.variables if v["kind"] == "reference")
    assert paper["value"].isdigit() and paper["label"]  # a real demo paper, by id + title
    call_command("seed_demo", verbosity=0)
    assert PromptUse.objects.count() == 6  # no duplicates on a re-seed
