"""#549: nothing on Today is lost by accident — delete, tick and snooze show an undo toast;
`z` takes the last action back. A UI slice over the existing API (no backend change)."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_undo_toast_exposes_undo_last():
    toast = (BASE / "frontend" / "src" / "components" / "UndoToast.tsx").read_text()
    assert "export function undoLast()" in toast and "let current: Toast | null" in toast


def test_today_wires_undo_for_delete_tick_and_snooze():
    today = (BASE / "frontend" / "src" / "app" / "pages" / "Today.tsx").read_text()
    assert "import { showUndo, undoLast }" in today
    assert today.count("showUndo(") == 3  # delete, tick, snooze
    # a deleted row comes back with every field it had; a done plain row is re-created open and
    # ticked again (a fresh stamp puts it back in Done today); a done repeating row is created
    # done so ticking cannot spawn a second occurrence
    assert "done: asDone, due_at: gone.due_at, all_day: gone.all_day, repeat: gone.repeat" in today
    assert "const asDone = gone.done && !!gone.repeat;" in today
    assert "if (gone.done && !asDone) await api(`/todos/${made.id}/`" in today
    assert "ids.splice(Math.min(ctx.index, ids.length), 0, made.id)" in today  # its old place
    assert "body: JSON.stringify(before)" in today  # snooze undo restores the exact day
    assert 'e.key === "z"' in today and "z undoes" in today
    assert today.index('e.key === "z"') < today.index(
        "else if (!t) return;"
    )  # works on an empty list
    dash = (BASE / "frontend" / "src" / "app" / "pages" / "Dashboard.tsx").read_text()
    assert dash.count("showUndo(`Done —") == 1  # the hero tick has the same toast
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "z undoes" in chunks


def test_shortcuts_sheet_lists_the_today_keys():
    sheet = (BASE / "frontend" / "src" / "app" / "shortcuts.tsx").read_text()
    assert 'title: "Today"' in sheet
    for key in ('["s / S"', '["z"', '["x"', '["⌥ ↑ / ↓"'):
        assert key in sheet.split('title: "Today"', 1)[1].split("title:", 1)[0], key
