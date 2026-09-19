"""Backlog 358 (#577): the Files pane edits a text file in a CodeMirror editor — line numbers,
undo, search, Markdown / LaTeX highlighting, ⌘S — saves it as a new version with an optional
note, and shows what changed right after. Source and bundle pins; the endpoint's contract is
in test_preview_endpoints.py."""

from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
FRONT = BASE / "frontend" / "src"


def test_the_code_editor_is_a_light_codemirror_with_a_save_key():
    src = (FRONT / "components" / "CodeEditor.tsx").read_text()
    for needle in (
        'key: "Mod-s"',
        "return true; }",  # ⌘S never opens the browser's own save dialog
        "lineNumbers()",
        "history()",
        "search()",
        'data-testid="code-editor"',
        "md-editor",  # the Observatory palette through the notes editor's variables
        "markdown({ base: markdownLanguage })",
        "latex()",
    ):
        assert needle in src, needle
    assert "onSaveRef.current?.()" in src  # ⌘S reads the note as it is now, not at mount
    assert 'from "../editor"' not in src and "mountEditor" not in src  # not the Studio's
    md = (FRONT / "app" / "notes" / "MarkdownEditor.tsx").read_text()
    assert "export const theme" in md and "export const highlight" in md


def test_the_pane_wires_editing_saving_and_the_diff():
    files = (FRONT / "app" / "pages" / "Files.tsx").read_text()
    # the editor loads only when Edit is clicked
    assert 'const CodeEditor = lazy(() => import("../../components/CodeEditor"));' in files
    for needle in (
        'data-testid="edit-file"',
        'data-testid="save-file"',
        'data-testid="save-note"',
        'data-testid="unsaved"',
        'data-testid="saved-strip"',
        'data-testid="edit-as-text"',
        "Saved as v{lastSave.version}",
        "<VersionDiff file={selected} number={lastSave.filed} />",
        "Nothing changed — the file is as it was.",
        'window.addEventListener("beforeunload", warn)',
        "body: JSON.stringify({ content: draft, note: note.trim().slice(0, 200) })",
    ):
        assert needle in files, needle
    # a save bumps the pane's version (its key) — the strip lives in Files and survives
    assert (
        "setSelectedRaw((s) => (s && s.id === a.id && a.saved ? { ...s, version: a.version" in files
    )
    # the file-switch guard wraps the setter; every caller still uses setSelected
    assert "const [selected, setSelectedRaw] = useState<FileNode | null>(null);" in files
    assert 'title: "Discard the unsaved changes?"' in files
    assert (
        files.count("setSelectedRaw(") == 3
    )  # the guard's two calls and the save bump; everything else goes through the guard
    # the state hooks sit above the component's early return (React #310)
    assert files.index("const [lastSave, setLastSave]") < files.rindex("if (isLoading)\n")
    sheet = (FRONT / "app" / "shortcuts.tsx").read_text()
    assert "Save the file you are editing (as a new version)" in sheet


def test_the_bundle_carries_the_editor_and_the_strip():
    islands = BASE / "static" / "js" / "islands"
    files = (islands / "Files-chunk.js").read_text()
    assert "saved-strip" in files and "save-note" in files and "edit-as-text" in files
    assert "What changed? (optional)" in files
    editor = "".join(p.read_text() for p in islands.glob("CodeEditor*.js"))
    assert "code-editor" in editor and "Mod-s" in editor
