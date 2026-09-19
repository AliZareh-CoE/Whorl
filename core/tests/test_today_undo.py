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
    # #570: a deleted row goes to the Trash and the undo restores that very row — no re-create,
    # no second tick, no reorder splice: the stamp, the rule, the chain and the place survive
    assert 'await api(`/todos/${id}/restore/`, { method: "POST" })' in today
    assert "done: asDone" not in today and "0, made.id)" not in today
    assert "in the Trash for 30 days" in today
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
