"""What Claude reads on every turn (#541): the tool descriptions have a budget.

A description is the tool's docstring. The picker reads its first words, so the headline
(the text before the first period or colon) says what the tool is for; slice numbers are
history for the repository, noise for the model; and the loaded-by-default set has a size.
"""

import re

from mcp_server import server, toolsets

HEADLINE_MAX = 110
DESCRIPTION_MAX = 800
CORE_DESCRIPTION_MAX = 720
CORE_TOTAL_MAX = 5200


def _tools():
    return {t.name: t for t in server._REGISTRY.values()}


def _norm(text: str | None) -> str:
    return " ".join((text or "").split())


def _headline(text: str) -> str:
    m = re.match(r"(.+?)[.:;—(?!]", text)
    return m.group(1) if m else text


def test_every_tool_has_a_description_with_a_short_headline():
    long = {}
    for name, tool in _tools().items():
        text = _norm(tool.description)
        assert text, f"{name} has no description"
        assert text[0].isupper() or text[0] in "\"'`[", f"{name}: {text[:40]!r}"
        if len(_headline(text)) > HEADLINE_MAX:
            long[name] = _headline(text)
    assert not long, long


def test_no_slice_numbers_in_what_claude_reads():
    noisy = {
        n: _norm(t.description)
        for n, t in _tools().items()
        if re.search(r"#\d{2,}\b", t.description or "")
    }
    assert not noisy, noisy


def test_descriptions_stay_under_budget():
    over = {
        n: len(_norm(t.description))
        for n, t in _tools().items()
        if len(_norm(t.description)) > DESCRIPTION_MAX
    }
    assert not over, over


def test_the_default_set_stays_small_in_context():
    tools = _tools()
    sizes = {n: len(_norm(tools[n].description)) for n in toolsets.CORE}
    over = {n: s for n, s in sizes.items() if s > CORE_DESCRIPTION_MAX}
    assert not over, over
    total = sum(sizes.values())
    assert total <= CORE_TOTAL_MAX, f"core descriptions total {total} chars (was 8997 before #541)"


def test_core_tools_say_when_to_use_them():
    """The daily set carries an explicit cue for the picker where the name alone is not one."""
    tools = _tools()
    for name in (
        "get_project_overview",
        "get_dashboard",
        "get_daily_brief",
        "search",
        "browse_library",
        "get_reading_queue",
        "list_toolsets",
        "enable_toolset",
        "get_plan",
    ):
        text = _norm(tools[name].description)
        assert "Use " in text or "Use for" in text or "Use when" in text or "Use before" in text, (
            name
        )
