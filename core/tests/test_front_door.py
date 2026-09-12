"""One front door (Owner report 2026-09-06): classic pages send browsers to their SPA twin."""

import re
from pathlib import Path

import pytest

from core.spa_routes import spa_equivalent
from core.ui_middleware import UI_COOKIE
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
HTML = {"HTTP_ACCEPT": "text/html,application/xhtml+xml,*/*;q=0.8"}


@pytest.mark.parametrize(
    ("classic", "spa"),
    [
        ("/library/", "/library"),
        ("/library/12/", "/references/12"),
        ("/projects/x/", "/projects/x"),
        ("/projects/x/plan/", "/projects/x/plan"),
        ("/projects/x/notes/3/", "/projects/x/notes/3"),
        ("/projects/x/literature/report/", "/projects/x/report"),
        ("/projects/x/writing/7/", "/manuscripts/7"),
        ("/projects/x/writing/7/editor/", "/manuscripts/7/editor"),
        ("/projects/x/writing/7/files/", None),
        ("/classic/", None),
        ("/pet/", "/pet"),
    ],
)
def test_spa_equivalent(classic, spa):
    assert spa_equivalent(classic) == spa


def test_python_and_ts_maps_agree():
    """links.ts and spa_routes.py must map the same classic paths."""
    ts = Path("frontend/src/app/links.ts").read_text()
    for classic, spa in [
        ("/library/", "/library"),
        ("/library/12/", "/references/12"),
        ("/projects/x/writing/7/", "/manuscripts/7"),
        ("/projects/x/literature/queue/", "/projects/x/queue"),
    ]:
        assert spa_equivalent(classic) == spa
    assert re.search(r"library.*references", ts) and "manuscripts/" in ts


def test_browser_get_redirects_to_the_app(client_logged_in):
    project = ProjectFactory()
    response = client_logged_in.get(f"/projects/{project.slug}/plan/", **HTML)
    assert response.status_code == 302 and response["Location"] == f"/projects/{project.slug}/plan"
    response = client_logged_in.get("/search/?q=load+theory", **HTML)
    assert response.status_code == 302 and response["Location"] == "/search?q=load+theory"


def test_htmx_and_json_requests_are_untouched(client_logged_in):
    assert client_logged_in.get("/library/", HTTP_HX_REQUEST="true", **HTML).status_code == 200
    assert client_logged_in.get("/library/", HTTP_ACCEPT="application/json").status_code == 200
    assert client_logged_in.get("/library/").status_code == 200  # no Accept: a script, not a person


def test_classic_opt_in_sets_a_cookie_and_shows_the_way_back(client_logged_in):
    response = client_logged_in.get("/library/?classic=1", **HTML)
    assert response.status_code == 200
    assert response.cookies[UI_COOKIE].value == "classic"
    assert b'data-testid="classic-banner"' in response.content
    assert b'href="/library?ui=app"' in response.content
    # the cookie keeps classic browsable without ?classic=1 on every link
    client_logged_in.cookies[UI_COOKIE] = "classic"
    assert client_logged_in.get("/library/", **HTML).status_code == 200


def test_entering_through_classic_home_sets_the_cookie(client_logged_in):
    response = client_logged_in.get("/classic/", **HTML)
    assert response.status_code == 200 and response.cookies[UI_COOKIE].value == "classic"
    assert b"Back to the app" in response.content


def test_back_to_the_app_clears_the_cookie(client_logged_in):
    client_logged_in.cookies[UI_COOKIE] = "classic"
    response = client_logged_in.get("/library?ui=app", **HTML)
    assert response.status_code == 200  # the SPA shell
    assert response.cookies[UI_COOKIE].value == "" and response.cookies[UI_COOKIE]["max-age"] == 0
    del client_logged_in.cookies[UI_COOKIE]
    assert client_logged_in.get("/library/", **HTML).status_code == 302


def test_pages_without_a_twin_still_render_with_the_banner(client_logged_in):
    response = client_logged_in.get("/library/add/", **HTML)
    assert response.status_code == 200 and b"classic-banner" in response.content
    assert b'href="/?ui=app"' in response.content


def test_login_page_has_no_banner(client):
    assert b"classic-banner" not in client.get("/login/", **HTML).content
