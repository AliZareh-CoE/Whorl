"""#433 (backlog #60): Library range selection — shift-click / shift-x from the anchor, ⌘A all."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_library_range_selection_wiring():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Library.tsx").read_text()
    for needle in (
        "const anchorRef",
        "const selectRange",
        'e.key === "X"',
        'e.key.toLowerCase() === "a"',
        "(e.nativeEvent as MouseEvent).shiftKey",
        "shift-x / shift-click range",
    ):
        assert needle in src, needle
    assert src.count("onCheck(i, r.id") == 2  # both the list rows and the cards
    chunks = " ".join(
        p.read_text(errors="ignore")
        for p in (BASE / "static" / "js" / "islands").glob("Library*.js")
    )
    assert "shift-click range" in chunks
