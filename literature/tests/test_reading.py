"""Library v2 slice 7 — structured highlights, reading notes, per-row PDF fetch."""

import pytest

from literature import reading
from literature.models import Highlight, ProjectReference
from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from notes.models import Note
from projects.tests.factories import ProjectFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def paper(db, django_user_model):
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    ref = ReferenceFactory(title="Attention is all you need", bibtex_key="vaswani2017attention")
    ProjectReferenceFactory(project=project, reference=ref)
    return project, ref


def test_add_highlight_mirrors_into_note_and_bumps_status(paper):
    project, ref = paper
    h = reading.add_highlight(ref, "  Multi-head attention  ", page=3, project=project)
    assert h.page == 3 and h.text == "Multi-head attention" and h.color == "yellow"
    note = Note.objects.get(project=project, title="Highlights — vaswani2017attention")
    assert "> Multi-head attention" in note.body and "p.3" in note.body
    assert ref in note.references.all()
    assert ProjectReference.objects.get(project=project, reference=ref).reading_status == "skimmed"


def test_add_highlight_without_project_is_global(paper):
    _, ref = paper
    h = reading.add_highlight(ref, "global passage", color="green")
    assert h.project is None and h.color == "green"
    assert not Note.objects.exists()


def test_add_highlight_validation(paper):
    project, ref = paper
    other = ProjectFactory(slug="other")
    with pytest.raises(reading.HighlightError):
        reading.add_highlight(ref, "   ")
    with pytest.raises(reading.HighlightError):
        reading.add_highlight(ref, "x" * 2001)
    with pytest.raises(reading.HighlightError):
        reading.add_highlight(ref, "not linked", project=other)
    reading.add_highlight(ref, "odd colour", color="chartreuse")
    assert Highlight.objects.get().color == "yellow"


def test_highlights_markdown_and_reading_notes(paper):
    project, ref = paper
    assert "_No highlights yet._" in reading.highlights_markdown(ref)
    reading.add_highlight(ref, "first", page=1, comment="key idea")
    reading.add_highlight(ref, "second\nline", page=2)
    md = reading.highlights_markdown(ref)
    assert md.index("> first") < md.index("> second\n> line")
    assert "— vaswani2017attention, p.1" in md and "\nkey idea" in md
    link = ProjectReference.objects.get(project=project, reference=ref)
    link.notes = "Read for the positional encoding section."
    link.save()
    notes = reading.reading_notes(ref)
    assert notes == [
        {
            "project_reference_id": link.pk,
            "project": "deep",
            "project_name": project.name,
            "reading_status": "skimmed",  # highlighting bumped it from to_read
            "notes": "Read for the positional encoding section.",
        }
    ]


def test_highlights_api_roundtrip(client, paper):
    project, ref = paper
    created = client.post(
        "/api/v1/highlights/",
        {"reference": ref.pk, "text": "scaled dot-product", "page": 4, "project": "deep"},
        content_type="application/json",
        **HEADERS,
    )
    assert created.status_code == 201, created.content
    hid = created.json()["id"]
    assert created.json()["project_name"] == project.name
    bad = client.post(
        "/api/v1/highlights/",
        {"reference": ref.pk, "text": "   "},
        content_type="application/json",
        **HEADERS,
    )
    assert bad.status_code == 400 and "text" in bad.json()
    listed = client.get(f"/api/v1/highlights/?reference={ref.pk}", **HEADERS).json()
    assert listed["count"] == 1 and listed["results"][0]["text"] == "scaled dot-product"
    patched = client.patch(
        f"/api/v1/highlights/{hid}/",
        {"comment": "the core trick"},
        content_type="application/json",
        **HEADERS,
    )
    assert patched.status_code == 200 and patched.json()["comment"] == "the core trick"
    md = client.get(f"/api/v1/references/{ref.pk}/highlights-markdown/", **HEADERS).json()
    assert md["count"] == 1 and "the core trick" in md["markdown"]
    notes = client.get(f"/api/v1/references/{ref.pk}/reading-notes/", **HEADERS).json()
    assert notes[0]["project"] == "deep"
    assert client.delete(f"/api/v1/highlights/{hid}/", **HEADERS).status_code == 204
    assert not Highlight.objects.exists()


def test_fetch_pdf_api(client, paper, monkeypatch):
    _, ref = paper
    monkeypatch.setattr(
        "literature.oa.fetch_and_attach_pdf", lambda reference: "No open-access PDF found."
    )
    out = client.post(f"/api/v1/references/{ref.pk}/fetch-pdf/", **HEADERS)
    assert out.status_code == 200
    assert out.json() == {"outcome": "No open-access PDF found.", "attached": False, "pdf": None}


def test_legacy_reader_highlight_view_writes_structured_row(client, paper):
    project, ref = paper
    client.login(username="owner", password="pw")
    out = client.post(
        f"/library/{ref.pk}/read/highlight/",
        {"project": "deep", "text": "from the reader", "page": 2},
    )
    assert out.status_code == 200, out.content
    h = Highlight.objects.get()
    assert h.project == project and h.page == 2 and h.text == "from the reader"
    assert Note.objects.get(pk=out.json()["note_id"]).body.count("from the reader") == 1


@pytest.mark.django_db
def test_highlight_rects_round_trip_and_validation(client_logged_in):
    from literature.tests.factories import ReferenceFactory

    ref = ReferenceFactory()
    boxes = [{"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.0123456}]
    made = client_logged_in.post(
        "/api/v1/highlights/",
        {"reference": ref.pk, "text": "a passage worth keeping", "page": 2, "rects": boxes},
        content_type="application/json",
    )
    assert made.status_code == 201 and made.json()["rects"] == [
        {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.0123}
    ]
    bad = client_logged_in.post(
        "/api/v1/highlights/",
        {"reference": ref.pk, "text": "bad boxes", "rects": [{"x": 2, "y": 0, "w": 1, "h": 1}]},
        content_type="application/json",
    )
    assert bad.status_code == 400 and "rects" in bad.json()
    assert client_logged_in.get(f"/api/v1/highlights/?reference={ref.pk}").json()["results"][0][
        "rects"
    ]
