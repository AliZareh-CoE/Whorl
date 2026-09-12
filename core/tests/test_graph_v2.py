"""Graph v2 — enriched nodes, stats, and vendored (offline) graph libraries."""

from pathlib import Path

import pytest
from django.conf import settings

from core.graph import project_graph
from literature.models import CitationEdge
from literature.reading import add_highlight
from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from notes.models import Note
from notes.services import sync_note_links
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


def test_graph_libraries_are_vendored_for_the_desktop():
    root = Path(settings.BASE_DIR)
    for name in ("3d-force-graph.min.js", "force-graph.min.js"):
        path = root / "static" / "vendor" / "forcegraph" / name
        assert path.exists() and path.stat().st_size > 100_000, name
    graph_tsx = (root / "frontend" / "src" / "app" / "pages" / "Graph.tsx").read_text()
    classic = (root / "templates" / "projects" / "graph.html").read_text()
    assert "unpkg.com" not in graph_tsx and "unpkg.com" not in classic
    assert "vendor/forcegraph/3d-force-graph.min.js" in graph_tsx
