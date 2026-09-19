"""Backlog 357: a Trash for deleted files — a deleted document waits thirty days out of every
list and count with its bytes and history intact, comes back into the folder it left (or the
root, or under a numbered name), and is swept for good after that. The same shape as the
Today Trash (#570)."""

from datetime import timedelta
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone

from documents import bulk, history, trash
from documents.management.commands.prune_media import orphaned_files
from documents.models import Document, DocumentVersion, Folder
from documents.selectors import workspace_tree
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}
BASE = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _doc(project, name, folder=None, body=b"x"):
    return Document.objects.create(
        project=project,
        folder=folder,
        title=name,
        rel_path=f"{bulk.folder_path(folder)}/{name}" if folder else name,
        kind="other",
        file=ContentFile(body, name=name),
    )


class TestManagers:
    def test_the_default_manager_hides_the_trash_everywhere(self):
        project = ProjectFactory()
        live, gone = _doc(project, "live.txt"), _doc(project, "gone.txt")
        trash.trash(gone)
        assert list(Document.objects.all()) == [live]
        assert set(Document.all_objects.all()) == {live, gone}
        assert list(project.documents.all()) == [live]  # reverse relations too
        assert list(Document.objects.general()) == [live]  # the queryset helpers survive
        tree = workspace_tree(project)
        assert [f["id"] for f in tree["files"]] == [live.pk]
        assert [t["id"] for t in tree["trash"]] == [gone.pk]
        from core.achievements import gather_facts

        assert gather_facts()["documents"] == 1

    def test_trash_and_restore_keep_the_row_its_bytes_and_its_history(
        self, django_capture_on_commit_callbacks
    ):
        project = ProjectFactory()
        folder = Folder.objects.create(project=project, name="Data")
        doc = _doc(project, "rt.csv", folder=folder, body=b"v1")
        history.replace_file(doc, ContentFile(b"v2", name="rt.csv"), note="fixed")
        path = Path(doc.file.path)
        before = doc.updated_at
        with django_capture_on_commit_callbacks(execute=True):
            trash.trash(doc)
        doc.refresh_from_db()
        assert doc.deleted_at is not None and doc.updated_at > before  # the ETag moves
        assert path.read_bytes() == b"v2" and doc.versions.count() == 1  # nothing unlinked
        trash.restore(doc)
        doc.refresh_from_db()
        assert doc.deleted_at is None
        assert (doc.folder_id, doc.rel_path, doc.version) == (folder.pk, "Data/rt.csv", 2)
        assert trash.restore(doc) is doc  # already live: unchanged

    def test_restore_lands_in_the_root_when_the_folder_is_gone(self):
        project = ProjectFactory()
        folder = Folder.objects.create(project=project, name="Data")
        doc = _doc(project, "rt.csv", folder=folder)
        trash.trash(doc)
        folder.delete()  # the collector sees the trashed row too: folder → null
        doc = Document.all_objects.get(pk=doc.pk)
        assert doc.folder_id is None and doc.rel_path == "Data/rt.csv"
        trash.restore(doc)
        doc.refresh_from_db()
        assert doc.rel_path == "rt.csv"

    def test_restore_takes_a_numbered_name_when_a_new_file_took_its_path(self):
        project = ProjectFactory()
        folder = Folder.objects.create(project=project, name="Data")
        old = _doc(project, "rt.csv", folder=folder)
        trash.trash(old)
        new = _doc(project, "rt.csv", folder=folder)  # only live rows are seen: no clash
        trash.restore(old)
        old.refresh_from_db()
        assert (old.title, old.rel_path) == ("rt-2.csv", "Data/rt-2.csv")
        assert new.rel_path == "Data/rt.csv"
        assert project.documents.count() == 2

    def test_prune_removes_only_what_waited_thirty_days_and_unlinks_its_bytes(
        self, django_capture_on_commit_callbacks
    ):
        project = ProjectFactory()
        old, fresh = _doc(project, "old.txt", body=b"old"), _doc(project, "fresh.txt")
        history.replace_file(old, ContentFile(b"old2", name="old.txt"))
        paths = [Path(old.file.path)] + [Path(v.file.path) for v in old.versions.all()]
        trash.trash(old)
        trash.trash(fresh)
        Document.all_objects.filter(pk=old.pk).update(
            deleted_at=timezone.now() - timedelta(days=trash.TRASH_DAYS + 1)
        )  # etag: ok
        with django_capture_on_commit_callbacks(execute=True):
            assert trash.prune_trash() == 1
        assert set(Document.all_objects.values_list("pk", flat=True)) == {fresh.pk}
        assert not DocumentVersion.objects.filter(document_id=old.pk).exists()
        assert not any(p.exists() for p in paths)
        assert trash.prune_trash() == 0

    def test_empty_takes_the_whole_project_trash_and_nothing_else(self):
        project, other = ProjectFactory(), ProjectFactory()
        a, b = _doc(project, "a.txt"), _doc(project, "b.txt")
        c = _doc(other, "c.txt")
        for d in (a, b, c):
            trash.trash(d)
        assert trash.empty(project) == 2
        assert set(Document.all_objects.values_list("pk", flat=True)) == {c.pk}

    def test_the_media_sweep_still_counts_a_trashed_file_as_referenced(self):
        project = ProjectFactory()
        doc = _doc(project, "keep.txt")
        trash.trash(doc)
        assert doc.file.name not in orphaned_files()


