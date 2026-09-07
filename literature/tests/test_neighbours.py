"""Explore neighbours from the reading queue (#403, backlog #37)."""

from pathlib import Path

from django.conf import settings


def test_queue_rows_offer_similar_papers():
    src = (Path(settings.BASE_DIR) / "frontend/src/app/pages/Literature.tsx").read_text()
    assert "Similar in your library" in src and 'data-testid="neighbours"' in src
    assert "/related/`" in src and 'action: "link"' in src
