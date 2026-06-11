import pytest
from django.contrib.auth.models import User
from django.urls import reverse


def test_sanity():
    assert 1 + 1 == 2


def test_login_page_renders(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert b"Atlas" in response.content


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 302
    assert reverse("login") in response.url


@pytest.mark.django_db
def test_dashboard_renders_when_logged_in(client):
    user = User.objects.create_superuser("owner", password="pw")
    client.force_login(user)
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 200
    assert b"Dashboard" in response.content


@pytest.mark.django_db
def test_seed_demo_runs():
    from django.core.management import call_command

    call_command("seed_demo")


def test_seed_demo_includes_abstracts(db):
    # AUDIT #8 finding: tl;dr/Listen/reading-flow need real abstracts to demo (#90)
    from django.core.management import call_command

    from literature.models import Reference

    call_command("seed_demo")
    with_abstracts = Reference.objects.exclude(abstract="").count()
    assert with_abstracts >= 3
    # at least one to_read paper has an abstract, so reading-flow tl;dr demos out of the box
    from literature.models import ProjectReference

    assert (
        ProjectReference.objects.filter(reading_status="to_read")
        .exclude(reference__abstract="")
        .exists()
    )


class TestSpaShell:
    """Owner idea #20: after the cutover the SPA owns / and slash-less routes."""

    def test_requires_login(self, client):
        assert client.get("/").status_code == 302

    def test_any_slashless_path_serves_the_shell(self, client_logged_in):
        # Backlog #77: one catch-all rule — even a page no Django route names serves the
        # shell, so adding a React route never needs a Django change.
        for path in (
            "/",
            "/projects/some-slug",
            "/projects/x/plan",
            "/projects/x/read",
            "/library",
            "/references/24",
            "/manuscripts/3",
            "/automations",
            "/a-page-nobody-registered",
        ):
            response = client_logged_in.get(path)
            assert response.status_code == 200, path
            assert b'id="root"' in response.content, path

    def test_unknown_api_path_still_404s(self, client_logged_in):
        # the catch-all must NOT swallow unmatched /api/ paths
        assert client_logged_in.get("/api/v1/nonsense").status_code == 404

    def test_classic_pages_keep_their_urls(self, client_logged_in):
        from projects.tests.factories import ProjectFactory

        project = ProjectFactory()
        response = client_logged_in.get(f"/projects/{project.slug}/")  # trailing slash = classic
        assert b'id="root"' not in response.content
        assert project.name.encode() in response.content
        classic_home = client_logged_in.get("/classic/")
        assert b"Today, everywhere" in classic_home.content

    def test_old_app_bookmarks_redirect(self, client_logged_in):
        response = client_logged_in.get("/app/projects/x/plan")
        assert response.status_code == 302
        assert response.url == "/projects/x/plan"

    def test_app_redirect_is_not_an_open_redirect(self, client_logged_in):
        # /app//evil.com would become a protocol-relative redirect off-site
        response = client_logged_in.get("/app//evil.com/x")
        assert response.status_code == 302
        assert response.url == "/evil.com/x"  # collapsed to a local path
        assert not response.url.startswith("//")

    def test_spa_artifact_built(self):
        from pathlib import Path

        assert Path("static/js/spa.js").stat().st_size > 10_000

    def test_shell_sets_csrf_cookie(self, client_logged_in):
        # the SPA has no server-rendered form; its API writes need the token
        response = client_logged_in.get("/")
        assert "csrftoken" in response.cookies


def test_reading_flow_route_served(client_logged_in):
    from projects.tests.factories import ProjectFactory

    project = ProjectFactory()
    response = client_logged_in.get(f"/projects/{project.slug}/read")
    assert response.status_code == 200
    assert b'id="root"' in response.content


def test_github_templates_present_and_valid():
    from pathlib import Path

    import yaml

    base = Path(".github")
    assert (base / "PULL_REQUEST_TEMPLATE.md").exists()
    for name in ("bug_report.yml", "feature_request.yml", "config.yml"):
        path = base / "ISSUE_TEMPLATE" / name
        assert path.exists(), name
        yaml.safe_load(path.read_text())  # raises if malformed
