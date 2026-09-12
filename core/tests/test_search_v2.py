"""Search v2 — explained hits: snippet, page for PDF hits, SPA links."""

import pytest
from django.core.files.base import ContentFile

from core.management.commands.seed_demo import make_demo_pdf
from core.search import describe, excerpt
from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from notes.models import Note
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def test_excerpt_windows_around_the_term():
    text = "alpha " * 40 + "the DISSOCIATION matters here " + "omega " * 40
    out = excerpt(text, "dissociation", radius=20)
    assert out.startswith("…") and out.endswith("…") and "DISSOCIATION" in out and len(out) < 60
    assert excerpt("short text", "zzz") == "short text" and excerpt("", "x") == ""
    assert excerpt("x" * 500, '"quoted phrase" -neg', radius=10).endswith("…")


def test_search_api_explains_hits(client, settings, django_user_model, tmp_path):
    settings.ATLAS_API_KEY = "k"
    settings.MEDIA_ROOT = tmp_path
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep", name="Deep")
    ref = ReferenceFactory(
        title="Load theory",
        abstract="Nothing relevant here.",
        authors=[{"family": "Lavie"}],
        year=2010,
    )
    ref.pdf.save(
        "l.pdf",
        ContentFile(make_demo_pdf(["The dissociation between load types matters."])),
        save=True,
    )
    ProjectReferenceFactory(project=project, reference=ref)
    Note.objects.create(
        project=project,
        title="Thinking",
        body="A long note about the dissociation and more words after it.",
    )
    out = client.get("/api/v1/search/?q=dissociation", HTTP_X_API_KEY="k").json()
    by_type = {r["type"]: r for r in out["results"]}
    paper = by_type["reference"]
    assert (
        paper["where"] == "in the PDF" and paper["page"] == 1 and "dissociation" in paper["snippet"]
    )
    assert paper["app_url"] == f"/references/{ref.pk}" and paper["meta"].startswith("Lavie · 2010")
    note = by_type["note"]
    assert (
        note["app_url"].endswith("/notes/") is False and "/projects/deep/notes/" in note["app_url"]
    )
    assert "dissociation" in note["snippet"] and note["project_name"] == "Deep"
    # describe() falls back to the abstract when the term is not in the PDF
    row = {"type": "reference", "object": ref, "project": None}
    assert (
        describe(row, "relevant")["snippet"].startswith("Nothing relevant")
        and describe(row, "relevant")["page"] is None
    )
