"""#445 (backlog #124): a \\cite fragment that matches nothing offers to add the paper."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_editor_core_offers_add_paper_when_nothing_matches():
    src = (BASE / "frontend" / "src" / "editor" / "index.ts").read_text()
    for needle in (
        "onAddPaper?: (fragment: string, replace: (key: string) => void) => void",
        "const looksLikePaperId",
        "Add a paper by DOI or arXiv id…",
        "nothing in the library matches",
        "filter: false",
        "matched.length === 0 || looksLikePaperId(frag)",
    ):
        assert needle in src, needle


def test_studio_adds_links_and_cites():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Studio.tsx").read_text()
    for needle in (
        "onAddPaper: async (fragment, replace)",
        '"/references/by-doi/"',
        "project: m.project",
        "cite-library/`, { reference: String(ref.id) }",
        "replace(linked.key || ref.bibtex_key)",
        "reloadCiteLibrary()",
    ):
        assert needle in src, needle
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "Add a paper by DOI or arXiv id" in chunks
