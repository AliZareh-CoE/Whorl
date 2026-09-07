"""#422 (backlog #51) — every template parses, and the title/breadcrumb blocks carry no script.

The cycle-44 corruption class: a `<script>` pasted into a `{% block title %}` rendered into the
document `<title>` and broke every page's chrome. Cheap to guard, so it is guarded.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.template import engines

BASE = Path(settings.BASE_DIR)
TEMPLATES = sorted(
    p
    for d in [BASE / "templates", *BASE.glob("*/templates")]
    if d.is_dir()
    for p in d.rglob("*.html")
    if ".venv" not in p.parts and "node_modules" not in p.parts
)
BLOCK = re.compile(r"{%\s*block\s+(title|breadcrumbs)\s*%}(.*?){%\s*endblock", re.S | re.I)


def test_templates_were_found():
    assert len(TEMPLATES) > 50


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: str(p.relative_to(BASE)))
def test_template_parses_and_chrome_blocks_are_clean(path):
    source = path.read_text(encoding="utf-8")
    engines["django"].from_string(source)  # raises TemplateSyntaxError on a broken tag
    for name, body in BLOCK.findall(source):
        assert "<script" not in body.lower(), f"{path.name}: <script> inside block {name}"
        assert "<style" not in body.lower(), f"{path.name}: <style> inside block {name}"
