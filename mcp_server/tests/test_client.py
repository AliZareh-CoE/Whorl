"""mcp_server.client is Django-free; test it with a mock transport."""

import httpx
import pytest

from mcp_server import client


def calls_url_has(calls, fragment):
    return fragment in calls["url"]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ATLAS_API_URL", "http://testserver")
    monkeypatch.setenv("ATLAS_API_KEY", "k")


@pytest.fixture
def capture(monkeypatch, env):
    calls = {}

    def fake_client():
        def handler(request):
            calls["method"] = request.method
            calls["url"] = str(request.url)
            calls["body"] = request.content.decode() if request.content else ""
            return httpx.Response(200, json={"ok": True})

        return httpx.Client(
            base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(client, "_client", fake_client)
    return calls


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("ATLAS_API_KEY", raising=False)
    with pytest.raises(client.AtlasClientError, match="ATLAS_API_KEY"):
        client.list_projects()


def test_complete_milestone_patches_timestamp(capture):
    client.complete_milestone(7)
    assert capture["method"] == "PATCH"
    assert capture["url"].endswith("/milestones/7/")
    assert "completed_at" in capture["body"]


def test_add_reference_by_doi_includes_project(capture):
    client.add_reference_by_doi("10.1/x", "my-project")
    assert capture["url"].endswith("/references/by-doi/")
    assert "my-project" in capture["body"]


def test_error_response_raises_with_detail(monkeypatch, env):
    def fake_client():
        return httpx.Client(
            base_url="http://testserver/api/v1",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(404, json={"detail": "nope"})
            ),
        )

    monkeypatch.setattr(client, "_client", fake_client)
    with pytest.raises(client.AtlasClientError, match="404"):
        client.get_plan("missing")


def test_no_django_imports():
    """The MCP client must stay a pure HTTP client — the API is the single contract."""
    import ast

    import mcp_server.client as module

    tree = ast.parse(open(module.__file__).read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "django" not in imported
    assert imported <= {"os", "datetime", "httpx"}


class TestETagCache:
    @pytest.fixture(autouse=True)
    def fresh_cache(self):
        client._etag_cache.clear()
        yield
        client._etag_cache.clear()

    def _transport(self, monkeypatch, statuses):
        """Server stub: first response 200+ETag, then 304 when If-None-Match matches."""

        def fake_client():
            def handler(request):
                statuses.append((request.method, request.headers.get("If-None-Match", "")))
                if request.headers.get("If-None-Match") == 'W/"abc"':
                    return httpx.Response(304)
                return httpx.Response(200, json={"projects": [1, 2]}, headers={"ETag": 'W/"abc"'})

            return httpx.Client(
                base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
            )

        monkeypatch.setattr(client, "_client", fake_client)

    def test_repeat_get_serves_cached_body_on_304(self, monkeypatch, env):
        seen = []
        self._transport(monkeypatch, seen)
        first = client.list_projects()
        second = client.list_projects()
        assert first == second == {"projects": [1, 2]}
        assert seen == [("GET", ""), ("GET", 'W/"abc"')]

    def test_params_split_the_cache(self, monkeypatch, env):
        seen = []
        self._transport(monkeypatch, seen)
        client.search("alpha")
        client.search("beta")  # different params — must not send alpha's ETag
        assert seen == [("GET", ""), ("GET", "")]

    def test_posts_never_touch_the_cache(self, monkeypatch, env):
        seen = []
        self._transport(monkeypatch, seen)
        client.quick_capture("hello")
        assert seen == [("POST", "")]
        assert client._etag_cache == {}


def test_get_weekly_review_builds_request(capture):
    from mcp_server import client

    client.get_weekly_review("attention-and-memory", weeks_back=2)
    assert calls_url_has(capture, "/weekly-review/")
    assert "project=attention-and-memory" in capture["url"]
    assert "weeks_back=2" in capture["url"]


def test_get_weekly_review_global(capture):
    from mcp_server import client

    client.get_weekly_review()
    assert "project=" not in capture["url"]


def test_get_synthesis_scaffold_builds_request(capture):
    from mcp_server import client

    client.get_synthesis_scaffold("attention-and-memory")
    assert "/projects/attention-and-memory/synthesis/" in capture["url"]
