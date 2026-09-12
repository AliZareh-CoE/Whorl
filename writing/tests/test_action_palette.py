"""#447 (backlog #119 + #139): the Studio's ⌘⇧P actions palette lists every action with its key."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_palette_is_wired_with_bindings():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Studio.tsx").read_text()
    for needle in (
        "function ActionPalette",
        'data-testid="action-palette"',
        'data-testid="action-row"',
        'k === "p" && e.shiftKey',
        '{ label: "Save", keys:',
        '{ label: "Compile", keys:',
        '{ label: "Locate the cursor in the PDF"',
        '{ label: "New file',
        '"Download the submission .zip"',
        "Keymap:",
    ):
        assert needle in src, needle
    sheet = (BASE / "frontend" / "src" / "app" / "shortcuts.tsx").read_text()
    assert "⇧ P" in sheet and "Actions palette" in sheet
    chunks = " ".join(
        p.read_text(errors="ignore")
        for p in (BASE / "static" / "js" / "islands").glob("Studio*.js")
    )
    assert "action-palette" in chunks