class TestBulkVerbs:
    def test_delete_trashes_restore_and_purge_reach_the_trash(self):
        project = ProjectFactory()
        a, b = _doc(project, "a.md"), _doc(project, "b.md")
        out = bulk.bulk_documents(project, [a.pk, b.pk], "delete")
        assert out["count"] == 2
        assert not project.documents.exists() and Document.all_objects.count() == 2
        # a live id is never purged: it is skipped and reported
        live = _doc(project, "live.md")
        out = bulk.bulk_documents(project, [a.pk, live.pk], "purge")
        assert out == {"action": "purge", "count": 1, "skipped": [live.pk]}
        assert not Document.all_objects.filter(pk=a.pk).exists()
        out = bulk.bulk_documents(project, [b.pk, live.pk, 999_999], "restore")
        assert out == {"action": "restore", "count": 1, "skipped": [live.pk]}
        b.refresh_from_db()
        assert b.deleted_at is None


class TestApi:
    def test_delete_trashes_forever_deletes_and_the_list_splits(self, client):
        project = ProjectFactory()
        doc = _doc(project, "a.txt")
        assert client.delete(f"/api/v1/documents/{doc.pk}/", **HEADERS).status_code == 204
        doc = Document.all_objects.get(pk=doc.pk)
        assert doc.deleted_at is not None
        live = client.get(f"/api/v1/documents/?project={project.slug}", **HEADERS).json()
        assert live["count"] == 0
        gone = client.get(f"/api/v1/documents/?project={project.slug}&trash=true", **HEADERS).json()
        assert [r["id"] for r in gone["results"]] == [doc.pk]
        assert gone["results"][0]["deleted_at"] is not None
        # a trashed row still previews (read) but takes no edit (409)
        assert client.get(f"/api/v1/documents/{doc.pk}/", **HEADERS).status_code == 200
        resp = client.patch(f"/api/v1/documents/{doc.pk}/", {"title": "b.txt"}, **JSON)
        assert resp.status_code == 409 and "Trash" in resp.json()["detail"]
        resp = client.put(f"/api/v1/documents/{doc.pk}/content/", {"content": "x"}, **JSON)
        assert resp.status_code == 409
        # a second DELETE (or ?forever=true) removes it for good
        assert client.delete(f"/api/v1/documents/{doc.pk}/", **HEADERS).status_code == 204
        assert not Document.all_objects.filter(pk=doc.pk).exists()
        other = _doc(project, "c.txt")
        assert (
            client.delete(f"/api/v1/documents/{other.pk}/?forever=true", **HEADERS).status_code
            == 204
        )
        assert not Document.all_objects.filter(pk=other.pk).exists()

    def test_restore_and_empty_trash(self, client):
        project = ProjectFactory()
        a, b = _doc(project, "a.txt"), _doc(project, "b.txt")
        trash.trash(a)
        trash.trash(b)
        resp = client.post(f"/api/v1/documents/{a.pk}/restore/", **HEADERS)
        assert resp.status_code == 200 and resp.json()["deleted_at"] is None
        assert resp.json()["title"] == "a.txt"
        resp = client.post(f"/api/v1/documents/{a.pk}/restore/", **HEADERS)  # idempotent
        assert resp.status_code == 200
        resp = client.post(f"/api/v1/projects/{project.slug}/documents/empty-trash/", **HEADERS)
        assert resp.status_code == 200 and resp.json() == {"deleted": 1}
        assert set(Document.all_objects.values_list("pk", flat=True)) == {a.pk}

    def test_bulk_restore_and_purge_over_the_api(self, client):
        project = ProjectFactory()
        a, b = _doc(project, "a.txt"), _doc(project, "b.txt")
        url = f"/api/v1/projects/{project.slug}/documents/bulk/"
        resp = client.post(url, {"ids": [a.pk, b.pk], "action": "delete"}, **JSON)
        assert resp.status_code == 200 and resp.json()["count"] == 2
        resp = client.post(url, {"ids": [a.pk], "action": "restore"}, **JSON)
        assert resp.json() == {"action": "restore", "count": 1, "skipped": []}
        resp = client.post(url, {"ids": [b.pk, a.pk], "action": "purge"}, **JSON)
        assert resp.json() == {"action": "purge", "count": 1, "skipped": [a.pk]}

    def test_the_tree_carries_the_trash(self, client):
        project = ProjectFactory()
        folder = Folder.objects.create(project=project, name="Data")
        doc = _doc(project, "rt.csv", folder=folder)
        trash.trash(doc)
        tree = client.get(f"/api/v1/projects/{project.slug}/tree/", **HEADERS).json()
        assert tree["files"] == []
        (row,) = tree["trash"]
        assert (row["id"], row["name"], row["folder"], row["rel_path"]) == (
            doc.pk,
            "rt.csv",
            "Data",
            "Data/rt.csv",
        )
        assert row["deleted_at"]

    def test_the_classic_delete_view_trashes(self, client_logged_in):
        from django.urls import reverse

        project = ProjectFactory()
        doc = _doc(project, "a.txt")
        url = reverse("documents:document_delete", args=[project.slug, doc.pk])
        assert client_logged_in.post(url).status_code == 302
        assert Document.all_objects.get(pk=doc.pk).deleted_at is not None


