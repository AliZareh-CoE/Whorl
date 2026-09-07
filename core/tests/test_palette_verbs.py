"""#432: ⌘K creation verbs — paper: <DOI|arXiv>, a bare id, "Add a paper", "New note",
"New manuscript", "New project" — and an honest empty state."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)
APP = BASE / "frontend" / "src" / "app"


def test_command_bar_wiring():
    src = (APP / "CommandBar.tsx").read_text()
    for needle in (
        "const doPaper",
        '"/references/by-doi/"',
        'startsWith("paper:")',
        'startsWith("doi:")',
        "10\\.\\d{4,9}",  # a bare DOI needs no prefix
        "arxiv:",
        '"Add a paper by DOI or arXiv id"',
        '"/library?add=1"',
        '"/writing?new=1"',
        "/notes/new",
        '"/projects/new"',
        'data-testid="palette-empty"',
        "paper: <i>DOI</i>",
    ):
        assert needle in src, needle


def test_focus_params():
    library = (APP / "pages" / "Library.tsx").read_text()
    assert 'get("add")' in library and "ref={doiRef}" in library
    writing = (APP / "pages" / "Writing.tsx").read_text()
    assert 'get("new")' in writing and "ref={titleRef}" in writing


def test_built_bundle_carries_the_verbs():
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "palette-empty" in chunks and "Add a paper by DOI or arXiv id" in chunks
