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

    def test_dashboard_calm_mode_is_built(self):
        # #274/#278: a localStorage-persisted "calm mode" toggle hides the monthly stats and
        # is shared (../calm) so the palette can flip it live. Guard that the committed bundle
        # reflects the source (i.e. it was rebuilt).
        from pathlib import Path

        assert "atlas-calm" in Path("frontend/src/app/calm.ts").read_text()  # the shared key
        assert "Calm mode" in Path("frontend/src/app/pages/Dashboard.tsx").read_text()  # toggle
        chunk = Path("static/js/islands/Dashboard-chunk.js").read_text()
        assert "Calm mode" in chunk or "Full view" in chunk  # it compiled into the served bundle

    def test_command_palette_theme_verb_is_built(self):
        # #275-cmd: the ⌘K palette exposes a "Toggle dark mode" verb (surfacing the
        # #273 theme toggle). Guard that the source and committed bundle agree.
        from pathlib import Path

        src = Path("frontend/src/app/CommandBar.tsx").read_text()
        bundle = Path("static/js/spa.js").read_text()
        for verb in ("Toggle dark mode", "Toggle calm mode"):  # #276 theme, #277 calm
            assert verb in src
            assert verb in bundle

    def test_data_load_failures_use_shared_error_state(self):
        # #280: every page's data-load failure uses the retryable ErrorState, not a bare
        # red line. Guard the component is built and no page regresses to the old pattern.
        import re
        from pathlib import Path

        assert "Try again" in Path("frontend/src/components/ErrorState.tsx").read_text()
        built = Path("static/js/islands/ErrorState-chunk.js").read_text()
        assert "Try again" in built  # it compiled into the served bundle
        # no page should still bail out with a bare red <p> on load failure
        for page in Path("frontend/src/app/pages").glob("*.tsx"):
            assert not re.search(r'text-red-600">Couldn.t load', page.read_text()), page.name
        # the primary index/detail pages must keep the shared error state (#280 + #281 rollout)
        pages_dir = Path("frontend/src/app/pages")
        wired = (
            "Dashboard",
            "Documents",
            "Files",
            "ProjectOverview",
            "Plan",  # #280
            "Projects",
            "Library",
            "Notes",
            "Writing",
            "Literature",
            "Search",  # #281
            "Decisions",
            "Timeline",
            "Figures",
            "Inbox",
            "Review",  # #282
        )
        for name in wired:
            assert "ErrorState" in (pages_dir / f"{name}.tsx").read_text(), name

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


def test_make_audit_target_exists():
    from pathlib import Path

    assert Path("scripts/audit.sh").exists()
    assert "audit:" in Path("Makefile").read_text()
    # the script is read-only: it must not POST/PATCH/DELETE
    script = Path("scripts/audit.sh").read_text()
    assert "-X POST" not in script and "-X DELETE" not in script and "-X PATCH" not in script


def test_ci_workflow_present_and_valid():
    from pathlib import Path

    import yaml

    path = Path(".github/workflows/ci.yml")
    assert path.exists()
    wf = yaml.safe_load(path.read_text())
    steps = wf["jobs"]["test"]["steps"]
    blob = path.read_text()
    # the gate the loop runs by hand must be in CI
    assert "ruff check ." in blob
    assert "pytest" in blob
    assert "npm run check" in blob  # tsc --noEmit
    assert "git diff --exit-code" in blob  # assets staleness
    assert len(steps) >= 6
