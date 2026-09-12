"""#452 (backlog #116): the Studio's PDF preview carries a pdf.js text layer — selectable text."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_preview_pages_have_a_text_layer():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Studio.tsx").read_text()
    for needle in (
        "const libRef",
        'textDiv.className = "textLayer"',
        "streamTextContent()",
        "new TextLayer({ textContentSource",
        'wrap.className = "studio-page"',
        '`.studio-page[data-page="${n}"]`',
        '`.studio-page[data-page="${locate.page}"]`',
    ):
        assert needle in src, needle
    assert "canvas.studio-page" not in src and "canvas[data-page" not in src
    css = (BASE / "assets" / "css" / "app.css").read_text()
    assert ".textLayer span" in css  # shared with the reader — transparent glyphs over the canvas
