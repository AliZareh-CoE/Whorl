"""#569: the gallery at a narrow width — the card header is title · actions · meta and wraps
(the buttons stay on the title line, the chips drop under it below `lg`), the toolbar wraps,
the form's two columns start at `lg`, the picker's hit list never runs past the viewport."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_the_card_header_wraps_in_the_source_and_the_chunk():
    src = (BASE / "frontend" / "src" / "app" / "pages" / "Prompts.tsx").read_text()
    for needle in (
        'data-testid="prompt-actions"',
        'data-testid="prompt-meta"',
        "lg:order-last",  # the actions go last only from lg
        "order-last flex min-w-0 basis-full flex-wrap",  # the chips take a line of their own below lg
        "min-w-0 flex-1 basis-0 truncate",  # the title never forces a wrap, and truncates
        "max-w-[calc(100vw-2rem)]",  # the picker's hit list
        '${flip ? "right-0" : "left-0"}',  # …and it hangs from the right edge when it would overflow
        "lg:grid-cols-[minmax(0,1fr)_16rem]",  # the form
        "min-w-0 flex-1 basis-40 max-w-72",  # the search box gives way
        'Next<span className="hidden lg:inline">: ',  # the offered step reads "Next →" below lg
    ):
        assert needle in src, needle
    assert "sm:grid-cols-[minmax(0,1fr)_16rem]" not in src
    # the actions group comes before the meta group in the DOM — flex wraps in DOM order
    assert src.index('data-testid="prompt-actions"') < src.index('data-testid="prompt-meta"')
    chunks = list((BASE / "static" / "js" / "islands").glob("Prompts-chunk*.js"))
    assert chunks, "the Prompts chunk is built"
    built = chunks[0].read_text()
    for needle in ("prompt-actions", "prompt-meta", "lg:order-last"):
        assert needle in built, needle
    css = (BASE / "static" / "css" / "app.css").read_text()
    for needle in ("lg\\:order-last", "basis-full", "max-w-max"):
        assert needle in css, needle  # the stylesheet was rebuilt for the new utilities
