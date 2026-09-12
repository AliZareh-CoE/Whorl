"""Library v2 workbench (SPA) stays wired: the page, its bundle, and the API it talks to."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_library_page_carries_the_workbench_pieces():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Library.tsx").read_text()
    for needle in (
        "Import from Zotero",
        "/references/facets/",
        "/references/bulk/",
        "/references/import/",
        "/references/import-zotero/",
        "find-metadata",
        "Drop to import",  # whole-page drop zone
        'e.key === "j"',  # keyboard navigation
        "useInfiniteQuery",  # load-more pagination
        "Find metadata",
    ):
        assert needle in src, needle


def test_library_bundle_matches_the_source():
    chunks = " ".join(
        p.read_text(errors="ignore")
        for p in (BASE / "static" / "js" / "islands").glob("Library*.js")
    )
    assert (
        "Import from Zotero" in chunks
        and "/references/facets/" in chunks
        and "Drop to import" in chunks
    )


def test_desktop_freeze_bundles_pypdf():
    spec = (BASE / "desktop" / "server" / "atlas_server.spec").read_text()
    assert '"pypdf"' in spec
