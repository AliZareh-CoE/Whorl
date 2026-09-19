"""#567: prompt chains — `Prompt.next` names the step after a prompt; the API refuses a loop;
the gallery offers the next step after a copy with the fill-ins carried over."""

import json
from pathlib import Path

import pytest
from django.conf import settings

from prompts import services
from prompts.models import Prompt

pytestmark = pytest.mark.django_db
BASE = Path(settings.BASE_DIR)
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _chain(*titles):
    rows = [Prompt.objects.create(title=t, body="x") for t in titles]
    for a, b in zip(rows, rows[1:], strict=False):
        a.next = b
        a.save(update_fields=["next"])
    return rows


class TestCycleGuard:
    def test_none_and_a_straight_chain_pass(self):
        a, b, c = _chain("A", "B", "C")
        assert services.chain_would_cycle(a, None) is False
        d = Prompt.objects.create(title="D", body="x")
        assert services.chain_would_cycle(c, d) is False  # A → B → C → D
        assert services.chain_would_cycle(d, a) is False  # D → A → B → C, no loop

    def test_self_two_and_three_cycles_are_caught(self):
        a, b, c = _chain("A", "B", "C")
        assert services.chain_would_cycle(a, a) is True
        assert services.chain_would_cycle(b, a) is True  # B → A → B
        assert services.chain_would_cycle(c, a) is True  # C → A → B → C

    def test_a_chain_longer_than_the_hop_limit_counts_as_a_cycle(self):
        rows = _chain(*[f"P{n}" for n in range(services.CHAIN_HOPS + 2)])
        lone = Prompt.objects.create(title="lone", body="x")
        assert services.chain_would_cycle(lone, rows[0]) is True


class TestApi:
    def test_next_is_set_read_and_cleared(self, client):
        a, b = _chain("A", "B")
        b.next = None
        b.save(update_fields=["next"])
        rows = {r["title"]: r for r in client.get("/api/v1/prompts/", **HEADERS).json()["results"]}
        assert rows["A"]["next"] == b.pk and rows["A"]["next_title"] == "B"
        assert rows["B"]["next"] is None and rows["B"]["next_title"] is None
        r = client.patch(f"/api/v1/prompts/{b.pk}/", json.dumps({"next": None}), **JSON)
        assert r.status_code == 200 and r.json()["next"] is None
        r = client.post(
            "/api/v1/prompts/", json.dumps({"title": "C", "body": "x", "next": a.pk}), **JSON
        )
        assert r.status_code == 201 and r.json()["next_title"] == "A"

    def test_a_loop_is_refused(self, client):
        a, b = _chain("A", "B")
        r = client.patch(f"/api/v1/prompts/{b.pk}/", json.dumps({"next": a.pk}), **JSON)
        assert r.status_code == 400 and "loop" in r.json()["next"][0]
        r = client.patch(f"/api/v1/prompts/{a.pk}/", json.dumps({"next": a.pk}), **JSON)
        assert r.status_code == 400
        a.refresh_from_db()
        assert a.next_id == b.pk  # untouched

    def test_deleting_the_next_step_unlinks(self, client):
        a, b = _chain("A", "B")
        assert client.delete(f"/api/v1/prompts/{b.pk}/", **HEADERS).status_code == 204
        a.refresh_from_db()
        assert a.next_id is None and Prompt.objects.filter(pk=a.pk).exists()

    def test_list_stays_under_the_query_budget(self, client, django_assert_max_num_queries):
        _chain("A", "B", "C", "D", "E", "F")
        with django_assert_max_num_queries(8):
            rows = client.get("/api/v1/prompts/", **HEADERS).json()["results"]
        assert [r["next_title"] for r in rows] == ["B", "C", "D", "E", "F", None]


def test_mcp_docstring_names_the_chain():
    server = (BASE / "mcp_server" / "server.py").read_text()
    assert "follow `next` to the prompt that comes after it in a chain" in server


def test_gallery_offers_the_next_step_and_carries_values_over():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Prompts.tsx").read_text()
    for needle in (
        'data-testid="prompt-next-select"',
        'data-testid="prompt-next"',
        'data-testid="prompt-next-step"',
        "export function carryOver(",
        "handoff && handoff.id === prompt.id",
        "next_title",
    ):
        assert needle in src, needle
    chunk = (BASE / "static" / "js" / "islands" / "Prompts-chunk.js").read_text()
    assert "prompt-next-step" in chunk and "prompt-next-select" in chunk


def test_seed_demo_chains_summarize_to_find_the_gap_once(client_logged_in):
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)
    first = Prompt.objects.get(title="Summarize {{paper}} for {{venue}}")
    gap = Prompt.objects.get(title="Find the gap in {{paper}}")
    assert first.next_id == gap.pk and gap.next_id is None
    other = Prompt.objects.get(title="Reviewer-2 pass")
    first.next = other
    first.save(update_fields=["next"])
    call_command("seed_demo", verbosity=0)
    first.refresh_from_db()
    assert first.next_id == other.pk  # the owner's chain survives a re-seed
