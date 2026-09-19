"""#560 (backlog 355): the selection behaves like a Finder selection — drag moves every checked
file, Duplicate copies a file (or the selection) next to itself with a numbered name and no
shared storage, `untag` completes the bulk verbs, and Claude gets `organize_files` (by tree
path) after `export_bibtex` folded into `export_references`."""

import json
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile

from documents import bulk
from documents.models import Document, DocumentVersion, Folder, Tag
from mcp_server import client as mcp_client
from projects.tests.factories import ProjectFactory
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db

BASE = Path(settings.BASE_DIR)
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _doc(project, name, folder=None, body=b"x", content="", tags=(), description=""):
    doc = Document.objects.create(
        project=project,
        folder=folder,
        title=name,
        rel_path=f"{bulk.folder_path(folder)}/{name}" if folder else name,
        kind="other",
        file=ContentFile(body, name=name) if body is not None else None,
        content=content,
        content_type="text/plain",
        description=description,
    )
    doc.tags.set(tags)
    return doc


class TestDuplicate:
    def test_copy_lands_next_to_the_original_with_its_metadata_and_no_history(self):
        project = ProjectFactory()
        data = Folder.objects.create(project=project, name="Data")
        tag = Tag.objects.create(project=project, name="key-paper")
        doc = _doc(project, "rt.csv", data, b"a,b\n1,2\n", tags=[tag], description="Pilot")
        DocumentVersion.objects.create(document=doc, number=1, content="old", file_size=3)
        copy = bulk.duplicate_document(doc)
        assert copy.rel_path == "Data/rt-2.csv" and copy.title == "rt-2.csv"
        assert copy.folder_id == data.pk and copy.description == "Pilot"
        assert list(copy.tags.values_list("name", flat=True)) == ["key-paper"]
        assert copy.version == 1 and copy.versions.count() == 0
        assert copy.file.read() == b"a,b\n1,2\n" and copy.file_size == 8
        assert bulk.duplicate_document(doc).rel_path == "Data/rt-3.csv"

    def test_copy_never_shares_storage_with_the_original(self, django_capture_on_commit_callbacks):
        project = ProjectFactory()
        doc = _doc(project, "notes.txt", body=b"hello")
        copy = bulk.duplicate_document(doc)
        assert copy.file.name != doc.file.name
        path = Path(copy.file.path)
        with django_capture_on_commit_callbacks(execute=True):
            doc.delete()
        assert path.read_bytes() == b"hello"

    def test_inline_text_copies_content_without_a_file(self):
        project = ProjectFactory()
        doc = _doc(project, "readme.md", body=None, content="# hi")
        copy = bulk.duplicate_document(doc)
        assert not copy.file and copy.content == "# hi" and copy.file_size == 4
        assert copy.rel_path == "readme-2.md"

    def test_available_name_counts_only_the_same_folder(self):
        project = ProjectFactory()
        data = Folder.objects.create(project=project, name="Data")
        _doc(project, "a.txt")
        _doc(project, "a-2.txt")
        assert bulk.available_name(project, None, "a.txt") == "a-3.txt"
        assert bulk.available_name(project, data, "a.txt") == "a.txt"
        _doc(project, "Makefile")
        assert bulk.available_name(project, None, "Makefile") == "Makefile-2"


class TestBulkVerbs:
    def test_duplicate_and_untag_through_the_service(self):
        project = ProjectFactory()
        tag = Tag.objects.create(project=project, name="t")
        a = _doc(project, "a.txt", tags=[tag])
        b = _doc(project, "b.txt", tags=[tag])
        m = ManuscriptFactory(project=project)
        m.files.create(path="main.tex", content="x", kind="tex", is_main=True)
        source = project.documents.get(role="manuscript_source")
        out = bulk.bulk_documents(project, [a.pk, b.pk, source.pk], "duplicate")
        assert out["count"] == 2 and out["skipped"] == [source.pk] and len(out["created"]) == 2
        assert project.documents.filter(rel_path__in=["a-2.txt", "b-2.txt"]).count() == 2
        out = bulk.bulk_documents(project, [a.pk], "untag", tag=tag)
        assert out == {"action": "untag", "count": 1, "skipped": []}
        assert a.tags.count() == 0 and b.tags.count() == 1
        with pytest.raises(bulk.BulkError):
            bulk.bulk_documents(project, [a.pk], "untag")

    def test_api_duplicate_answers_the_copies(self, client):
        project = ProjectFactory()
        a = _doc(project, "a.txt")
        url = f"/api/v1/projects/{project.slug}/documents/bulk/"
        r = client.post(url, json.dumps({"ids": [a.pk], "action": "duplicate"}), **JSON)
        assert r.status_code == 200 and r.json()["count"] == 1
        copy = Document.objects.get(pk=r.json()["created"][0])
        assert copy.rel_path == "a-2.txt"
        r = client.post(url, json.dumps({"ids": [a.pk], "action": "copy"}), **JSON)
        assert r.status_code == 400
        assert client.post(url, "{}", content_type="application/json").status_code == 401


