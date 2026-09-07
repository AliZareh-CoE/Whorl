"""#436: the local related-papers list reaches the Reference page and Claude (MCP)."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_reference_page_shows_related():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Reference.tsx").read_text()
    for needle in (
        "/references/${id}/related/",
        'data-testid="related-section"',
        'data-testid="related-row"',
        "Related in your library",
        "nothing leaves the machine",
    ):
        assert needle in src, needle
    chunks = " ".join(
        p.read_text(errors="ignore")
        for p in (BASE / "static" / "js" / "islands").glob("Reference*.js")
    )
    assert "related-section" in chunks


def test_mcp_tool_calls_the_related_endpoint(monkeypatch):
    from mcp_server import client as mcp_client
    from mcp_server import server

    seen = {}
    monkeypatch.setattr(
        mcp_client, "_request", lambda method, path, **kw: seen.update(path=path) or []
    )
    assert server.get_related_in_library(7) == []
    assert seen["path"] == "/references/7/related/"
