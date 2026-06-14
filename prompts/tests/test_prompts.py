import pytest
from django.urls import reverse

from prompts.models import Prompt

pytestmark = pytest.mark.django_db


def make_prompts():
    Prompt.objects.create(title="Summarize paper", body="Summarize…", tags="lit-review, summarize")
    Prompt.objects.create(title="Reviewer 2 pass", body="Act as reviewer…", tags="writing")


class TestGallery:
    def test_gallery_lists_and_has_copy_buttons(self, client_logged_in):
        make_prompts()
        response = client_logged_in.get(reverse("prompts:gallery"))
        content = response.content.decode()
        assert "Summarize paper" in content
        assert "Reviewer 2 pass" in content
        assert 'data-copy-target="prompt-body-' in content

    def test_gallery_shows_count(self, client_logged_in):
        make_prompts()  # creates 2 prompts
        content = client_logged_in.get(reverse("prompts:gallery")).content.decode()
        assert "2 prompts saved." in content

    def test_search_filters(self, client_logged_in):
        make_prompts()
        response = client_logged_in.get(reverse("prompts:gallery"), {"q": "reviewer"})
        content = response.content.decode()
        assert "Reviewer 2 pass" in content
        assert "Summarize paper" not in content
        assert "matching the filter" in content  # the count reflects the filter (#199 family)

    def test_tag_filter_chips(self, client_logged_in):
        make_prompts()
        response = client_logged_in.get(reverse("prompts:gallery"), {"tag": "writing"})
        content = response.content.decode()
        assert "Reviewer 2 pass" in content
        assert "Summarize paper" not in content

    def test_create_edit_delete(self, client_logged_in):
        response = client_logged_in.post(
            reverse("prompts:create"),
            {"title": "New prompt", "body": "Do the thing.", "tags": "misc"},
        )
        assert response.status_code == 302
        prompt = Prompt.objects.get(title="New prompt")
        client_logged_in.post(
            reverse("prompts:edit", args=[prompt.pk]),
            {"title": "New prompt", "body": "Do the better thing.", "tags": "misc"},
        )
        prompt.refresh_from_db()
        assert "better" in prompt.body
        client_logged_in.post(reverse("prompts:delete", args=[prompt.pk]))
        assert not Prompt.objects.filter(pk=prompt.pk).exists()


class TestPromptAPI:
    def test_crud_and_search_via_api(self, client, owner, settings):
        settings.ATLAS_API_KEY = "k"
        headers = {"HTTP_X_API_KEY": "k"}
        response = client.post(
            "/api/v1/prompts/",
            {"title": "From API", "body": "body text", "tags": "mcp"},
            content_type="application/json",
            **headers,
        )
        assert response.status_code == 201
        Prompt.objects.create(title="Other", body="unrelated", tags="")
        data = client.get("/api/v1/prompts/?q=api", **headers).json()
        assert data["count"] == 1
        assert data["results"][0]["title"] == "From API"


def test_mcp_client_prompt_functions(monkeypatch):
    import httpx

    from mcp_server import client as mcp_client

    monkeypatch.setenv("ATLAS_API_KEY", "k")
    calls = {}

    def fake_client():
        def handler(request):
            calls["url"] = str(request.url)
            return httpx.Response(200, json={"ok": True})

        return httpx.Client(base_url="http://t/api/v1", transport=httpx.MockTransport(handler))

    monkeypatch.setattr(mcp_client, "_client", fake_client)
    mcp_client.list_prompts("review")
    assert "/prompts/" in calls["url"] and "q=review" in calls["url"]
    mcp_client.get_prompt(3)
    assert calls["url"].endswith("/prompts/3/")


class TestPromptVariables:
    def test_variable_names_parsed_in_order_and_deduped(self):
        prompt = Prompt.objects.create(
            title="Var prompt",
            body="Review {{ paper }} for {{venue}}. Focus on {{paper}} stats.",
        )
        assert prompt.variable_names == ["paper", "venue"]

    def test_no_variables(self):
        prompt = Prompt.objects.create(title="Plain", body="No placeholders here.")
        assert prompt.variable_names == []

    def test_gallery_renders_fillin_inputs(self, client_logged_in):
        Prompt.objects.create(title="Var prompt", body="Summarize {{paper}} briefly.")
        response = client_logged_in.get(reverse("prompts:gallery"))
        content = response.content.decode()
        assert "Fill in before copying" in content
        assert 'data-var-name="paper"' in content