class TestMcp:
    def test_export_bibtex_folded_into_export_references(self):
        server = (BASE / "mcp_server" / "server.py").read_text()
        assert "def export_bibtex(" not in server and "def organize_files(" in server
        assert not hasattr(mcp_client, "export_bibtex")

    def test_organize_files_resolves_paths_folders_and_tags(self, monkeypatch):
        calls = []
        tree = {
            "folders": [
                {"id": 1, "name": "Data", "parent_id": None},
                {"id": 2, "name": "Pilot", "parent_id": 1},
            ],
            "files": [
                {"id": 10, "rel_path": "Data/rt.csv"},
                {"id": 11, "rel_path": "readme.md"},
            ],
        }

        def fake(method, path, **kw):
            calls.append((method, path, kw))
            if path.endswith("/tree/"):
                return tree
            if path == "/tags/":
                return {"results": [{"id": 5, "name": "key-paper", "count": 1}]}
            return {"action": "ok"}

        monkeypatch.setattr(mcp_client, "_request", fake)
        mcp_client.organize_files("p", ["Data/rt.csv", "/readme.md/"], "move", folder="Data/Pilot")
        assert calls[-1] == (
            "POST",
            "/projects/p/documents/bulk/",
            {"json": {"ids": [10, 11], "action": "move", "folder": 2}},
        )
        mcp_client.organize_files("p", ["readme.md"], "move")
        assert calls[-1][2]["json"]["folder"] is None
        mcp_client.organize_files("p", ["readme.md"], "untag", tag="Key-Paper")
        assert calls[-1][2]["json"] == {"ids": [11], "action": "untag", "tag": 5}
        mcp_client.organize_files("p", ["readme.md"], "duplicate")
        assert calls[-1][2]["json"] == {"ids": [11], "action": "duplicate"}
        with pytest.raises(ValueError, match="No file at nope.txt"):
            mcp_client.organize_files("p", ["nope.txt"], "delete")
        with pytest.raises(ValueError, match="No folder at Elsewhere"):
            mcp_client.organize_files("p", ["readme.md"], "move", folder="Elsewhere")
        with pytest.raises(ValueError, match="Name the tag"):
            mcp_client.organize_files("p", ["readme.md"], "tag")
        with pytest.raises(ValueError, match="action must be"):
            mcp_client.organize_files("p", ["readme.md"], "rename")
        with pytest.raises(ValueError, match="at least one"):
            mcp_client.organize_files("p", [""], "delete")

    def test_organize_files_restore_and_purge_resolve_paths_from_the_trash(self, monkeypatch):
        # backlog 357: `delete` is into the Trash; restore / purge name what was deleted
        calls = []
        tree = {
            "folders": [],
            "files": [{"id": 11, "rel_path": "readme.md"}],
            "trash": [
                {"id": 20, "rel_path": "Data/rt.csv"},
                {"id": 19, "rel_path": "Data/rt.csv"},  # an older deletion at the same path
                {"id": 21, "rel_path": "old.txt"},
            ],
        }

        def fake(method, path, **kw):
            calls.append((method, path, kw))
            return tree if path.endswith("/tree/") else {"action": "ok"}

        monkeypatch.setattr(mcp_client, "_request", fake)
        mcp_client.organize_files("p", ["Data/rt.csv", "old.txt"], "restore")
        assert calls[-1][2]["json"] == {"ids": [20, 21], "action": "restore"}  # newest wins
        mcp_client.organize_files("p", ["old.txt"], "purge")
        assert calls[-1][2]["json"] == {"ids": [21], "action": "purge"}
        with pytest.raises(ValueError, match="No file at readme.md in the Trash of p"):
            mcp_client.organize_files("p", ["readme.md"], "restore")
        with pytest.raises(ValueError, match="No file at old.txt in p"):
            mcp_client.organize_files("p", ["old.txt"], "delete")  # a trashed path is not live


def test_explorer_drags_the_selection_and_duplicates():
    files = (BASE / "frontend" / "src" / "app" / "pages" / "Files.tsx").read_text()
    body = files.split("export default function Files()", 1)[1]
    # a checked row drags the whole selection; the drop parses a list and routes many through bulk
    assert (
        "const dragIds = (f: FileNode): number[] => (checked.has(f.id) ? [...checked] : [f.id]);"
        in body
    )
    assert 'raw.split(",").map(Number).filter(Boolean)' in body
    assert 'else bulk.mutate({ action: "move", folder, ids });' in body
    assert body.count("droppedIds(e.dataTransfer") == 2
    # Duplicate: the menu (⌘D), the bar, the key; copies become the selection
    for needle in (
        "hint: `${MOD} D`",
        'data-testid="bulk-duplicate"',
        'e.key.toLowerCase() === "d"',
        "setChecked(new Set(r.created ?? []))",
    ):
        assert needle in body, needle
    sheet = (BASE / "frontend" / "src" / "app" / "shortcuts.tsx").read_text()
    assert 'title: "Files"' in sheet and "Duplicate the file or the selection" in sheet
    chunk = (BASE / "static" / "js" / "islands" / "Files-chunk.js").read_text()
    assert "bulk-duplicate" in chunk
