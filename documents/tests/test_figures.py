"""Figure-gallery data layer (Backlog #8 — API-first slice)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from documents.models import Document, Tag
from documents.selectors import project_figures
from documents.tests.factories import FolderFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _image_doc(project, name, ct, **kw):
    doc = Document.objects.create(
        project=project, title=name, file=SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\n"), **kw
    )
    Document.objects.filter(pk=doc.pk).update(content_type=ct)
    return Document.objects.get(pk=doc.pk)


def test_project_figures_returns_only_raster_images():
    project = ProjectFactory()
    _image_doc(project, "plot.png", "image/png")
    _image_doc(project, "scan.jpg", "image/jpeg")
    _image_doc(project, "diagram.svg", "image/svg+xml")  # excluded: script-bearing
    _image_doc(project, "notes.txt", "text/plain")  # excluded: not an image

    figs = project_figures(project)
    titles = {f["title"] for f in figs}
    assert titles == {"plot.png", "scan.jpg"}


def test_project_figures_excludes_other_projects():
    project = ProjectFactory()
    other = ProjectFactory()
    _image_doc(project, "mine.png", "image/png")
    _image_doc(other, "theirs.png", "image/png")
    assert {f["title"] for f in project_figures(project)} == {"mine.png"}


def test_project_figures_includes_folder_and_tags():
    project = ProjectFactory()
    folder = FolderFactory(project=project, name="Results")
    tag = Tag.objects.create(project=project, name="fig2")
    doc = _image_doc(project, "result.png", "image/png", folder=folder)
    doc.tags.add(tag)

    fig = project_figures(project)[0]
    assert fig["folder"] == "Results"
    assert fig["folder_id"] == folder.id
    assert fig["tags"] == ["fig2"]
    assert fig["content_type"] == "image/png"


def test_project_figures_newest_first():
    project = ProjectFactory()
    a = _image_doc(project, "old.png", "image/png")
    b = _image_doc(project, "new.png", "image/png")
    # force a deterministic ordering by created_at
    Document.objects.filter(pk=a.pk).update(created_at="2026-01-01T00:00:00Z")
    Document.objects.filter(pk=b.pk).update(created_at="2026-06-01T00:00:00Z")
    titles = [f["title"] for f in project_figures(project)]
    assert titles == ["new.png", "old.png"]


def test_figures_endpoint_serves_raw_urls(client):
    project = ProjectFactory()
    doc = _image_doc(project, "plot.png", "image/png")
    data = client.get(f"/api/v1/projects/{project.slug}/figures/", **HEADERS).json()
    assert len(data) == 1
    assert data[0]["title"] == "plot.png"
    assert data[0]["raw_url"].endswith(f"/api/v1/documents/{doc.id}/raw/")


def test_figures_endpoint_requires_api_key(client):
    project = ProjectFactory()
    assert client.get(f"/api/v1/projects/{project.slug}/figures/").status_code == 401


def test_figures_query_count_is_bounded(client, django_assert_max_num_queries):
    project = ProjectFactory()
    for i in range(5):
        _image_doc(project, f"f{i}.png", "image/png")
    # the queryset is one SELECT + one prefetch for tags (+ auth/project lookups); no per-row N+1
    with django_assert_max_num_queries(8):
        project_figures(project)
