"""#510 — related notes: scoring, exclusions, API, editor wiring."""

from pathlib import Path

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from literature.tests.factories import ReferenceFactory
from notes.models import Note
from notes.related import related_notes, terms
from notes.services import sync_note_links
from notes.tags import sync_note_tags
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def _project():
    p = ProjectFactory(slug="deep")
    a, b = ReferenceFactory(bibtex_key="a2020x"), ReferenceFactory(bibtex_key="b2021y")
    hub = Note.objects.create(
        project=p, title="Load theory", body="perceptual load gates distractor processing #capacity"
    )
    twin = Note.objects.create(
        project=p,
        title="Distractor notes",
        body="distractor processing under perceptual load #capacity #pilot",
    )
    linked = Note.objects.create(
        project=p, title="Linked already", body="see [[Load theory]] distractor load perceptual"
    )
    stranger = Note.objects.create(
        project=p, title="Budget", body="travel money for the conference"
    )
    for n in (hub, twin, linked, stranger):
        sync_note_links(n)
        sync_note_tags(n)
    hub.references.set([a, b])
    twin.references.set([a, b])
    linked.references.set([a])
    return p, hub, twin, linked, stranger


def test_related_notes_score_shared_papers_tags_and_terms_and_skip_linked_notes():
    p, hub, twin, linked, stranger = _project()
    rows = related_notes(hub)
    assert [r["id"] for r in rows] == [twin.pk]  # linked and unrelated notes are left out
    row = rows[0]
    assert row["score"] == 3.0 * 2 + 2.0 + 0.5 * 5  # two papers, one tag, five words
    assert row["reasons"][0] == "cites 2 of the same papers" and row["reasons"][1] == "#capacity"
    assert (
        row["reasons"][2].startswith("shares 5 terms:")
        and row["url"] == f"/projects/deep/notes/{twin.pk}"
    )
    assert related_notes(stranger) == []


def test_related_notes_count_shared_link_targets_and_honour_the_limit():
    p = ProjectFactory(slug="links")
    target = Note.objects.create(project=p, title="Target", body="")
    a = Note.objects.create(project=p, title="A", body="[[Target]]")
    b = Note.objects.create(project=p, title="B", body="[[Target]]")
    c = Note.objects.create(project=p, title="C", body="[[Target]]")
    for n in (target, a, b, c):
        sync_note_links(n)
    rows = related_notes(a)
    assert [r["title"] for r in rows] == ["B", "C"] and rows[0]["reasons"] == [
        "both link to Target"
    ]
    assert len(related_notes(a, limit=1)) == 1 and len(related_notes(a, limit=999)) == 2
    assert terms("Load-theory of attention, the") == {"load", "theory", "load-theory", "attention"}


def test_related_api_and_auth(owner):
    p, hub, twin, linked, stranger = _project()
    client = APIClient(HTTP_HOST="127.0.0.1")
    assert client.get(f"/api/v1/notes/{hub.pk}/related/").status_code == 401
    client.credentials(HTTP_X_API_KEY=settings.ATLAS_API_KEY)
    out = client.get(f"/api/v1/notes/{hub.pk}/related/?limit=3").json()
    assert [r["id"] for r in out] == [twin.pk]
    assert client.get(f"/api/v1/notes/{hub.pk}/related/?limit=abc").status_code == 400
    assert client.get("/api/v1/notes/999999/related/").status_code == 404


def test_editor_has_the_related_panel_with_a_link_action():
    tsx = (Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Notes.tsx").read_text()
    for needle in (
        'data-testid="related-panel"',
        'data-testid="related-row"',
        'data-testid="related-link"',
        "See also [[${t}]]",
        '"note-related", id',
    ):
        assert needle in tsx, needle
