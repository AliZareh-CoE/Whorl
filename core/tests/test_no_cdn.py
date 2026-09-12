"""Offline desktop (#385): nothing the app needs at runtime may come from a CDN.

The graph libraries and pdf.js were vendored earlier; htmx and Alpine (the classic shell)
were the last two unpkg loads. A desktop without internet must still draw every page."""

import re
from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)
CDN = re.compile(r"https?://(unpkg\.com|cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com|esm\.sh)/")


def _sources():
    for folder, pattern in (
        ("templates", "*.html"),
        ("frontend/src", "*.ts"),
        ("frontend/src", "*.tsx"),
    ):
        yield from (BASE / folder).rglob(pattern)


def test_no_cdn_urls_in_templates_or_spa_sources():
    offenders = [
        f"{p.relative_to(BASE)}:{i}"
        for p in _sources()
        for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1)
        if CDN.search(line)
    ]
    assert not offenders, offenders


def test_htmx_and_alpine_are_vendored():
    assert (BASE / "static/vendor/htmx/htmx.min.js").stat().st_size > 40_000
    assert (BASE / "static/vendor/alpine/alpine.min.js").stat().st_size > 40_000
    base = (BASE / "templates/base.html").read_text()
    assert "vendor/htmx/htmx.min.js" in base and "vendor/alpine/alpine.min.js" in base
