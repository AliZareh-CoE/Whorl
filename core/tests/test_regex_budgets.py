"""Audit #29 — every parser that reads user or remote text must be linear.

A note body is the user's, but a pasted junk file must not hang the save; a page head is the
site's, and a page that never closes a tag must not hang the enrich request. Each case ran
for tens of seconds before the audit; the budget below is generous only to keep CI calm.
"""

import datetime
import time

from core.rendering import render_markdown
from notes.links import title_from_html
from notes.outline import measure, outline
from notes.services import parse_cite_keys, parse_wiki_titles
from notes.tags import parse_tags
from notes.when import parse_when

BUDGET_SECONDS = 1.0


def _under_budget(label, fn):
    started = time.perf_counter()
    fn()
    elapsed = time.perf_counter() - started
    assert elapsed < BUDGET_SECONDS, f"{label} took {elapsed:.2f}s"


def test_wiki_link_parsers_are_linear_on_bracket_runs():
    junk = "[[" * 50_000
    _under_budget("parse_wiki_titles", lambda: parse_wiki_titles(junk))
    _under_budget("outline/measure", lambda: measure(junk))
    assert parse_wiki_titles(junk) == [] and measure(junk)["links"] == 0
    assert parse_wiki_titles("see [[A]] and [[B]] but not [[ [C] ]]") == ["A", "B"]


def test_html_title_reader_is_linear_on_unclosed_tags():
    _under_budget("meta without >", lambda: title_from_html("<html><head>" + "<meta " * 30_000))
    _under_budget("title without </title>", lambda: title_from_html("<title>" * 20_000))
    _under_budget("title never closed", lambda: title_from_html("<title>" + "a" * 250_000))
    assert title_from_html("<meta " * 30_000) == ""
    html = '<meta name="x"><meta property="og:title" content="The Paper"><title>Site</title>'
    assert title_from_html(html) == "The Paper"
    html = '<meta content="Reversed" property="og:title"><title>Site</title>'
    assert title_from_html(html) == "Reversed"


def test_other_text_parsers_stay_under_budget():
    today = datetime.date.today()
    _under_budget("outline spaces", lambda: outline("# " + " " * 50_000))
    _under_budget("parse_tags", lambda: parse_tags("#" * 50_000))
    _under_budget("parse_cite_keys", lambda: parse_cite_keys("@" * 50_000))
    _under_budget("parse_when", lambda: parse_when("next " * 20_000, today))
    _under_budget("render tag lines", lambda: render_markdown("#tag line\n" * 2_000))
    # Audit #30: the #509 research-markdown parsers — math, highlights, callouts, task boxes
    _under_budget("render dollars", lambda: render_markdown("$" * 100_000))
    _under_budget("render display math", lambda: render_markdown("$$" * 50_000))
    _under_budget("render highlights", lambda: render_markdown("==" * 50_000))
    _under_budget("render callouts", lambda: render_markdown("> [!note] " * 20_000))
    # Python-Markdown itself spends ~50 µs per list item (linear); 10 k keeps the check honest
    _under_budget("render task boxes", lambda: render_markdown("- [ ] a\n" * 10_000))
