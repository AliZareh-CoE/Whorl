"""Explore neighbours from the reading queue (#403, backlog #37)."""

from pathlib import Path

from django.conf import settings


def test_queue_rows_offer_similar_papers():
    src = (Path(settings.BASE_DIR) / "frontend/src/app/pages/Literature.tsx").read_text()
    assert "Similar in your library" in src and 'data-testid="neighbours"' in src
    assert "/related/`" in src and 'action: "link"' in src


def test_listen_is_chunked_and_prefetched():
    """#404 (backlog #38): read-aloud plays sentence chunks and fetches the next while one plays."""
    base = Path(settings.BASE_DIR)
    listen = (base / "frontend/src/app/listen.ts").read_text()
    assert "export function chunkText" in listen and "prefetch the following chunk" in listen
    for page in ("ReadingFlow.tsx", "Reference.tsx"):
        src = (base / "frontend/src/app/pages" / page).read_text()
        assert (
            "listenTo(" in src
            and 'fetch("/tts/"' not in src.split("async function listen")[1].split("\n  }\n")[0]
        )
