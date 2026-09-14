"""#499 — link captures know their page."""

from pathlib import Path

import httpx
import pytest

from notes import links
from notes.models import QuickCapture

PAGE = """<html><head><meta property="og:title" content="Attention Is All You Need &amp; more">
<title>  1706.03762  </title></head><body>hi</body></html>"""


def test_title_from_html_prefers_og_title_then_title_and_cleans_it():
    assert links.title_from_html(PAGE) == "Attention Is All You Need & more"
    assert links.title_from_html("<title>\n Two\n   words </title>") == "Two words"
    assert links.title_from_html('<meta content="Rev" property="og:title">') == "Rev"
    assert links.title_from_html("<p>no title</p>") == ""
    assert len(links.title_from_html("<title>" + "x" * 900 + "</title>")) == 300


def test_check_url_refuses_non_http_and_private_hosts():
    for bad in ("ftp://example.org/x", "javascript:alert(1)", "", "http://"):
        with pytest.raises(links.LinkError):
            links.check_url(bad)
    for private in (
        "http://127.0.0.1/",
        "http://10.1.2.3/x",
        "http://localhost:8000/",
        "http://192.168.1.4/",
        "http://[::1]/",
        "http://atlas/",
    ):
        with pytest.raises(links.LinkError, match="private"):
            links.check_url(private)
    assert links.check_url(" http://8.8.8.8/paper ") == "http://8.8.8.8/paper"


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_fetch_link_title_reads_html_only_and_caps_the_body(monkeypatch):
    monkeypatch.setattr(links, "_host_is_private", lambda host: False)
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.path == "/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        if request.url.path == "/missing":
            return httpx.Response(404, text="nope")
        if request.url.path == "/big":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"<title>Early</title>" + b"x" * (links.MAX_BYTES * 2),
            )
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=PAGE)

    with _client(handler) as client:
        assert (
            links.fetch_link_title("https://example.org/abs/1", client=client)
            == "Attention Is All You Need & more"
        )
        assert links.fetch_link_title("https://example.org/pdf", client=client) == ""
        assert links.fetch_link_title("https://example.org/big", client=client) == "Early"
        with pytest.raises(links.LinkError, match="404"):
            links.fetch_link_title("https://example.org/missing", client=client)
    assert len(calls) == 4


@pytest.mark.django_db
def test_enrich_capture_remembers_the_title_once(monkeypatch, client, settings, django_user_model):
    monkeypatch.setattr(links, "_host_is_private", lambda host: False)
    seen = []

    def handler(request):
        seen.append(1)
        if request.url.host == "down.example":
            raise httpx.ConnectError("boom")
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text="<title>Page</title>"
        )

    c = QuickCapture.objects.create(text="https://example.org/abs/1")
    with _client(handler) as http:
        out = links.enrich_capture(c, client=http)
        assert out == {
            "url": "https://example.org/abs/1",
            "site": "example.org",
            "title": "Page",
            "error": "",
        }
        assert c.link_title == "Page" and c.link_fetched_at is not None
        links.enrich_capture(c, client=http)  # remembered, not fetched again
        assert len(seen) == 1
        links.enrich_capture(c, force=True, client=http)
        assert len(seen) == 2
        # a failed fetch is stamped too, with the reason
        d = QuickCapture.objects.create(text="see https://down.example/x for details")
        out = links.enrich_capture(d, client=http)
        assert out["title"] == "" and "could not fetch" in out["error"] and d.link_fetched_at
        assert (
            links.enrich_capture(QuickCapture.objects.create(text="no link"), client=http)["error"]
            == "no link in the capture"
        )

    # convert: a bare link becomes a note titled by the page
    from notes import capture as cap
    from projects.tests.factories import ProjectFactory

    project = ProjectFactory()
    made = cap.convert(c, "note", project)
    assert made["title"] == "Page"
    assert project.notes.get(pk=made["id"]).body.startswith("https://example.org/abs/1")

    # API: the action (fetcher stubbed), force, and the serializer fields
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("atlas", "a@b.c", "atlas")
    monkeypatch.setattr(links, "fetch_link_title", lambda url, client=None: "Stubbed title")
    e = QuickCapture.objects.create(text="https://example.org/abs/2")
    assert (
        client.post(f"/api/v1/quick-capture/{e.id}/enrich/", HTTP_HOST="127.0.0.1").status_code
        == 401
    )
    r = client.post(
        f"/api/v1/quick-capture/{e.id}/enrich/", HTTP_X_API_KEY="k", HTTP_HOST="127.0.0.1"
    )
    assert (
        r.status_code == 200
        and r.json()["link_title"] == "Stubbed title"
        and r.json()["link_error"] == ""
    )
    assert r.json()["link_fetched_at"] and r.json()["hint"]["url"] == "https://example.org/abs/2"
    tsx = Path("frontend/src/app/pages/Inbox.tsx").read_text()
    for needle in ('data-testid="link-title"', "/enrich/", "link_fetched_at"):
        assert needle in tsx, needle
