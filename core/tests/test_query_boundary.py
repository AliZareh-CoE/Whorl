"""#409 (backlog #282): no SPA page may fetch without an error branch.

A page whose query fails must show `ErrorState` (with a retry), not a skeleton forever. The
shared `queryGate` / `QueryBoundary` gives that for one line; this guard catches the next page
that forgets. Pages whose queries only decorate an otherwise-static page are allowlisted.
"""

from pathlib import Path

from django.conf import settings

PAGES = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"
# optional data on a page that renders fine without it (a form's template list, a widget's
# extra numbers, an editor whose queries each have their own fallback)
OPTIONAL = {
    "NewProject.tsx",
    "Studio.tsx",
    "library/PdfReader.tsx",
    "plan/Focus.tsx",
    "plan/Roadmap.tsx",
    "project/Constellation.tsx",
}


def test_every_querying_page_has_an_error_branch():
    missing = []
    for path in sorted(PAGES.rglob("*.tsx")):
        rel = path.relative_to(PAGES).as_posix()
        src = path.read_text()
        if "useQuery({" not in src or rel in OPTIONAL:
            continue
        if not any(needle in src for needle in ("queryGate(", "<QueryBoundary", "<ErrorState")):
            missing.append(rel)
    assert not missing, f"pages that query without an error state: {missing}"


def test_gate_component_exists():
    src = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "components" / "QueryBoundary.tsx"
    ).read_text()
    assert "export function queryGate" in src and "export function QueryBoundary" in src
    assert "onRetry" in src  # a failed load always offers a retry