class TestSweeps:
    def test_the_nightly_task_and_the_desktop_tick_call_the_sweep(self):
        from core import tasks

        assert callable(tasks.prune_file_trash_task)
        loop = (BASE / "core" / "snapshots.py").read_text()
        assert "prune_file_trash()" in loop and 'log.exception("file trash sweep failed")' in loop

    def test_the_admin_sees_the_trash(self):
        from django.contrib.admin.sites import site

        project = ProjectFactory()
        doc = _doc(project, "a.txt")
        trash.trash(doc)
        admin = site._registry[Document]
        assert list(admin.get_queryset(None)) == [doc]
        assert "deleted_at" in admin.list_display


def test_explorer_trash_ui_wiring():
    files = (BASE / "frontend" / "src" / "app" / "pages" / "Files.tsx").read_text()
    # delete is immediate with an undo toast; the confirm is gone from single and bulk deletes
    assert "showUndo(`Deleted — “${f.name.slice(0, 50)}” · in the Trash for 30 days`" in files
    assert 'body: JSON.stringify({ ids, action: "restore" })' in files
    assert "const trashFile = (f: FileNode) => deleteDoc.mutate(f);" in files
    assert "Delete “${f.name}”?" not in files and "Delete ${n} file" not in files
    # the Trash section sits under the tree, outside role="tree"
    tree_end = files.index('data-testid="file-trash"')
    assert files.rindex('role="tree"', 0, tree_end) < files.rindex("</div>", 0, tree_end)
    for needle in (
        'data-testid="file-trash-toggle"',
        'data-testid="file-trash-empty"',
        'data-testid="file-trash-row"',
        'data-testid="file-trash-restore"',
        'data-testid="file-trash-forever"',
        'data-testid="file-trash-when"',
        "kept 30 days",
        "/documents/empty-trash/",
        "?forever=true",
    ):
        assert needle in files, needle
    # the confirms that remain are the irreversible ones
    assert 'title: "Empty the trash?"' in files and "for good?`" in files
    bundle = (BASE / "static" / "js" / "islands" / "Files-chunk.js").read_text()
    assert "file-trash-restore" in bundle and "in the Trash for 30 days" in bundle
