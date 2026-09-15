"""Atlas inside another app's tab (#539): ATLAS_FRAME_ANCESTORS."""

import pytest
from django.conf import settings as django_settings
from django.urls import reverse

from core import diagnostics, framing

pytestmark = pytest.mark.django_db

ORIGIN = "http://localhost:3000"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("", []),
        (None, []),
        ("http://localhost:3000", ["http://localhost:3000"]),
        ("http://localhost:3000/", ["http://localhost:3000"]),
        ("HTTP://LocalHost:3000", ["http://localhost:3000"]),
        (
            "http://localhost:3000, https://lab.example.org",
            ["http://localhost:3000", "https://lab.example.org"],
        ),
        ("http://a:3000 http://a:3000", ["http://a:3000"]),
        ("http://[::1]:3000", ["http://[::1]:3000"]),
        # dropped, never guessed at
        ("localhost:3000", []),
        ("http://localhost:3000/atlas", []),
        ("http://localhost:3000?x=1", []),
        ("http://user:pw@localhost:3000", []),
        ("http://*.example.org", []),
        ("file:///etc/passwd", []),
        ("javascript:alert(1)", []),
        ("http://localhost:99999", []),
        ("http://", []),
    ],
)
def test_parse_ancestors(raw, expected):
    assert framing.parse_ancestors(raw) == expected


def test_parse_ancestors_is_capped():
    raw = " ".join(f"http://h{i}.example.org" for i in range(40))
    assert len(framing.parse_ancestors(raw)) == framing.MAX_ANCESTORS


def test_default_is_still_deny_everywhere(client_logged_in):
    assert django_settings.ATLAS_FRAME_ANCESTORS == []
    for url in (reverse("core:dashboard"), "/login/", "/api/v1/projects/"):
        r = client_logged_in.get(url)
        assert r.headers["X-Frame-Options"] == "DENY", url
        assert "Content-Security-Policy" not in r.headers, url


def test_listed_origins_replace_deny_with_frame_ancestors(client_logged_in, client, settings):
    settings.ATLAS_FRAME_ANCESTORS = [ORIGIN, "https://lab.example.org"]
    expected = "frame-ancestors 'self' http://localhost:3000 https://lab.example.org"
    for url in (reverse("core:dashboard"), "/api/v1/projects/", "/diagnostics/"):
        r = client_logged_in.get(url)
        assert "X-Frame-Options" not in r.headers, url
        assert r.headers["Content-Security-Policy"] == expected, url
    # the login page too — the host's tab starts there when the session is cold
    r = client.get("/login/")
    assert "X-Frame-Options" not in r.headers
    assert r.headers["Content-Security-Policy"] == expected


def test_exempt_responses_and_existing_policies_are_left_alone(settings, rf):
    settings.ATLAS_FRAME_ANCESTORS = [ORIGIN]
    from django.http import HttpResponse

    def view(_request):
        resp = HttpResponse("x")
        resp.xframe_options_exempt = True
        return resp

    r = framing.FrameAncestorsMiddleware(view)(rf.get("/"))
    assert "Content-Security-Policy" not in r.headers

    def strict(_request):
        resp = HttpResponse("x")
        resp["X-Frame-Options"] = "DENY"
        resp["Content-Security-Policy"] = "default-src 'none'"
        return resp

    r = framing.FrameAncestorsMiddleware(strict)(rf.get("/"))
    assert r.headers["Content-Security-Policy"] == "default-src 'none'"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_middleware_runs_after_the_clickjacking_one():
    mw = django_settings.MIDDLEWARE
    ours = mw.index("core.framing.FrameAncestorsMiddleware")
    theirs = mw.index("django.middleware.clickjacking.XFrameOptionsMiddleware")
    assert ours < theirs, "listed earlier = runs later on the response, so it can replace DENY"


def test_diagnostics_say_who_may_embed(client_logged_in, settings):
    r = client_logged_in.get("/api/v1/diagnostics/")
    assert r.status_code == 200
    assert r.json()["frame_ancestors"] == []
    assert "embeddable from: nobody (X-Frame-Options DENY)" in r.json()["text"]
    settings.ATLAS_FRAME_ANCESTORS = [ORIGIN]
    report = diagnostics.collect()
    assert report["frame_ancestors"] == [ORIGIN]
    assert f"embeddable from: {ORIGIN}" in diagnostics.as_text(report)
