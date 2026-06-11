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
