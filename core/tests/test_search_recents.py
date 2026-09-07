"""#435 (backlog #55): the Search page remembers recent searches and lets you pin one."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_search_page_wiring():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Search.tsx").read_text()
    for needle in (
        'RECENTS_KEY = "atlas-search-recents"',
        'PINS_KEY = "atlas-search-pins"',
        "RECENTS_MAX = 8",
        'data-testid="search-pin"',
        'data-testid="search-pinned"',
        'data-testid="search-recent"',
        'data-testid="search-saved"',
        "aria-pressed={pinned}",
        "try {",  # localStorage reads and writes are guarded
    ):
        assert needle in src, needle
    chunks = " ".join(
        p.read_text(errors="ignore")
        for p in (BASE / "static" / "js" / "islands").glob("Search*.js")
    )
    assert "atlas-search-pins" in chunks and "search-recent" in chunks
