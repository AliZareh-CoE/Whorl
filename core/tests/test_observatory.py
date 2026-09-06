"""The Observatory identity (owner-directed redesign, 2026-09-06) stays wired.

Tokens under `.dark` re-skin every page; the constellation canvas lives in a shared static
module used by the React dashboard and the login template; the shell + dashboard carry the
signature pieces (spotlight ⌘K, orbit rings, display type).
"""

from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

BASE = Path(settings.BASE_DIR)


def test_design_tokens_reskin_the_dark_theme():
    css = (BASE / "assets" / "css" / "app.css").read_text()
    # the whole trick: Tailwind emits var(--color-*), so redefining the tokens under .dark
    # restyles all pages at once
    assert "--color-stone-950: #05070f" in css
    assert "--color-stone-900: rgb(16 20 40 / 0.62)" in css  # glass panel
    assert "--color-indigo-600: #7c6cff" in css  # electric violet accent
    assert "@keyframes aurora" in css and ".dark body::before" in css
    assert '[class~="dark:bg-stone-900"]' in css and "backdrop-filter" in css  # glass
    assert "--font-display" in css and "Space Grotesk" in css


def test_fonts_are_vendored_for_offline_use():
    fonts = BASE / "static" / "fonts"
    assert (fonts / "Inter-var.woff2").stat().st_size > 10_000
    assert (fonts / "SpaceGrotesk-var.woff2").stat().st_size > 10_000
    assert "Open Font License" in (fonts / "LICENSE-OFL.txt").read_text()


def test_constellation_module_is_shared_by_spa_and_login():
    js = (BASE / "static" / "js" / "constellation.js").read_text()
    assert "export function mountConstellation" in js
    assert "prefers-reduced-motion" in js  # renders a static frame for reduced motion
    login = (BASE / "templates" / "registration" / "login.html").read_text()
    assert "constellation.js" in login and "mountConstellation" in login
    component = (BASE / "frontend" / "src" / "components" / "Constellation.tsx").read_text()
    assert "/static/js/constellation.js" in component
    dashboard = (BASE / "frontend" / "src" / "app" / "pages" / "Dashboard.tsx").read_text()
    assert "<Constellation" in dashboard and "OrbitRing" in dashboard
    assert "Calm mode" in dashboard  # the calm toggle survives the redesign


def test_shell_carries_the_signature_pieces():
    layout = (BASE / "frontend" / "src" / "app" / "Layout.tsx").read_text()
    assert "Ask Atlas anything" in layout  # the ⌘K spotlight pill
    assert 'from "lucide-react"' in layout  # icon rail
    assert "Observatory (dark)" in layout and "Paper (light)" in layout


def test_built_bundle_matches_the_source():
    bundle = (BASE / "static" / "js" / "spa.js").read_text(errors="ignore")
    assert "Ask Atlas anything" in bundle
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").glob("*.js"))
    assert "/static/js/constellation.js" in chunks  # the dashboard lazy-loads the canvas


@pytest.mark.django_db
def test_login_page_renders_the_observatory(client):
    html = client.get(reverse("login")).content.decode()
    assert 'id="constellation"' in html
    assert "Enter the observatory" in html
