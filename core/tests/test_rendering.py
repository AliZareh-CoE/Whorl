"""#407 — one renderer for every markdown body: mentions resolve the same way in decisions,
experiment entries, protocols and captures as they do in notes."""

import pytest

from core.rendering import render_body, render_markdown, resolve_mentions
from literature.models import Reference
from notes.models import Note, QuickCapture
from projects.models import DecisionRecord, Project
from research.models import ExperimentEntry, Protocol

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def world():
    project = Project.objects.create(name="Attention")
    other = Project.objects.create(name="Other")
    note = Note.objects.create(project=project, title="Load theory overview", body="x")
    Note.objects.create(project=other, title="Load theory overview", body="y")  # same title
    ref = Reference.objects.create(
        title='Attention, "distraction" and load', bibtex_key="lavie2010attention", year=2010
    )
    return project, other, note, ref


def test_project_scoped_wiki_links_and_cite_keys(world):
    project, _, note, ref = world
    out = resolve_mentions("See [[load theory overview]] and @lavie2010attention.", project)
    assert f"[load theory overview]({note.get_absolute_url()})" in out
    assert (
        f"[@lavie2010attention]({ref.get_absolute_url()} \"Attention, 'distraction' and load\")"
        in out
    )
    html = render_body("See [[Load theory overview]]", project)
    assert (
        f'<a href="{note.get_absolute_url()}" rel="noopener noreferrer">Load theory overview</a>'
        in html
    )


def test_unresolved_mentions_are_visible_gaps(world):
    project, *_ = world
    assert resolve_mentions("[[Nothing here]] and @nobody2099", project) == (
        "*[[Nothing here]]* and *@nobody2099*"
    )
    # without a project an ambiguous title (two projects) stays unresolved
    assert resolve_mentions("[[Load theory overview]]") == "*[[Load theory overview]]*"


def test_render_body_sanitizes_and_soft_breaks(world):
    project, *_ = world
    html = render_body("<script>alert(1)</script>**bold**\nnext", project)
    assert "<script>" not in html and "<strong>bold</strong>" in html and "<br" not in html
    assert "<br" in render_body("one\ntwo", project, soft_breaks=True)
    assert render_body("", project) == ""


def test_api_html_companions(client, world, django_user_model):
    django_user_model.objects.create_superuser("owner", password="pw")  # the key maps to them
    project, _, note, ref = world
    DecisionRecord.objects.create(
        project=project,
        title="Dual task",
        context="Because [[Load theory overview]]",
        decision="Adopt it (@lavie2010attention).",
        alternatives="- single task\n- nothing",
    )
    ExperimentEntry.objects.create(
        project=project, title="Pilot", body="See [[Load theory overview]]"
    )
    Protocol.objects.create(
        project=project, title="Dual-task procedure", body="1. brief @lavie2010attention"
    )
    QuickCapture.objects.create(text="read @lavie2010attention\nthen [[Load theory overview]]")

    d = client.get(f"/api/v1/decisions/?project={project.slug}", **HEADERS).json()["results"][0]
    assert f'href="{note.get_absolute_url()}"' in d["context_html"]
    assert (
        ref.get_absolute_url() in d["decision_html"]
        and "<li>single task</li>" in d["alternatives_html"]
    )
    e = client.get(f"/api/v1/experiments/?project={project.slug}", **HEADERS).json()["results"][0]
    assert note.get_absolute_url() in e["body_html"]
    p = client.get(f"/api/v1/protocols/?project={project.slug}", **HEADERS).json()["results"][0]
    assert "<ol>" in p["body_html"] and ref.get_absolute_url() in p["body_html"]
    c = client.get("/api/v1/quick-capture/", **HEADERS).json()["results"][0]
    # no project on a capture → global resolution: the paper links, the ambiguous title does not
    assert ref.get_absolute_url() in c["text_html"] and "<br" in c["text_html"]
    assert "<em>[[Load theory overview]]</em>" in c["text_html"]


