"""Small polish (#402): the active nav icon tint and the typeahead miss feedback stay wired."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_active_nav_icon_tint_and_typeahead_miss():
    layout = (BASE / "frontend/src/app/Layout.tsx").read_text()
    assert "[&>svg]:text-indigo-600" in layout
    files = (BASE / "frontend/src/app/pages/Files.tsx").read_text()
    assert "setTypedMiss(true)" in files and 'data-testid="typeahead-hint"' in files
    assert ".typeahead-miss" in (BASE / "assets/css/app.css").read_text()


def test_files_rows_drag_to_move():
    """#410: a file row is draggable; folder rows and the root accept it through moveDoc."""
    files = (BASE / "frontend/src/app/pages/Files.tsx").read_text()
    assert 'DOC_MIME = "application/x-atlas-doc"' in files
    assert 'draggable={f.role !== "manuscript_source"}' in files
    assert files.count("e.dataTransfer.getData(DOC_MIME)") == 2  # folder rows + root
    assert "moveDoc.mutate({ id: movedId, folder: folder.id })" in files
    assert "moveDoc.mutate({ id: movedId, folder: null })" in files


def test_notes_read_aloud():
    """#412: the note editor reads the note through the chunked listener, markdown stripped."""
    notes = (BASE / "frontend/src/app/pages/Notes.tsx").read_text()
    assert 'data-testid="note-listen"' in notes and "listenTo(text, (index, total)" in notes
    assert "speakable(`${title}. ${bodyRef.current}`)" in notes
    assert "useEffect(() => stopListening, [id])" in notes  # switching notes stops the voice
    listen = (BASE / "frontend/src/app/listen.ts").read_text()
    assert "export function speakable(markdown: string): string" in listen


def test_narrow_width_overflow_fixes():
    """#420: the 900 px audit found three sideways scrolls; these are the fixes."""
    assert (
        'className="relative overflow-x-auto"'
        in (BASE / "frontend/src/components/DocumentsTable.tsx").read_text()
    )
    writing = (BASE / "frontend/src/app/pages/Writing.tsx").read_text()
    assert writing.count('className="min-w-0 space-y-4"') == 2
    lit = (BASE / "frontend/src/app/pages/Literature.tsx").read_text()
    assert 'className="mb-6 flex flex-wrap items-end justify-between gap-4"' in lit


def test_documents_sparse_state():
    """#421 (backlog #178): a near-empty documents table explains itself and offers the next step."""
    table = (BASE / "frontend/src/components/DocumentsTable.tsx").read_text()
    assert 'data-testid="documents-sparse"' in table and "documents.length <= 3" in table
    assert 'data-testid="documents-upload-cta"' in table
    assert (
        "filesUrl={`/projects/${slug}/files`}"
        in (BASE / "frontend/src/app/pages/Documents.tsx").read_text()
    )


def test_shortcuts_sheet():
    """#425: ? opens the cheat sheet; the palette has the verb; text fields are exempt."""
    sheet = (BASE / "frontend/src/app/shortcuts.tsx").read_text()
    assert (
        'data-testid="shortcuts-sheet"' in sheet and "export function installShortcutsKey" in sheet
    )
    assert 'el.closest(".cm-editor")' in sheet  # typing ? in the editor never opens it
    assert "installShortcutsKey();" in (BASE / "frontend/src/app/Layout.tsx").read_text()
    assert 'label: "Keyboard shortcuts"' in (BASE / "frontend/src/app/CommandBar.tsx").read_text()
