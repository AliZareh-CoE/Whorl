"""Small polish (#402): the active nav icon tint and the typeahead miss feedback stay wired."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_active_nav_icon_tint_and_typeahead_miss():
    layout = (BASE / "frontend/src/app/Layout.tsx").read_text()
    assert "[&>svg]:text-indigo-600" in layout
    files = (BASE / "frontend/src/app/pages/Files.tsx").read_text()
    assert "setTypedMiss(true)" in files and 'data-testid="typeahead-hint"' in files
    assert ".typeahead-miss" in (BASE / "assets/css/app.css").read_text()
