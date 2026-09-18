"""#562: typed prompt variables — `{{paper:reference}}` is picked from the library and expands
to the paper at copy time; notes, projects and manuscripts likewise; `POST /prompts/{id}/render/`
and `get_prompt(values)` render through one service; the gallery draws pickers."""

import json
from pathlib import Path

import pytest
from django.conf import settings

from literature.models import Reference
from mcp_server import client as mcp_client
from notes.models import Note
from projects.tests.factories import ProjectFactory
from prompts import services
from prompts.models import Prompt, parse_variables, render_prompt
from writing.models import Manuscript

pytestmark = pytest.mark.django_db

BASE = Path(settings.BASE_DIR)
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def test_parse_reads_the_kind_and_keeps_old_syntax():
    rows = parse_variables(
        "{{paper:reference}} for {{venue|NeurIPS}} by {{who : Note | Ali}} {{x:bogus}} {{paper}}"
    )
    assert rows == [
        {"name": "paper", "kind": "reference", "default": ""},
        {"name": "venue", "kind": "text", "default": "NeurIPS"},
        {"name": "who", "kind": "note", "default": "Ali"},
        {"name": "x", "kind": "text", "default": ""},
    ]
    # a later occurrence that names the kind speaks for the bare one before it
    assert parse_variables("{{p}} then {{p:project}}")[0]["kind"] == "project"
    assert render_prompt("{{paper:reference}} {{venue|X}}", {"paper": "T"}) == "T X"
    assert render_prompt("{{paper:reference}}") == "{{paper}}"


def _paper():
    return Reference.objects.create(
        bibtex_key="lavie2010",
        title="Attention under load",
        authors=[{"given": "Nilli", "family": "Lavie"}, {"given": "A", "family": "Beck"}],
        year=2010,
        venue="Trends in Cognitive Sciences",
        doi="10.1000/xyz",
        abstract="Perceptual load determines distractor processing.",
    )


class TestExpansion:
    def test_reference_expands_to_a_citation_block(self):
        ref = _paper()
        text, label = services.expand_value("reference", ref.pk, "paper")
        assert text == (
            "Attention under load (Nilli Lavie, A Beck, 2010).\n"
            "Trends in Cognitive Sciences.\n"
            "doi:10.1000/xyz\n"
            "Abstract: Perceptual load determines distractor processing."
        )
        assert label == "Attention under load"
        bare = Reference.objects.create(bibtex_key="k2", title="Bare")
        assert services.expand_value("reference", bare.pk) == ("Bare.", "Bare")

    def test_note_project_manuscript_and_text(self):
        project = ProjectFactory(name="Deep work", description="Focus study")
        note = Note.objects.create(project=project, title="Pilot", body="# Pilot\nran 7")
        ms = Manuscript.objects.create(project=project, title="Paper A", abstract="We show…")
        assert services.expand_value("note", str(note.pk)) == ("Pilot\n\n# Pilot\nran 7", "Pilot")
        assert services.expand_value("project", project.pk) == (
            "Deep work\n\nFocus study",
            "Deep work",
        )
        assert services.expand_value("manuscript", ms.pk) == ("Paper A\n\nWe show…", "Paper A")
        # a non-numeric value on a typed variable is used as typed; text is always as typed
        assert services.expand_value("reference", "Smith 2020") == ("Smith 2020", "Smith 2020")
        assert services.expand_value("text", "12") == ("12", "12")
        assert services.expand_value("note", "") == ("", "")
        assert services.expand_value("note", 10**9) == (None, None)
        with pytest.raises(services.PromptError):
            services.expand_value("note", 2**40)

    def test_render_with_data(self):
        ref = _paper()
        prompt = Prompt.objects.create(
            title="Sum", body="Summarize for {{venue|NeurIPS}}:\n{{paper:reference}} {{extra}}"
        )
        out = services.render_with_data(prompt, {"paper": ref.pk})
        assert out["text"].startswith("Summarize for NeurIPS:\nAttention under load (")
        assert out["text"].endswith("{{extra}}")
        assert [v["name"] for v in out["variables"]] == ["venue", "paper", "extra"]
        assert out["variables"][1] == {
            "name": "paper",
            "kind": "reference",
            "default": "",
            "value": str(ref.pk),
            "label": "Attention under load",
        }
        assert services.render_with_data(prompt, None)["text"].endswith("{{paper}} {{extra}}")
        with pytest.raises(services.PromptError, match="No reference with id 999999"):
            services.render_with_data(prompt, {"paper": 999999})
        with pytest.raises(services.PromptError, match="must be an object"):
            services.render_with_data(prompt, [1])

    def test_expansion_is_capped(self):
        project = ProjectFactory()
        note = Note.objects.create(project=project, title="Big", body="x" * 60_000)
        prompt = Prompt.objects.create(title="N", body="{{n:note}}")
        text = services.render_with_data(prompt, {"n": note.pk})["text"]
        assert len(text) == services.EXPANSION_CAP


class TestApi:
    def test_render_endpoint(self, client):
        ref = _paper()
        prompt = Prompt.objects.create(title="Sum", body="{{paper:reference}} / {{venue|X}}")
        url = f"/api/v1/prompts/{prompt.pk}/render/"
        r = client.post(url, json.dumps({"values": {"paper": ref.pk}}), **JSON)
        assert r.status_code == 200
        assert r.json()["text"].startswith("Attention under load (") and "/ X" in r.json()["text"]
        assert r.json()["variables"][0]["label"] == "Attention under load"
        assert client.post(url, json.dumps({}), **JSON).json()["text"] == "{{paper}} / X"
        assert (
            client.post(url, json.dumps({"values": {"paper": 999999}}), **JSON).status_code == 404
        )
        assert client.post(url, json.dumps({"values": [1]}), **JSON).status_code == 400
        assert client.post(url, "{}", content_type="application/json").status_code == 401
        detail = client.get(f"/api/v1/prompts/{prompt.pk}/", **HEADERS).json()
        assert detail["variables"][0] == {"name": "paper", "kind": "reference", "default": ""}


def test_mcp_get_prompt_renders_with_values(monkeypatch):
    calls = []

    def fake(method, path, **kw):
        calls.append((method, path, kw))
        if method == "GET":
            return {"id": 3, "title": "Sum", "body": "{{paper:reference}}"}
        return {"text": "Attention under load (…)", "variables": []}

    monkeypatch.setattr(mcp_client, "_request", fake)
    assert mcp_client.get_prompt(3) == {"id": 3, "title": "Sum", "body": "{{paper:reference}}"}
    assert calls == [("GET", "/prompts/3/", {})]
    out = mcp_client.get_prompt(3, {"paper": 1})
    assert out["text"].startswith("Attention") and out["title"] == "Sum"
    assert calls[-1] == ("POST", "/prompts/3/render/", {"json": {"values": {"paper": 1}}})
    server = (BASE / "mcp_server" / "server.py").read_text()
    assert "def get_prompt(prompt_id: int, values: dict | None = None) -> dict:" in server


def test_gallery_draws_pickers_and_copies_through_render():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Prompts.tsx").read_text()
    for needle in (
        'data-testid="prompt-pick"',
        'data-testid="prompt-var"',
        "/render/`",
        "/search/?q=",
        "kind: Kind",
        "match[3]",  # the default moved to the third group with the kind in the second
    ):
        assert needle in src, needle
    chunk = (BASE / "static" / "js" / "islands" / "Prompts-chunk.js").read_text()
    assert "prompt-pick" in chunk
