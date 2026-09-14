"""#507 — the shape and size of a note: outline + measure, API, MCP-facing payload, editor."""

from pathlib import Path

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from notes.models import Note
from notes.outline import measure, note_outline, outline
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

BODY = """# Pilot
Intro text with [[Plan]] and @lavie2010load, again [[Plan]].

## Setup ##
```
# not a heading, inside a fence
- [ ] not a task either
```
   ### Anomalies
####### seven hashes is prose
#no-space is a tag, not a heading

## Next
- [x] counterbalance
- [ ] re-run P4
1. [ ] write it up
* [X] upper-case x counts as done
"""


def test_outline_lists_headings_outside_fences_with_line_numbers():
    assert outline(BODY) == [
        {"level": 1, "text": "Pilot", "line": 1},
        {"level": 2, "text": "Setup", "line": 4},
        {"level": 3, "text": "Anomalies", "line": 9},
        {"level": 2, "text": "Next", "line": 13},
    ]
    assert outline("") == [] and outline("plain text\n#tag only") == []


def test_measure_counts_words_minutes_links_citations_and_tasks():
    m = measure(BODY)
    assert m["words"] == len(BODY.split()) and m["characters"] == len(BODY)
    assert m["minutes"] == 1 and m["headings"] == 4
    assert m["links"] == 1 and m["citations"] == 1  # distinct
    assert m["tasks"] == {"done": 2, "total": 4}  # the fenced box is not a task
    assert measure("") == {
        "words": 0,
        "characters": 0,
        "minutes": 0,
        "headings": 0,
        "links": 0,
        "citations": 0,
        "tasks": {"done": 0, "total": 0},
    }
    assert measure("w " * 401)["minutes"] == 3  # 401 words at 200 wpm rounds up


def test_outline_api_and_auth(owner):
    project = ProjectFactory(slug="deep")
    note = Note.objects.create(project=project, title="Pilot", body=BODY)
    client = APIClient(HTTP_HOST="127.0.0.1")
    assert client.get(f"/api/v1/notes/{note.pk}/outline/").status_code == 401
    client.credentials(HTTP_X_API_KEY=settings.ATLAS_API_KEY)
    out = client.get(f"/api/v1/notes/{note.pk}/outline/").json()
    assert out == note_outline(note)
    assert [h["text"] for h in out["outline"]] == ["Pilot", "Setup", "Anomalies", "Next"]
    assert out["measure"]["tasks"] == {"done": 2, "total": 4}
    assert client.get("/api/v1/notes/999999/outline/").status_code == 404


def test_editor_has_the_outline_pane_and_the_measure_line():
    root = Path(settings.BASE_DIR)
    notes_tsx = (root / "frontend" / "src" / "app" / "pages" / "Notes.tsx").read_text()
    editor_tsx = (root / "frontend" / "src" / "app" / "notes" / "MarkdownEditor.tsx").read_text()
    for needle in (
        'data-testid="outline-panel"',
        'data-testid="outline-row"',
        'data-testid="note-measure"',
        "editorHandle.current?.goToLine(line)",
        "Math.ceil(words / 200)",  # the same reading speed as notes/outline.py
        "if (items.length < 2) return null",  # one heading is a title, not a structure
    ):
        assert needle in notes_tsx, needle
    assert "goToLine: (line: number) =>" in editor_tsx and "scrollIntoView(pos" in editor_tsx