def test_ui_wiring():
    from pathlib import Path

    from django.conf import settings

    pages = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"
    assert (
        "export function Prose"
        in (Path(settings.BASE_DIR) / "frontend" / "src" / "components" / "Prose.tsx").read_text()
    )
    decisions = (pages / "Decisions.tsx").read_text()
    for needle in ("decision_html", 'data-testid="decision-body"', 'data-testid="decision-expand"'):
        assert needle in decisions, needle
    research = (pages / "Research.tsx").read_text()
    for needle in ('testId="experiment-body"', 'testId="protocol-body"', "body_html"):
        assert needle in research, needle
    assert 'testId="capture-text"' in (pages / "Inbox.tsx").read_text()


def test_a_tag_at_the_start_of_a_line_is_not_a_heading():
    """#507: `#pilot #method` on its own line stays prose; real headings still render."""
    html = render_markdown("## Next\n\n#pilot #method\n\n# Title")
    assert "<h2>Next</h2>" in html and "<h1>Title</h1>" in html
    assert "<p>#pilot #method</p>" in html


def test_research_markdown_math_is_lifted_and_marked_for_katex():
    """#509: `$a_i$` keeps its underscores, display math becomes its own block, dollars in
    prose and code stay dollars."""
    html = render_markdown(
        "Let $a_i + b_j$ hold and\n\n$$\nx^2_{ij} < \\alpha\n$$\n\ncosts $5 and $6, `$HOME`"
    )
    assert '<span class="math-inline">a_i + b_j</span>' in html
    assert '<div class="math-display">x^2_{ij} &lt; \\alpha</div>' in html
    assert "<em>" not in html
    assert "costs $5 and $6" in html and "<code>$HOME</code>" in html


def test_research_markdown_tasks_callouts_footnotes_and_highlights():
    body = (
        "- [ ] open\n- [x] done\n\n> [!warning] Careful\n> body here\n\n> [!wat]\n> unknown kind\n\n"
        "Text[^1] with ==a mark==.\n\n[^1]: The note."
    )
    html = render_markdown(body)
    assert '<li class="task"><input type="checkbox" disabled> open' in html
    assert '<li class="task task-done"><input type="checkbox" disabled checked> done' in html
    assert (
        '<blockquote class="callout callout-warning"><p class="callout-title">Careful</p><p>body here'
        in html
    )
    assert (
        '<blockquote class="callout callout-note"><p class="callout-title">Note</p><p>unknown kind'
        in html
    )
    assert '<sup id="fnref:1"><a class="footnote-ref" href="#fn:1"' in html
    assert '<li id="fn:1">' in html and "<mark>a mark</mark>" in html


def test_research_markdown_sanitizer_keeps_only_our_classes_and_ids():
    html = render_markdown(
        '<div class="callout" id="x" onclick="1">a</div><input type="text"><p class="evil<b>">d</p>'
        '<sup id="fnref:9">c</sup><span class="a b">ok</span>'
    )
    assert '<div class="callout">a</div>' in html and "onclick" not in html and 'id="x"' not in html
    assert "<input" not in html and "<p>d</p>" in html
    assert '<sup id="fnref:9">c</sup>' in html and '<span class="a b">ok</span>' in html


def test_katex_is_vendored_and_wired_into_prose():
    from pathlib import Path

    from django.conf import settings

    root = Path(settings.BASE_DIR)
    vendor = root / "static" / "vendor" / "katex"
    assert (vendor / "katex.min.js").exists() and (vendor / "katex.min.css").exists()
    assert len(list((vendor / "fonts").glob("*.woff2"))) >= 15
    prose = (root / "frontend" / "src" / "components" / "Prose.tsx").read_text()
    # Audit #30: KaTeX must stay untrusted — `trust: true` would let \\href carry javascript:
    assert "trust" not in prose
    assert "vendor/katex/katex.min.js" in prose and ".math-inline, .math-display" in prose
    assert (
        "useMath(ref, html)" in prose.split("if (!html) return null")[0]
    )  # hooks above the early return
    notes = (root / "frontend" / "src" / "app" / "pages" / "Notes.tsx").read_text()
    assert 'testId="note-preview"' in notes and "<Prose html={preview.data?.html" in notes
