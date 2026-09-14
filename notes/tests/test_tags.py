"""#504 — #tags in notes."""

from pathlib import Path

import pytest

from notes.models import Note
from notes.services import suggest
from notes.tags import parse_tags, project_tags, sync_note_tags
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def test_parse_tags_reads_inline_tags_and_skips_headings_code_and_anchors():
    body = """# Heading is not a tag
## Neither is this #heading-looking one? no: this line is a heading
Pilot #method notes, #Pilot/v2 and #to-discuss. Twice: #method.
See https://example.org/page#section and issue #123 and C# code.
`#not-in-code` and
```
#nor-in-a-block
```
Trailing punctuation #ends-here."""
    assert parse_tags(body) == ["method", "pilot/v2", "to-discuss", "ends-here"]
    assert parse_tags("") == [] and parse_tags("#a") == []  # a single letter is not a tag


def test_sync_and_project_tags_count_and_order(client, settings, django_user_model):
    p = ProjectFactory(slug="attention")
    a = Note.objects.create(project=p, title="A", body="#method #pilot")
    b = Note.objects.create(project=p, title="B", body="#method only")
    c = Note.objects.create(project=p, title="C", body="no tags")
    for n in (a, b, c):
        sync_note_tags(n)
    a.refresh_from_db()
    assert a.tags == ["method", "pilot"] and Note.objects.get(pk=c.pk).tags == []
    assert project_tags(p) == [{"tag": "method", "count": 2}, {"tag": "pilot", "count": 1}]
    assert [r["label"] for r in suggest(p, "", kind="tag")] == ["method", "pilot"]
    assert [r["label"] for r in suggest(p, "#pi", kind="tag")] == ["pilot"]

    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("atlas", "a@b.c", "atlas")
    hdr = {"HTTP_X_API_KEY": "k", "HTTP_HOST": "127.0.0.1"}
    r = client.get("/api/v1/notes/?project=attention&tag=%23pilot", **hdr)
    assert [n["title"] for n in r.json()["results"]] == ["A"]
    assert r.json()["results"][0]["tags"] == ["method", "pilot"]
    r = client.get("/api/v1/notes/tags/?project=attention", **hdr)
    assert r.status_code == 200 and r.json()["tags"][0] == {"tag": "method", "count": 2}
    assert client.get("/api/v1/notes/tags/?project=nope", **hdr).status_code == 400
    r = client.get("/api/v1/notes/suggest/?project=attention&kind=tag&q=me", **hdr)
    assert [row["label"] for row in r.json()] == ["method"]  # the editor's # completion
    assert (
        client.get("/api/v1/notes/tags/?project=attention", HTTP_HOST="127.0.0.1").status_code
        == 401
    )
    # saving through the API keeps the tags in step
    r = client.patch(
        f"/api/v1/notes/{b.id}/", {"body": "now #draft"}, content_type="application/json", **hdr
    )
    assert r.json()["tags"] == ["draft"]
    r = client.post(
        "/api/v1/notes/",
        {"project": "attention", "title": "D", "body": "#new-one"},
        content_type="application/json",
        **hdr,
    )
    assert r.status_code == 201 and r.json()["tags"] == ["new-one"]
    tsx = Path("frontend/src/app/pages/Notes.tsx").read_text()
    for needle in ('data-testid="tag-chip"', "/notes/tags/?project=", 'data-testid="note-tags"'):
        assert needle in tsx, needle
    editor = Path("frontend/src/app/notes/MarkdownEditor.tsx").read_text()
    assert "tagSource" in editor and '"tag"' in editor
