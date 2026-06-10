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
