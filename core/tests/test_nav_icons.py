"""Sidebar icon-language guard (Backlog #161, Owner-prompted).

The classic Django sidebar shares the React workspace's Lucide icon set via the
core/_nav_icon.html partial. Keep them in lockstep: every primary nav item must
render an icon, and the partial must define the glyph each one asks for. A
regression (someone re-adds a bare text link, or drops an icon name) fails here
instead of quietly breaking the one-icon-language convention.
"""

from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

TEMPLATES = Path(settings.BASE_DIR) / "templates"
BASE = TEMPLATES / "base.html"
PARTIAL = TEMPLATES / "core" / "_nav_icon.html"

NAV_ICONS = ("dashboard", "projects", "library", "writing", "prompts", "inbox", "assistant", "menu")


def test_base_includes_a_nav_icon_for_every_primary_item():
    text = BASE.read_text()
    for name in NAV_ICONS:
        assert f'_nav_icon.html" with name="{name}"' in text, f"base.html lost the {name} nav icon"


def test_partial_defines_each_named_glyph():
    text = PARTIAL.read_text()
    for name in NAV_ICONS:
        assert f'name == "{name}"' in text, f"_nav_icon.html has no glyph for {name}"


def test_no_bare_emoji_nav_glyphs_remain():
    text = BASE.read_text()
    # the hamburger ☰ and the ✨ Assistant glyph were swapped for Lucide SVGs
    assert "☰" not in text and "✨" not in text


@pytest.mark.django_db
def test_sidebar_renders_icons_when_logged_in(client, django_user_model):
    django_user_model.objects.create_superuser("owner2", "o2@example.com", "pw")
    client.force_login(django_user_model.objects.get(username="owner2"))
    html = client.get(reverse("core:dashboard")).content.decode()
    # the dashboard icon's first rect is a stable marker that the partial rendered
    assert 'viewBox="0 0 24 24"' in html
    assert "<span>Dashboard</span>" in html
