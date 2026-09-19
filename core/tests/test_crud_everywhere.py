"""CRUD sweep (owner report 2026-09-06: "CRUD is missing from the whole project").

Source-level guards so the SPA keeps its edit/delete affordances and never falls back to
native browser dialogs, which the desktop webview can swallow silently.
"""

from pathlib import Path

import pytest

PAGES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "pages"
COMPONENTS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components"


def _src(name: str) -> str:
    return (PAGES / name).read_text()


def test_no_native_browser_dialogs_in_the_spa():
    offenders = []
    for path in list(PAGES.rglob("*.tsx")) + list(Path(PAGES.parent).glob("*.tsx")):
        text = path.read_text()
        for needle in (
            "window.prompt(",
            "window.confirm(",
            "window.alert(",
            " confirm(`",
            " alert(",
        ):
            if needle in text:
                offenders.append(f"{path.name}: {needle.strip()}")
    assert not offenders, offenders


def test_dialog_host_is_mounted_once_at_the_root():
    main = (PAGES.parent / "main.tsx").read_text()
    assert "<DialogHost />" in main
    dialog = (COMPONENTS / "Dialog.tsx").read_text()
    for fn in ("confirmDialog", "promptDialog", "noticeDialog", "errorDialog"):
        assert f"export function {fn}" in dialog


@pytest.mark.parametrize(
    ("page", "needles"),
    [
        (
            "ProjectOverview.tsx",
            ['method: "DELETE"', "verify: name", "Archive", "project-settings"],
        ),
        ("Projects.tsx", ["onContextMenu", "Delete project", "Archive"]),
        (
            "Files.tsx",
            ["onContextMenu", "/folders/${v.id}/", "Upload here", "New folder inside", "F2"],
        ),
        ("Decisions.tsx", ['method: editing ? "PATCH" : "POST"', "/decisions/${id}/"]),
        ("Figures.tsx", ["Rename…", "Delete", "/documents/${f.id}/"]),
        ("Prompts.tsx", ["/prompts/${id}/", "New prompt"]),
        ("Literature.tsx", ["Remove from this project", "priority"]),
        ("Reference.tsx", ["EditReference", "Delete from library"]),
        (
            "Research.tsx",
            ["QuestionsPanel", "/questions/${id}/", "/experiments/${id}/", "/datasets/${id}/"],
        ),
        ("Plan.tsx", ["add-phase", "Delete phase", "Rename…"]),
        ("Writing.tsx", ["Delete manuscript", "/manuscripts/${id}/", "cardItems", "Shelve"]),
        ("Library.tsx", ["rowItems", "Delete from library", "Find metadata", "onContextMenu"]),
    ],
)
def test_pages_expose_edit_and_delete(page, needles):
    text = _src(page)
    missing = [n for n in needles if n not in text]
    assert not missing, f"{page} lost: {missing}"


def test_documents_table_rows_have_in_app_actions():
    text = (COMPONENTS / "DocumentsTable.tsx").read_text()
    for needle in ("rowItems", "Rename…", "Edit description…", "Delete…", "onContextMenu"):
        assert needle in text
    assert "href={doc.editUrl}" not in text  # no more exits to the classic edit page


def test_files_open_from_disk_surfaces_errors_and_can_add_the_file():
    text = _src("Files.tsx")
    assert 'errorDialog("Couldn\'t open a file from disk"' in text
    assert "add-local-file" in text


def test_desktop_open_local_file_is_async():
    # a blocking file picker inside a sync Tauri command runs on the main thread and never
    # shows — the command must be async (owner: "open from disk not working")
    rust = (Path(__file__).resolve().parents[2] / "desktop" / "src" / "localfs.rs").read_text()
    assert "pub async fn open_local_file" in rust
    assert "blocking_pick_file" not in rust
    assert "data_b64" in rust
