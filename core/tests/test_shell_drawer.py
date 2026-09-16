"""#552 (backlog 312): below 640 px the SPA's fixed 240-px rail becomes a drawer behind a top
bar, so every page is usable at phone width. Closed on navigation, Escape, a tap outside and
when the window widens; inert while closed so its links leave the tab order; the rail carries
no transform from 640 px up (a `fixed` toast inside a transformed ancestor would pin to it)."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_layout_turns_the_rail_into_a_drawer_below_640():
    layout = (BASE / "frontend" / "src" / "app" / "Layout.tsx").read_text()
    # the CSS's own `sm` query, in rem: a px query would drift from it under a larger default font
    assert (
        'const WIDE = "(min-width: 40rem)";' in layout
        and "!window.matchMedia(WIDE).matches" in layout
    )
    assert "const on = () => setNarrow(!mq.matches);" in layout
    assert "639px" not in layout
    assert (
        'className="flex items-center gap-2.5 max-sm:hidden"' in layout
    )  # one wordmark on a phone
    assert (
        "function useNarrow(): boolean" in layout and 'mq.addEventListener("change", on)' in layout
    )
    # the transform exists only below 640: `max-sm:` variants, never a bare translate
    assert 'railOpen ? "max-sm:translate-x-0" : "max-sm:-translate-x-full"' in layout
    assert "max-sm:transition-transform" in layout and "max-sm:top-12 max-sm:z-[35]" in layout
    assert 'ref={asideRef} id="rail" data-testid="rail"' in layout
    assert (
        "overflow-y-auto" in layout.split('data-testid="rail"', 1)[1].split(">", 1)[0]
    )  # a short landscape phone scrolls the drawer
    # the top bar (hamburger ≥ 40 px, wordmark, ⌘K) only when narrow; the backdrop only when open
    assert "{narrow && (" in layout and 'data-testid="rail-bar"' in layout
    assert 'aria-controls="rail" data-testid="rail-toggle" className="flex h-10 w-10' in layout
    assert 'data-testid="rail-bar-ask"' in layout
    assert "{narrow && railOpen && <button" in layout and 'data-testid="rail-backdrop"' in layout
    assert "fixed inset-0 top-12 z-30 bg-stone-950/40 sm:hidden" in layout
    # closes on navigation, on Escape (focus back to the toggle), when widened; inert while closed
    assert "useEffect(() => { setRailOpen(false); }, [location.pathname]);" in layout
    assert "useEffect(() => { if (!narrow) setRailOpen(false); }, [narrow]);" in layout
    assert 'asideRef.current?.toggleAttribute("inert", narrow && !railOpen)' in layout
    assert "const closeRail = () => { setRailOpen(false); toggleRef.current?.focus(); };" in layout
    assert 'if (e.key === "Escape") { e.preventDefault(); closeRail(); }' in layout
    assert 'asideRef.current?.querySelector<HTMLElement>("nav a")?.focus();' in layout
    # the content column: no rail margin below 640, room for the top bar, tighter padding
    assert '<main className="min-w-0 flex-1 max-sm:pt-12 sm:ml-60">' in layout
    assert "px-4 py-5 sm:px-8 sm:py-7" in layout
    # the unlock toast renders outside the aside (a `fixed` box inside a transform pins to it)
    aside_end = layout.index("</aside>")
    assert layout.index("<UnlockToast unlocks=") > aside_end
    # the hooks sit above the return (React #310 otherwise)
    assert layout.index("const narrow = useNarrow();") < layout.index(
        'return (\n    <div className="flex h-full">'
    )


def test_terminal_dock_and_viewport_follow_the_rail():
    dock = (BASE / "frontend" / "src" / "app" / "TerminalDock.tsx").read_text()
    assert "fixed bottom-0 left-0 right-0 z-30 sm:left-60" in dock
    spa = (BASE / "templates" / "spa.html").read_text()
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in spa


def test_built_assets_carry_the_drawer():
    css = (BASE / "static" / "css" / "app.css").read_text()
    assert "not all and (min-width:40rem)" in css  # how `max-sm:` compiles
    assert "max-sm\\:-translate-x-full" in css and "max-sm\\:translate-x-0" in css
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "rail-toggle" in chunks and "rail-backdrop" in chunks and "(min-width: 40rem)" in chunks
