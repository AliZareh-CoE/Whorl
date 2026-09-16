"""#551: Today at narrow widths — the rows measure against their own column (a container
query, so the fixed rail is not the yardstick), a chip group that does not fit drops under
the text instead of squeezing it, the snooze menu stays inside its row, hover-only controls
show on a coarse pointer, and the last row's menu is no longer clipped by the panel."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_today_rows_wrap_against_their_column():
    today = (BASE / "frontend" / "src" / "app" / "pages" / "Today.tsx").read_text()
    assert '<div className="@container mx-auto max-w-2xl">' in today  # one container for every row
    # three row kinds, one wrap-aware chip group each: under the text below a 32-rem column,
    # inline from it; the indent (the tick's width) stays at every width
    meta = "order-last flex min-w-0 basis-full flex-wrap items-center gap-1 @lg:order-none @lg:basis-auto"
    assert (
        today.count(
            f'className={{`{meta} ${{drag ? "pl-[3.75rem]" : "pl-9"}}`}} data-testid="todo-meta"'
        )
        == 1
    )
    assert today.count(f'className="{meta} pl-8" data-testid="todo-meta"') == 2  # Later, Logbook
    assert "@lg:pl-0" not in today
    # the group is rendered only when it has something to show (an empty flex line is not free)
    assert (
        "const meta = !!old || (!t.done && (!!t.repeat || (!!t.due_at && showsDue(t.due_at, t.all_day)))) || !!t.project;"
        in today
    )
    assert "function showsDue(iso: string, allDay: boolean): boolean" in today
    # the text keeps a 13-rem floor (#522's rule) from a 32-rem column; below it the text shrinks
    # so the action buttons share its line (a 334-px column cannot hold both)
    assert (
        today.count('data-testid="todo-text"') == 3
        and today.count("min-w-0 @lg:min-w-[13rem] flex-1") == 3
    )
    # the actions are one group placed before the chips, so a tight row drops the chips, not them
    assert today.count('data-testid="todo-actions"') == 2  # today + done rows share Row; Later
    for name in ("function LaterRow", "function Row("):
        chunk = today.split(name, 1)[1]
        assert chunk.index('data-testid="todo-actions"') < chunk.index('data-testid="todo-meta"'), (
            name
        )
    log = today.split("function LogRow", 1)[1].split("function RepeatChip", 1)[0]
    assert log.index('aria-label="Delete"') < log.index('data-testid="todo-meta"')


def test_today_menu_controls_and_headers():
    today = (BASE / "frontend" / "src" / "app" / "pages" / "Today.tsx").read_text()
    assert "max-w-[calc(100%-1.5rem)]" in today and "calc(100vw" not in today  # bounded by the row
    # every hover-only control shows on a phone (no hover there)
    assert today.count("opacity-0 transition-opacity pointer-coarse:opacity-100") == 8
    assert "opacity-0 transition-opacity hover" not in today
    # the panel no longer clips the last row's menu: the rows round their own corners …
    assert "first:rounded-t-2xl last:rounded-b-2xl" in today
    assert "<section className={`${panel} rise relative z-[3]`}" in today
    assert (
        'className={`border-b border-stone-100 bg-stone-50/60 px-4 py-1.5 ${i === 0 ? "rounded-t-2xl" : ""}'
        in today
    )
    # … and the sections stack top first (the rise animation leaves a transform on each;
    # any positive z outranks those, and small values stay under every fixed overlay)
    assert (
        'className="rise relative z-[2] mt-5"' in today
        and 'className="rise relative z-[1] mt-5"' in today
    )
    assert (
        today.count(
            'className="mb-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1"'
        )
        == 3
    )


def test_built_css_carries_the_container_and_pointer_rules():
    css = (BASE / "static" / "css" / "app.css").read_text()
    assert "@container (min-width:32rem)" in css and "(pointer:coarse)" in css
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert (
        "@container" in chunks and "todo-meta" in chunks and "pointer-coarse:opacity-100" in chunks
    )
