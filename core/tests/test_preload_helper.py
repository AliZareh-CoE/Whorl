"""Owner report (2026-09-14, desktop 0.1.221 on Edge 152): the app booted blank because the
WebView refused to parse Vite's emitted preload helper ("Unexpected strict mode reserved
word"), which spa.js imports. The build now replaces that chunk with a three-token module
(frontend/scripts/simplify-preload.mjs); this guards the committed output and the hook."""

import re
from pathlib import Path

from django.conf import settings

ROOT = Path(settings.BASE_DIR)


def test_committed_preload_helper_is_the_trivial_module():
    helper = (ROOT / "static" / "js" / "islands" / "preload-helper-chunk.js").read_text()
    assert re.fullmatch(r"function (\w+)\(e\)\{return e\(\)\}export\{\1 as \w+\};\n?", helper), (
        helper[:120]
    )


def test_build_runs_the_simplifier_and_importers_still_resolve():
    makefile = (ROOT / "Makefile").read_text()
    assert "vite build && node scripts/simplify-preload.mjs" in makefile
    helper = (ROOT / "static" / "js" / "islands" / "preload-helper-chunk.js").read_text()
    alias = re.search(r"as (\w+)\}", helper).group(1)
    spa = (ROOT / "static" / "js" / "spa.js").read_text()
    imports = re.findall(
        r"import\{(\w+)(?: as \w+)?\}from\"./islands/preload-helper-chunk.js\"", spa
    )
    assert imports and all(name == alias for name in imports), (imports, alias)


def test_boot_watchdog_reports_line_and_column():
    spa_html = (ROOT / "templates" / "spa.html").read_text()
    assert '":" + e.lineno + ":" + e.colno' in spa_html
