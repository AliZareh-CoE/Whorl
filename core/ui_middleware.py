"""One front door (Owner report 2026-09-06).

The SPA owns every slash-less path; classic pages keep trailing slashes. Links, ⌘K rows,
search results and old bookmarks still pointed at classic URLs, so people "suddenly" landed
in the old UI — where Today, the todo list and the pet do not exist — with no way back.

This middleware sends a plain browser GET for a classic page to its SPA twin. Escape
hatches: ``?classic=1`` (or entering through ``/classic/``) sets an ``atlas_ui=classic``
cookie for the browser session so classic can still be browsed deliberately; the classic
banner's "Back to the app" link (``?ui=app``) clears it. HTMX and non-HTML requests are
never touched.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpResponseRedirect

from .spa_routes import spa_equivalent

UI_COOKIE = "atlas_ui"


def _wants_html(request) -> bool:
    """Real browser navigations always send text/html; fetch()/scripts/tests do not."""
    return "text/html" in request.headers.get("Accept", "")


def _plain_page_get(request) -> bool:
    return (
        request.method == "GET"
        and not request.headers.get("HX-Request")
        and request.headers.get("X-Requested-With") != "XMLHttpRequest"
        and _wants_html(request)
    )


class ClassicRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        params = request.GET.copy()
        wants_classic = params.pop("classic", [""])[-1] == "1"
        back_to_app = params.pop("ui", [""])[-1] == "app"
        entering_classic = request.path == "/classic/"
        target = spa_equivalent(request.path)
        classic_cookie = request.COOKIES.get(UI_COOKIE) == "classic" and not back_to_app

        if target and _plain_page_get(request) and not (wants_classic or classic_cookie):
            query = params.urlencode()
            return HttpResponseRedirect(target + (f"?{query}" if query else ""))

        request.classic_ui = not request.path.startswith(("/login/", "/logout/", "/admin/"))
        request.spa_back_url = (target or "/") + "?" + urlencode({"ui": "app"})
        response = self.get_response(request)
        if wants_classic or entering_classic:
            response.set_cookie(UI_COOKIE, "classic", samesite="Lax", httponly=True)
        elif back_to_app and UI_COOKIE in request.COOKIES:
            response.delete_cookie(UI_COOKIE)
        return response
