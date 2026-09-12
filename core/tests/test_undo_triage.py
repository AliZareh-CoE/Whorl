"""#440 (backlog #158): filing or dismissing a capture inline can be undone for a few seconds."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)
SRC = BASE / "frontend" / "src"


def test_undo_host_is_mounted_once_and_used_by_both_triage_surfaces():
    host = (SRC / "components" / "UndoToast.tsx").read_text()
    for needle in (
        "export function showUndo",
        "export function UndoHost",
        'data-testid="undo-toast"',
        'data-testid="undo-button"',
        "ms = 6000",
    ):
        assert needle in host, needle
    main = (SRC / "app" / "main.tsx").read_text()
    assert main.count("<UndoHost />") == 1
    inbox = (SRC / "app" / "pages" / "Inbox.tsx").read_text()
    assert (
        "showUndo(" in inbox and "processed: false, project: ctx?.before?.project ?? null" in inbox
    )
    dashboard = (SRC / "app" / "pages" / "Dashboard.tsx").read_text()
    assert "showUndo(" in dashboard and "processed: false, project: null" in dashboard
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "undo-toast" in chunks
