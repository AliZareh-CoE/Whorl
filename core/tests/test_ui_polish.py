"""Cycle 9 (UI/UX): toast messages, keyboard shortcut wiring, accessibility hooks."""

import pytest
from django.urls import reverse

from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


class TestUIPolish:
    def test_skip_link_and_main_landmark(self, client_logged_in):
        response = client_logged_in.get(reverse("core:dashboard"))
        content = response.content.decode()
        assert 'href="#main"' in content
        assert 'id="main"' in content

    def test_search_shortcut_wiring(self, client_logged_in):
        response = client_logged_in.get(reverse("core:dashboard"))
        content = response.content.decode()
        assert 'id="global-search"' in content
        assert 'aria-label="Search everything"' in content
        assert "( / )" in content

    def test_messages_render_with_level_and_dismiss(self, client_logged_in):
        project = ProjectFactory()
        # archive action emits a success message and redirects to the list page
        response = client_logged_in.post(
            reverse("projects:archive", args=[project.slug]), follow=True
        )
        content = response.content.decode()
        assert 'role="alert"' in content
        assert "border-green-200" in content  # success styling
        assert 'aria-label="Dismiss"' in content

    def test_error_message_styled_as_error(self, client_logged_in):
        from literature.tests.factories import ReferenceFactory

        ref = ReferenceFactory()  # no pdf attached
        response = client_logged_in.get(reverse("literature:read", args=[ref.pk]), follow=True)
        content = response.content.decode()
        assert "border-red-200" in content  # error styling on "No PDF attached"


class TestResponsiveSidebar:
    def test_hamburger_and_drawer_classes(self, client_logged_in):
        from django.urls import reverse as r

        response = client_logged_in.get(r("core:dashboard"))
        content = response.content.decode()
        assert 'aria-label="Open navigation"' in content
        assert "lg:hidden" in content
        assert "-translate-x-full" in content
        assert "lg:translate-x-0" in content

    def test_tables_scroll_on_narrow_screens(self, client_logged_in):
        from django.urls import reverse as r

        from literature.tests.factories import ReferenceFactory

        ReferenceFactory()
        response = client_logged_in.get(r("literature:index"))
        assert b'class="overflow-x-auto"><table' in response.content

    def test_drawer_swipe_to_close_wiring(self, client_logged_in):
        from django.urls import reverse as r

        response = client_logged_in.get(r("core:dashboard"))
        content = response.content.decode()
        assert "@touchstart" in content
        assert "@touchend" in content
        assert "sidebarOpen = false; touchX = null" in content


class TestTouchTargets:
    def test_check_off_buttons_have_extended_hit_area(self, client_logged_in):
        from django.urls import reverse as r

        from plans.tests.factories import MilestoneFactory, TaskFactory

        milestone = MilestoneFactory()
        TaskFactory(milestone=milestone)
        response = client_logged_in.get(r("plans:plan", args=[milestone.phase.project.slug]))
        content = response.content.decode()
        # 20px visual + 10px pseudo-element padding per side ≈ 40px tap target
        assert content.count("after:-inset-2.5") >= 2  # milestone + task buttons


class TestSuggestKeyboardNav:
    def test_suggest_partial_has_listbox_roles(self, client_logged_in):
        from projects.tests.factories import ProjectFactory

        ProjectFactory(name="Attention pilot")
        response = client_logged_in.get("/search/suggest/?q=attention")
        content = response.content.decode()
        assert 'role="listbox"' in content
        assert content.count('role="option"') >= 2  # result + the all-results row
        assert 'class="suggest-item' in content

    def test_combobox_wiring_in_base_template(self, client_logged_in):
        from django.urls import reverse as r

        response = client_logged_in.get(r("core:dashboard"))
        content = response.content.decode()
        assert 'role="combobox"' in content
        assert 'aria-controls="suggest-listbox"' in content
        assert "ArrowDown" in content
        assert "aria-activedescendant" in content


class TestEdgeSwipeAndRecentSearches:
    def test_edge_swipe_wiring(self, client_logged_in):
        from django.urls import reverse as r

        response = client_logged_in.get(r("core:dashboard"))
        content = response.content.decode()
        assert "edgeX" in content
        assert "@touchstart.window" in content
        assert "sidebarOpen = true" in content

    def test_recent_searches_wiring(self, client_logged_in):
        from django.urls import reverse as r

        response = client_logged_in.get(r("core:dashboard"))
        content = response.content.decode()
        assert "atlas-recent-searches" in content
        assert "Recent searches" in content
        assert "textContent = q" in content  # stored queries rendered inertly


def test_reduced_motion_is_respected_globally():
    # #272: users who set "reduce motion" should not see the skeleton pulse / transitions.
    from pathlib import Path

    from django.conf import settings

    src = (Path(settings.BASE_DIR) / "assets" / "css" / "app.css").read_text()
    assert "prefers-reduced-motion: reduce" in src
    built = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text()
    assert "prefers-reduced-motion" in built  # it actually compiled into the served CSS


def test_observatory_is_the_default_theme():
    # Observatory (dark) is Atlas's identity and the default (owner-directed, 2026-09-06);
    # "Paper" (light) is an explicit saved choice. This replaced #273's follow-the-OS default.
    from pathlib import Path

    from django.conf import settings

    for name in ("base.html", "spa.html"):
        html = (Path(settings.BASE_DIR) / "templates" / name).read_text()
        assert 'classList.toggle("dark", stored() !== "light")' in html, name
        assert 'localStorage.setItem("theme"' in html, name  # the toggle persists a choice
        assert "prefers-color-scheme" not in html, name  # the OS no longer decides

    # The standalone login page (the desktop app's first screen) follows the same rule.
    login = (Path(settings.BASE_DIR) / "templates" / "registration" / "login.html").read_text()
    assert 'if (t !== "light") document.documentElement.classList.add("dark")' in login


def test_calm_mode_is_class_based_app_wide():
    # #275: calm mode is reflected as a `.calm` class on <html> so CSS `calm:` variants
    # quiet secondary chrome app-wide. Guard the variant compiles + the wiring is present.
    from pathlib import Path

    from django.conf import settings

    base = Path(settings.BASE_DIR)
    src = (base / "assets" / "css" / "app.css").read_text()
    assert "@custom-variant calm" in src
    built = (base / "static" / "css" / "app.css").read_text()
    assert ".calm" in built  # the variant compiled into the served CSS
    # the preference is applied as a class before paint on both shells
    for name in ("base.html", "spa.html"):
        html = (base / "templates" / name).read_text()
        assert 'classList.add("calm")' in html, name
    # calm.ts keeps the class in sync when toggled live
    assert 'classList.toggle("calm"' in (base / "frontend" / "src" / "app" / "calm.ts").read_text()
