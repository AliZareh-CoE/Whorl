"""Audit #34 (#558): the test suite writes files under a temp MEDIA_ROOT, never the working
tree's media/; a deleted document or version takes its bytes with it; `prune_media` removes
the files no row references; the three phone-width seams and the constellation labels."""

from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from documents import history
from documents.management.commands.prune_media import orphaned_files, prune
from documents.models import Document
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

BASE = Path(settings.BASE_DIR)


def _doc(project, name="a.txt", body=b"x"):
    return Document.objects.create(
        project=project,
        title=name,
        rel_path=name,
        kind="other",
        file=ContentFile(body, name=name),
        content_type="text/plain",
    )


def test_tests_write_under_a_temp_media_root(tmp_path):
    assert Path(settings.MEDIA_ROOT) == tmp_path / "media"
    doc = _doc(ProjectFactory())
    assert Path(doc.file.path).is_relative_to(tmp_path)
    assert not str(doc.file.path).startswith(str(BASE / "media"))


def test_delete_removes_the_document_and_version_files(django_capture_on_commit_callbacks):
    doc = _doc(ProjectFactory())
    history.replace_file(doc, SimpleUploadedFile("a.txt", b"y", "text/plain"))
    doc.refresh_from_db()
    current = Path(doc.file.path)
    version = Path(doc.versions.get(number=1).file.path)
    assert current.exists() and version.exists()
    with django_capture_on_commit_callbacks(execute=True):
        doc.delete()  # the version row cascades; both hooks fire on commit
    assert not current.exists() and not version.exists()


def test_bulk_delete_removes_files_too(django_capture_on_commit_callbacks):
    from documents.bulk import bulk_documents

    project = ProjectFactory()
    a, b = _doc(project, "a.txt"), _doc(project, "b.txt")
    paths = [Path(a.file.path), Path(b.file.path)]
    with django_capture_on_commit_callbacks(execute=True):
        bulk_documents(project, [a.pk, b.pk], "delete")
    assert not any(p.exists() for p in paths)


def test_prune_media_removes_only_unreferenced_files():
    project = ProjectFactory()
    doc = _doc(project, "kept.txt")
    root = Path(settings.MEDIA_ROOT)
    stray = root / "projects" / project.slug / "documents" / "stray.txt"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"orphan")
    stray_version = root / "projects" / project.slug / "versions" / "999" / "v1-old.txt"
    stray_version.parent.mkdir(parents=True, exist_ok=True)
    stray_version.write_bytes(b"orphan")
    elsewhere = root / "projects" / project.slug / "figures" / "fig.png"  # not ours to touch
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    elsewhere.write_bytes(b"png")
    found = orphaned_files()
    assert set(found) == {
        f"projects/{project.slug}/documents/stray.txt",
        f"projects/{project.slug}/versions/999/v1-old.txt",
    }
    assert prune(apply=False) == (2, 0) and stray.exists()
    assert prune(apply=True) == (2, 2)
    assert not stray.exists() and not stray_version.exists() and not stray_version.parent.exists()
    assert Path(doc.file.path).exists() and elsewhere.exists()


def test_phone_width_seams_and_constellation_labels():
    projects = (BASE / "frontend" / "src" / "app" / "pages" / "Projects.tsx").read_text()
    assert 'className="mb-6 flex flex-wrap items-end justify-between gap-4"' in projects  # 349
    overview = (BASE / "frontend" / "src" / "app" / "pages" / "ProjectOverview.tsx").read_text()
    assert overview.count("[&>*]:min-w-0") == 2  # 350: grid items may shrink below content
    js = (BASE / "static" / "js" / "constellation.js").read_text()
    assert "if (n.label && w >= 640) {" in js  # 351
    css = (BASE / "static" / "css" / "app.css").read_text()
    assert "min-width:0" in css


def test_delete_of_a_fileless_row_is_a_no_op(django_capture_on_commit_callbacks):
    """Inline text nodes and manuscript-source rows carry no storage file; the post_delete
    hook must return before touching storage (an empty name would make it raise)."""
    project = ProjectFactory()
    inline = Document.objects.create(
        project=project, title="n.md", rel_path="n.md", kind="other", content="# hi"
    )
    source = Document.objects.create(
        project=project,
        title="main.tex",
        rel_path="main.tex",
        kind="other",
        role=Document.Role.MANUSCRIPT_SOURCE,
    )
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        inline.delete()
        source.delete()
    assert callbacks == []
    assert not Document.objects.filter(pk__in=[inline.pk, source.pk]).exists()
