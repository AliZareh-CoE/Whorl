"""#407 — one renderer for every markdown body: mentions resolve the same way in decisions,
experiment entries, protocols and captures as they do in notes."""

import pytest

from core.rendering import render_body, resolve_mentions
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
