"""#564: "Use a prompt with this…" — `GET /prompts/?kind=reference` lists the prompts that take
a paper (note / project / manuscript likewise), MCP `list_prompts(kind=…)` sends it, and the
gallery reads `/prompts?use=<kind>:<id>&label=` from the paper / note / manuscript pages."""

from pathlib import Path

import pytest
from django.conf import settings

from mcp_server import client as mcp_client
from prompts.models import Prompt

pytestmark = pytest.mark.django_db
BASE = Path(settings.BASE_DIR)
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _titles(client, **params):
    return [r["title"] for r in client.get("/api/v1/prompts/", params, **HEADERS).json()["results"]]


class TestKindFilter:
    def test_lists_the_prompts_that_take_the_kind(self, client):
        Prompt.objects.create(title="A paper", body="Summarize {{paper:reference}}")
        Prompt.objects.create(title="A note", body="Tighten {{note:note}} please")
        Prompt.objects.create(
            title="Second position", body="{{venue|X}} then {{p : reference | Y}}"
        )
        Prompt.objects.create(title="Plain", body="No fill-ins")
        Prompt.objects.create(title="Text only", body="{{topic}} and {{venue|NeurIPS}}")
        assert _titles(client, kind="reference") == ["A paper", "Second position"]
        assert _titles(client, kind="note") == ["A note"]
        assert _titles(client, kind="manuscript") == []

    def test_junk_kind_is_ignored(self, client):
        Prompt.objects.create(title="A paper", body="Summarize {{paper:reference}}")
        Prompt.objects.create(title="Plain", body="No fill-ins")
        for junk in ("text", "reference|note", ".*", "{{", "REFERENCE)"):
            assert len(_titles(client, kind=junk)) == 2, junk
        assert _titles(client, kind="Reference") == ["A paper"]  # case-insensitive
        assert _titles(client, kind="reference", q="paper") == ["A paper"]  # composes with q


def test_mcp_list_prompts_sends_the_kind(monkeypatch):
    calls = []
    monkeypatch.setattr(mcp_client, "_request", lambda m, p, **kw: calls.append((m, p, kw)) or {})
    mcp_client.list_prompts()
    mcp_client.list_prompts("review")
    mcp_client.list_prompts(kind="reference")
    mcp_client.list_prompts("x", "note")
    assert calls == [
        ("GET", "/prompts/", {"params": None}),
        ("GET", "/prompts/", {"params": {"q": "review"}}),
        ("GET", "/prompts/", {"params": {"kind": "reference"}}),
        ("GET", "/prompts/", {"params": {"q": "x", "kind": "note"}}),
    ]
    server = (BASE / "mcp_server" / "server.py").read_text()
    assert 'def list_prompts(query: str = "", kind: str = "") -> dict:' in server


def test_gallery_reads_the_use_address_and_every_page_offers_it():
    pages = BASE / "frontend" / "src" / "app" / "pages"
    gallery = (pages / "Prompts.tsx").read_text()
    for needle in (
        "useSearchParams",
        "parseUse(",
        'data-testid="prompt-use-banner"',
        "v.kind === use.kind",
    ):
        assert needle in gallery, needle
    assert "Use a prompt with this paper…" in (pages / "Reference.tsx").read_text()
    assert "Use a prompt with this paper…" in (pages / "Library.tsx").read_text()
    assert "Use a prompt with this manuscript…" in (pages / "Writing.tsx").read_text()
    assert 'data-testid="note-use-prompt"' in (pages / "Notes.tsx").read_text()
    assert "use=note:${id}" in (pages / "Notes.tsx").read_text()
    # #566: the remaining entry points — the project overview menu, the Library pane, the Studio
    overview = (pages / "ProjectOverview.tsx").read_text()
    assert "Use a prompt with this project…" in overview and "use=project:${project.id}" in overview
    assert "project: { id: number;" in overview  # the payload's id, typed
    assert 'data-testid="pane-use-prompt"' in (pages / "Library.tsx").read_text()
    studio = (pages / "Studio.tsx").read_text()
    assert "Use a prompt with this manuscript…" in studio and "useNavigate" in studio
    assert "void saveAll().then(() => navigate(`/prompts?use=manuscript:${m.id}" in studio
    chunk = (BASE / "static" / "js" / "islands" / "Prompts-chunk.js").read_text()
    assert "prompt-use-banner" in chunk


def test_seed_demo_has_a_prompt_per_kind(client_logged_in):
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)
    bodies = " ".join(Prompt.objects.values_list("body", flat=True))
    for kind in ("reference", "note", "manuscript", "project"):
        assert f":{kind}}}}}" in bodies, kind
