"""Density-width guard (Backlog #195, pairs with #183).

The dense list/table/dashboard pages get their roomy max-w-6xl column by extending
base_wide.html. If one is copied from an older template or hand-edited back to a bare
`{% extends "base.html" %}`, its width silently regresses to base.html's max-w-5xl. This
grep test fails the build in that case so the #25 density rhythm can't quietly drift.
"""

from pathlib import Path

from django.conf import settings

TEMPLATES = Path(settings.BASE_DIR) / "templates"

WIDE_PAGES = (
    "core/dashboard.html",
    "documents/index.html",
    "literature/index.html",
    "literature/matrix.html",
    "literature/project_literature.html",
    "literature/reading_queue.html",
    "plans/plan.html",
    "projects/overview.html",
    "writing/home.html",
    "research/ledger.html",
    "research/datasets.html",
    "research/experiments.html",
)


def test_dense_pages_extend_base_wide():
    offenders = []
    for page in WIDE_PAGES:
        text = (TEMPLATES / page).read_text()
        if '{% extends "base_wide.html" %}' not in text:
            offenders.append(page)
    assert not offenders, (
        "These dense pages must extend base_wide.html for the max-w-6xl column:\n"
        + "\n".join(offenders)
    )


def test_dense_pages_do_not_redeclare_main_class():
    # the whole point of base_wide is to OWN the width (#183); a page re-declaring
    # main_class is either redundant or silently fighting the shared column (#196).
    offenders = []
    for page in WIDE_PAGES:
        text = (TEMPLATES / page).read_text()
        if "{% block main_class %}" in text:
            offenders.append(page)
    assert not offenders, (
        "These pages extend base_wide.html but re-declare main_class — let the base own it:\n"
        + "\n".join(offenders)
    )


def test_base_wide_sets_the_wide_column():
    text = (TEMPLATES / "base_wide.html").read_text()
    assert '{% extends "base.html" %}' in text
    assert "max-w-6xl" in text
    # the extends must be the first tag, else every child 500s (the #183 gotcha)
    assert text.lstrip().startswith('{% extends "base.html" %}')
