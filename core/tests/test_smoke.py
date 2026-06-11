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


class TestSpaShell:
    """Owner idea #20: the SPA shell at /app/."""

    def test_requires_login(self, client):
        assert client.get("/app/").status_code == 302

    def test_serves_shell_for_any_subpath(self, client_logged_in):
        for path in ("/app/", "/app/projects", "/app/anything/deep"):
            response = client_logged_in.get(path)
            assert response.status_code == 200
            assert b'id="root"' in response.content
            assert b"js/spa.js" in response.content

    def test_spa_artifact_built(self):
        from pathlib import Path

        assert Path("static/js/spa.js").stat().st_size > 10_000

    def test_shell_sets_csrf_cookie(self, client_logged_in):
        # the SPA has no server-rendered form; its API writes need the token
        response = client_logged_in.get("/app/")
        assert "csrftoken" in response.cookies
