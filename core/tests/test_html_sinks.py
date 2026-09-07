"""#449 (backlog #152): one guard over every hand-built-HTML sink.

The SPA may set innerHTML only from server-rendered, nh3-sanitised `*html` fields; raw
`innerHTML =` assignments may only clear a node or write a static literal; templates never use
`|safe` / `autoescape off`; `mark_safe` lives in exactly one place, behind nh3.
"""

import re
from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)
FRONTEND = BASE / "frontend" / "src"
MARK_SAFE_ALLOWED = {"core/templatetags/markdown_extras.py"}


def _sources():
    for path in FRONTEND.rglob("*"):
        if path.suffix in (".ts", ".tsx") and "node_modules" not in path.parts:
            yield path, path.read_text(errors="ignore")


def test_dangerously_set_inner_html_only_from_html_fields():
    sinks = []
    for path, src in _sources():
        for m in re.finditer(r"dangerouslySetInnerHTML=\{\{\s*__html:\s*([^}]+?)\s*\}\}", src):
            expr = m.group(1).strip()
            sinks.append((path.relative_to(BASE).as_posix(), expr))
    assert sinks, "expected at least the Prose component"
    for where, expr in sinks:
        # the value must come from a field named *html (server-rendered, sanitised): `html`,
        # `citation.html`, `preview.data?.html ?? ""` — never a computed string or a template
        core = expr.split("??")[0].strip()
        assert re.search(r"(^|[.?\s])html$", core), f"{where}: raw HTML from {expr!r}"
        assert "`" not in expr and "+" not in expr, f"{where}: concatenated HTML in {expr!r}"


def test_raw_inner_html_assignments_are_static():
    for path, src in _sources():
        for m in re.finditer(r"\.innerHTML\s*=\s*(?!=)([^;]+);", src):
            value = m.group(1).strip()
            where = path.relative_to(BASE).as_posix()
            if value == '""':
                continue
            # a static literal (string parts joined with +) with no interpolation of data
            assert "${" not in value and re.fullmatch(r"(\s*'[^']*'\s*\+?)+", value), (
                f"{where}: dynamic innerHTML {value[:80]!r}"
            )


def test_templates_escape_everything_and_mark_safe_is_one_place():
    for path in (BASE / "templates").rglob("*.html"):
        text = path.read_text(errors="ignore")
        assert "|safe" not in text and "autoescape off" not in text, path
    users = set()
    for app in (
        "core",
        "projects",
        "literature",
        "writing",
        "notes",
        "research",
        "documents",
        "plans",
        "api",
    ):
        for path in (BASE / app).rglob("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            if "mark_safe(" in text or "format_html(" in text:
                users.add(path.relative_to(BASE).as_posix())
    assert users <= MARK_SAFE_ALLOWED, users - MARK_SAFE_ALLOWED
