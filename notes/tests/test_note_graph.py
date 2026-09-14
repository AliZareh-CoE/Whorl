"""#503 — the subgraph around one note."""

from pathlib import Path

import pytest

from core.graph import note_neighbourhood
from literature.models import ProjectReference
from literature.tests.factories import ReferenceFactory
from notes.models import Note
from notes.services import sync_note_links, sync_note_references
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def _web():
    p = ProjectFactory(slug="attention")
    paper = ReferenceFactory(bibtex_key="lavie2010load", title="Load")
    ProjectReference.objects.create(project=p, reference=paper)
    a = Note.objects.create(project=p, title="A", body="[[B]] and @lavie2010load")
    b = Note.objects.create(project=p, title="B", body="[[C]]")
    c = Note.objects.create(project=p, title="C", body="[[D]]")
    d = Note.objects.create(project=p, title="D", body="")
    Note.objects.create(project=p, title="Island", body="alone")
    e = Note.objects.create(project=p, title="E", body="[[A]]")  # links *to* A
    for n in (a, b, c, d, e):
        sync_note_links(n)
        sync_note_references(n)
    return p, a, b, c, d, e, paper


def test_note_neighbourhood_walks_both_directions_and_stops_at_depth():
    p, a, b, c, d, e, paper = _web()
    out = note_neighbourhood(a, depth=2)
    ids = {n["id"]: n["hops"] for n in out["nodes"]}
    assert ids == {
        f"note-{a.pk}": 0,
        f"note-{b.pk}": 1,
        f"note-{e.pk}": 1,
        f"ref-{paper.pk}": 1,
        f"note-{c.pk}": 2,
    }
    assert out["nodes"][0]["id"] == f"note-{a.pk}"  # the note itself first
    assert out["stats"] == {"notes": 3, "references": 1, "links": 4}
    assert out["note"] == {"id": a.pk, "title": "A"} and out["depth"] == 2
    assert {(edge["source"], edge["target"]) for edge in out["links"]} == {
        (f"note-{a.pk}", f"note-{b.pk}"),
        (f"note-{b.pk}", f"note-{c.pk}"),
        (f"note-{e.pk}", f"note-{a.pk}"),
        (f"note-{a.pk}", f"ref-{paper.pk}"),
    }
    one = note_neighbourhood(a, depth=1)
    assert {n["hops"] for n in one["nodes"]} == {0, 1} and one["stats"]["notes"] == 2
    assert note_neighbourhood(a, depth=99)["depth"] == 3  # clamped
    deep = note_neighbourhood(a, depth=3)
    assert f"note-{d.pk}" in {n["id"] for n in deep["nodes"]}
    assert "Island" not in {n["label"] for n in deep["nodes"]}


def test_note_graph_api_and_editor_panel(client, settings, django_user_model):
    p, a, *_ = _web()
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("atlas", "a@b.c", "atlas")
    hdr = {"HTTP_X_API_KEY": "k", "HTTP_HOST": "127.0.0.1"}
    r = client.get(f"/api/v1/notes/{a.id}/graph/?depth=1", **hdr)
    assert r.status_code == 200 and r.json()["depth"] == 1 and len(r.json()["nodes"]) == 4
    assert client.get(f"/api/v1/notes/{a.id}/graph/?depth=x", **hdr).status_code == 400
    assert client.get(f"/api/v1/notes/{a.id}/graph/", HTTP_HOST="127.0.0.1").status_code == 401
    tsx = Path("frontend/src/app/pages/Notes.tsx").read_text()
    for needle in ('data-testid="local-graph"', "/graph/?depth=", "force-graph.min.js"):
        assert needle in tsx, needle
