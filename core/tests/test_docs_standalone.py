"""#454: the run-from-source path is documented and its make target exists."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_standalone_path_is_documented():
    makefile = (BASE / "Makefile").read_text()
    assert "\nstandalone:" in makefile
    assert "config.settings.desktop uv run python manage.py run_desktop" in makefile
    readme = (BASE / "README.md").read_text()
    assert "## No installer? Run it from source in two commands" in readme
    assert "make standalone" in readme and "ATLAS_DATA_DIR" in readme
    assert '$env:DJANGO_SETTINGS_MODULE = "config.settings.desktop"' in readme
    desktop = (BASE / "desktop" / "README.md").read_text()
    assert "## No build at all: the server from source" in desktop
