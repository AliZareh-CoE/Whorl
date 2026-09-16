"""#557: time in the explorer — tree rows carry `created_at`, `updated_at` and `modified_at`
(when the bytes last changed: the newest version's stamp, not `updated_at`, which a tag or a
move also bumps); the explorer sorts by name / last change / size, stamps rows and the pane,
and lists the last-touched files in a Recent strip."""

from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from documents import history
from documents.models import Document, Tag
from documents.selectors import workspace_tree
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

BASE = Path(settings.BASE_DIR)


def _doc(project, name, body=b"x"):
    return Document.objects.create(
        project=project,
        title=name,
        rel_path=name,
        kind="other",
        file=ContentFile(body, name=name),
        content_type="text/plain",
    )


def _row(project, doc):
    return next(f for f in workspace_tree(project)["files"] if f["id"] == doc.pk)


def test_modified_at_moves_with_the_bytes_not_with_a_tag():
    project = ProjectFactory()
    doc = _doc(project, "a.md")
    row = _row(project, doc)
    assert row["modified_at"] == row["created_at"] == doc.created_at.isoformat()
    assert row["updated_at"] == doc.updated_at.isoformat()
    doc.tags.add(Tag.objects.create(project=project, name="t"))
    doc.description = "tagged, not changed"
    doc.save()
    row = _row(project, doc)
    assert row["modified_at"] == doc.created_at.isoformat()  # a tag / description is not a change
    assert row["updated_at"] > row["modified_at"]
    history.replace_file(doc, SimpleUploadedFile("a.md", b"y", "text/plain"), note="edit")
    row = _row(project, doc)
    version = doc.versions.get(number=1)
    assert row["modified_at"] == version.created_at.isoformat() > row["created_at"]


def test_version_count_survives_the_max_join():
    project = ProjectFactory()
    doc = _doc(project, "a.md")
    for i in range(3):
        history.replace_file(doc, SimpleUploadedFile("a.md", f"v{i}".encode(), "text/plain"))
    row = _row(project, doc)
    assert row["versions"] == 3 and row["version"] == 4


def test_inline_text_nodes_carry_their_size():
    project = ProjectFactory()
    doc = Document.objects.create(
        project=project, title="n.md", rel_path="n.md", kind="other", content="héllo"
    )
    assert doc.file_size == 6  # bytes, not characters
    assert _row(project, doc)["size"] == 6


def test_mcp_docstring_names_the_stamps():
    server = (BASE / "mcp_server" / "server.py").read_text()
    chunk = server.split("def list_project_files(", 1)[1].split("return", 1)[0]
    assert "`created_at` / `modified_at`" in chunk


def test_explorer_sorts_stamps_and_lists_recent():
    files = (BASE / "frontend" / "src" / "app" / "pages" / "Files.tsx").read_text()
    assert "modified_at: string;" in files and "created_at: string;" in files
    # the sort: folders by name always; files by name, newest change first, largest first
    assert 'type SortKey = "name" | "modified" | "size";' in files
    assert (
        'const SORT_KEY = "atlas-files-sort";' in files
        and "localStorage.setItem(SORT_KEY, k)" in files
    )
    assert (
        'sort === "modified" ? (b.modified_at.localeCompare(a.modified_at) || byName(a, b))'
        in files
    )
    assert 'sort === "size" ? ((b.size - a.size) || byName(a, b))' in files
    assert "rootFolders.sort(byName);" in files and "rootFiles.sort(byFile);" in files
    assert "}, [data, tagFilter, sort]);" in files
    assert (
        'data-testid="sort-files"' in files
        and '<option value="modified">Last change</option>' in files
    )
    # rows: the stamp replaces the size only under the "last change" sort; absolute dates in the title
    assert (
        'data-testid="row-stamp"' in files
        and "title={`changed ${stamp(f.modified_at)} · added ${stamp(f.created_at)}" in files
    )
    # the pane's dates line, with the absolute time on hover
    assert (
        'data-testid="pane-dates"' in files
        and "<time dateTime={selected.modified_at} title={stamp(selected.modified_at)}>" in files
    )
    # the Recent strip: top six by the bytes' last change, only for a tree worth a shortcut, hidden under a tag filter
    assert (
        "const recent = total >= 6 ? [...data.files].sort((a, b) => b.modified_at.localeCompare(a.modified_at)).slice(0, 6) : [];"
        in files
    )
    assert "{recent.length > 0 && !tagFilter && (" in files
    for needle in ("recent-strip", "recent-toggle", "recent-file"):
        assert f'data-testid="{needle}"' in files, needle
    assert 'const RECENT_KEY = "atlas-files-recent";' in files
    # clicking a recent file opens every folder above it and selects it
    assert "while (id != null) { open[id] = true; id = parentOfFolder.get(id) ?? null; }" in files
    # relative stamps with week / month / year buckets
    assert (
        "function ago(iso: string, now: number = Date.now()): string" in files and "wk ago" in files
    )
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "sort-files" in chunks and "recent-strip" in chunks and "atlas-files-sort" in chunks
