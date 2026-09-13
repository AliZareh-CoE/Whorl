"""#477 — go to definition in the Studio, backed by the project search."""

from pathlib import Path


def test_studio_wires_go_to_definition():
    studio = Path("frontend/src/app/pages/Studio.tsx").read_text()
    for needle in (
        "const goToDefinition = useCallback",
        'k === "d" && e.shiftKey',
        '{ label: "Go to definition", keys: `${MOD} ⇧ D`',
        "&regex=1&case=1",
        "\\\\\\\\label\\\\{",
    ):
        assert needle in studio, needle
    adapter = Path("frontend/src/editor/index.ts").read_text()
    assert "getCursor: () => { line: number; col: number }" in adapter
    sheet = Path("frontend/src/app/shortcuts.tsx").read_text()
    assert "Go to definition" in sheet and "Find in project" in sheet
