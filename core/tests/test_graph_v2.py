"""Graph v2 — enriched nodes, stats, and vendored (offline) graph libraries."""

import datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

from core.graph import project_graph
from literature.models import CitationEdge, ProjectReference
from literature.reading import add_highlight
from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from notes.models import Note
from notes.services import sync_note_links
from notes.tags import sync_note_tags
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def test_graph_nodes_carry_facts_and_stats():
    project = ProjectFactory(slug="deep")
    a = ReferenceFactory(bibtex_key="a2020", title="A", citation_count=100, year=2020)
    b = ReferenceFactory(bibtex_key="b2021", title="B", year=2021)
    lonely = ReferenceFactory(bibtex_key="c2022", title="C")
    for r in (a, b, lonely):
        ProjectReferenceFactory(
            project=project, reference=r, reading_status="read" if r is a else "to_read"
        )
    CitationEdge.objects.create(citing=b, cited=a)
    add_highlight(a, "a passage", page=2)
    hub = Note.objects.create(project=project, title="Hub", body="see [[Leaf]] " + "w " * 40)
    leaf = Note.objects.create(project=project, title="Leaf", body="")
    sync_note_links(hub)
    hub.references.add(a)
    g = project_graph(project)
    by_id = {n["id"]: n for n in g["nodes"]}
    ra = by_id[f"ref-{a.pk}"]
    assert (ra["group"], ra["year"], ra["citations"], ra["highlights"], ra["degree"]) == (
        "read",
        2020,
        100,
        1,
        2,
    )
    assert ra["app_url"] == f"/references/{a.pk}" and ra["has_pdf"] is False
    nh = by_id[f"note-{hub.pk}"]
    assert (
        nh["words"] == 42
        and nh["degree"] == 2
        and nh["app_url"] == f"/projects/deep/notes/{hub.pk}"
    )
    assert by_id[f"ref-{lonely.pk}"]["degree"] == 0
    assert g["stats"]["references"] == 3 and g["stats"]["notes"] == 2 and g["stats"]["links"] == 3
    assert g["stats"]["by_kind"] == {"citation": 1, "note-link": 1, "note-citation": 1}
    assert g["stats"]["orphans"] == 1
    assert g["stats"]["hubs"][0]["degree"] == 2 and by_id[f"note-{leaf.pk}"]["degree"] == 1


def test_graph_nodes_carry_filing_days_and_tags_for_the_time_lapse():
    """#506: a paper's node dates from the day it was filed into *this* project (the
    ProjectReference), a note's from its creation; note nodes carry their #tags; stats bound
    the time-lapse with first/last."""
    project = ProjectFactory(slug="time")
    old_paper = ReferenceFactory(bibtex_key="old1999", title="Old")
    new_paper = ReferenceFactory(bibtex_key="new2024", title="New")
    early = ProjectReferenceFactory(project=project, reference=old_paper)
    ProjectReferenceFactory(project=project, reference=new_paper)
    ProjectReference.objects.filter(pk=early.pk).update(  # etag: ok — test backdates a filing
        created_at=timezone.now() - datetime.timedelta(days=40)
    )
    note = Note.objects.create(project=project, title="Tagged", body="a thought #pilot #method")
    sync_note_tags(note)
    g = project_graph(project)
    by_id = {n["id"]: n for n in g["nodes"]}
    day_40 = (timezone.now() - datetime.timedelta(days=40)).date().isoformat()
    today = timezone.now().date().isoformat()
    assert by_id[f"ref-{old_paper.pk}"]["created_at"] == day_40
    assert by_id[f"ref-{new_paper.pk}"]["created_at"] == today
    assert by_id[f"note-{note.pk}"]["created_at"] == today
    assert by_id[f"note-{note.pk}"]["tags"] == ["method", "pilot"]
    assert (g["stats"]["first"], g["stats"]["last"]) == (day_40, today)
    # an empty project has no range
    assert project_graph(ProjectFactory(slug="void"))["stats"]["first"] is None


def test_graph_page_has_the_time_lapse_and_tag_filter():
    graph_tsx = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Graph.tsx"
    ).read_text()
    for needle in (
        'data-testid="graph-timeline"',
        'data-testid="timeline-play"',
        'data-testid="timeline-slider"',
        'data-testid="timeline-caption"',
        'data-testid="tag-filter"',
        "n.created_at <= cursorIso",  # the time filter
        "tagged && !tagged.has(n.id)",  # the tag dimming
        "graphRef.current?.graphData(visible)",  # data flows in without rebuilding the graph
        "nodeCache",  # …and node objects persist so positions hold
    ):
        assert needle in graph_tsx, needle


def test_graph_libraries_are_vendored_for_the_desktop():
    root = Path(settings.BASE_DIR)
    for name in ("3d-force-graph.min.js", "force-graph.min.js"):
        path = root / "static" / "vendor" / "forcegraph" / name
        assert path.exists() and path.stat().st_size > 100_000, name
    graph_tsx = (root / "frontend" / "src" / "app" / "pages" / "Graph.tsx").read_text()
    classic = (root / "templates" / "projects" / "graph.html").read_text()
    assert "unpkg.com" not in graph_tsx and "unpkg.com" not in classic
    assert "vendor/forcegraph/3d-force-graph.min.js" in graph_tsx


def test_graph_pages_share_the_constellation_renderer():
    """#511: one star painter for the 2D graph page and the note's local graph; the 3D page
    uses glow sprites only when the vendored bundle exposes THREE."""
    root = Path(settings.BASE_DIR) / "frontend" / "src" / "app"
    stars = (root / "graph" / "stars.ts").read_text()
    for name in (
        "export function drawStar",
        "export function drawStarfield",
        "export function paintStarArea",
        "export function glowSprite",
        "export function hexAlpha",
    ):
        assert name in stars, name
    graph = (root / "pages" / "Graph.tsx").read_text()
    assert 'from "../graph/stars"' in graph and ".nodeCanvasObject(paintNode)" in graph
    assert ".nodePointerAreaPaint(" in graph and ".onRenderFramePre(" in graph
    assert "if (window.THREE) g.nodeThreeObject(" in graph  # never assumes THREE is there
    notes = (root / "pages" / "Notes.tsx").read_text()
    assert 'from "../graph/stars"' in notes and "drawStar(ctx, n.x, n.y, r" in notes
