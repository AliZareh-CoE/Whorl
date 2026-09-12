"""#458 (backlog #138): the Studio's split gutters collapse a pane with one click."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_gutters_carry_chevrons():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Studio.tsx").read_text()
    for needle in (
        '"gutter-collapse"',
        "studio-gutter-btn",
        "Collapse the sidebar",
        "Collapse the PDF preview",
    ):
        assert needle in src, needle
    css = (BASE / "assets" / "css" / "app.css").read_text()
    assert ".studio-gutter-btn" in css
