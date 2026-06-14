import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from documents import selectors
from documents.forms import FolderForm
from projects.tests.factories import ProjectFactory

from .factories import DocumentFactory, FolderFactory, TagFactory

pytestmark = pytest.mark.django_db


class TestFolderNesting:
    def test_path_walks_ancestors(self):
        root = FolderFactory(name="Data")
        child = FolderFactory(project=root.project, parent=root, name="Raw")
        grandchild = FolderFactory(project=root.project, parent=child, name="2026")
        assert grandchild.path == "Data / Raw / 2026"

    def test_folder_tree_nests(self):
        project = ProjectFactory()
        root = FolderFactory(project=project, name="A")
        child = FolderFactory(project=project, parent=root, name="B")
        tree = selectors.folder_tree(project)
        assert len(tree) == 1
        assert tree[0]["folder"] == root
        assert tree[0]["children"][0]["folder"] == child

    def test_move_targets_exclude_self_and_descendants(self):
        project = ProjectFactory()
        root = FolderFactory(project=project, name="A")
        FolderFactory(project=project, parent=root, name="B")
        sibling = FolderFactory(project=project, name="C")
        targets = selectors.move_targets(root)
        assert list(targets) == [sibling]

    def test_form_rejects_duplicate_name_in_same_parent(self):
        project = ProjectFactory()
        FolderFactory(project=project, name="Data")
        form = FolderForm(data={"name": "Data", "parent": ""}, project=project)
        assert not form.is_valid()

    def test_duplicate_name_ok_in_different_parent(self):
        project = ProjectFactory()
        parent = FolderFactory(project=project, name="Top")
        FolderFactory(project=project, name="Data")
        form = FolderForm(data={"name": "Data", "parent": parent.pk}, project=project)
        assert form.is_valid(), form.errors


class TestDocumentViews:
    def test_upload_into_folder(self, client_logged_in):
        folder = FolderFactory()
        project = folder.project
        response = client_logged_in.post(
            reverse("documents:upload", args=[project.slug]),
            {
                "title": "Survey results",
                "file": SimpleUploadedFile("results.csv", b"a,b\n1,2", "text/csv"),
                "folder": folder.pk,
                "description": "",
            },
        )
        assert response.status_code == 302
        doc = project.documents.get()
        assert doc.folder == folder
        assert doc.file_size > 0
        assert doc.content_type == "text/csv"

    def test_index_root_vs_folder_filter(self, client_logged_in):
        project = ProjectFactory()
        folder = FolderFactory(project=project)
        in_folder = DocumentFactory(project=project, folder=folder, title="InFolder Doc")
        at_root = DocumentFactory(project=project, title="Root Doc")
        url = reverse("documents:index", args=[project.slug])

        root_page = client_logged_in.get(url)
        assert at_root.title.encode() in root_page.content
        assert in_folder.title.encode() not in root_page.content

        folder_page = client_logged_in.get(url, {"folder": folder.pk})
        assert in_folder.title.encode() in folder_page.content
        assert at_root.title.encode() not in folder_page.content

        all_page = client_logged_in.get(f"{url}?all")
        assert in_folder.title.encode() in all_page.content
        assert at_root.title.encode() in all_page.content

    def test_filter_by_tag(self, client_logged_in):
        project = ProjectFactory()
        tag = TagFactory(project=project)
        tagged = DocumentFactory(project=project, title="Tagged Doc")
        tagged.tags.add(tag)
        DocumentFactory(project=project, title="Plain Doc")
        url = reverse("documents:index", args=[project.slug])
        response = client_logged_in.get(f"{url}?all&tag={tag.pk}")
        assert b"Tagged Doc" in response.content
        assert b"Plain Doc" not in response.content

    def test_nested_folder_shows_clickable_breadcrumb(self, client_logged_in):
        # owner #14: viewing a nested folder shows a breadcrumb that links to each ancestor.
        project = ProjectFactory()
        parent = FolderFactory(project=project, name="Parent")
        child = FolderFactory(project=project, parent=parent, name="Child")
        url = reverse("documents:index", args=[project.slug])
        body = client_logged_in.get(f"{url}?folder={child.pk}").content.decode()
        assert f"?folder={parent.pk}" in body  # ancestor is a clickable jump
        assert ">Parent<" in body and ">Child<" in body  # both segments rendered
        # the current folder is the leaf and not itself a link target
        assert f"?folder={child.pk}" not in body.split(">Child<")[0][-60:]

    def test_documents_index_no_n_plus_one(self, client_logged_in, django_assert_max_num_queries):
        # #223 (AUDIT #21 follow-up): adding documents must not add queries — the listing
        # relies on select_related/prefetch and a single batched comment-count query.
        project = ProjectFactory()
        folder = FolderFactory(project=project)
        DocumentFactory.create_batch(3, project=project, folder=folder)
        url = f"{reverse('documents:index', args=[project.slug])}?all"
        client_logged_in.get(url)  # warm one-time caches (contenttypes, etc.)
        with django_assert_max_num_queries(30) as ctx:
            client_logged_in.get(url)
        baseline = len(ctx.captured_queries)
        DocumentFactory.create_batch(5, project=project, folder=folder)
        with django_assert_max_num_queries(baseline):
            client_logged_in.get(url)  # 8 documents cost no more queries than 3 did

    def test_folder_ancestors_property(self):
        # the breadcrumb data: root → … → self, in order.
        project = ProjectFactory()
        a = FolderFactory(project=project, name="A")
        b = FolderFactory(project=project, parent=a, name="B")
        c = FolderFactory(project=project, parent=b, name="C")
        assert [f.name for f in c.ancestors] == ["A", "B", "C"]

    def test_index_remembers_tag_filter(self, client_logged_in):
        # #212: a chosen tag sticks; a later visit with no tag param restores it.
        project = ProjectFactory()
        tag = TagFactory(project=project)
        tagged = DocumentFactory(project=project, title="Tagged Doc")
        tagged.tags.add(tag)
        DocumentFactory(project=project, title="Plain Doc")
        url = reverse("documents:index", args=[project.slug])
        client_logged_in.get(f"{url}?all&tag={tag.pk}")  # remember it
        body = client_logged_in.get(f"{url}?all").content  # restored from session
        assert b"Tagged Doc" in body
        assert b"Plain Doc" not in body

    def test_index_tag_memory_is_per_project(self, client_logged_in):
        # #212/#194: the tag pk is project-scoped, so the memory must not leak across projects.
        a = ProjectFactory()
        tag = TagFactory(project=a)
        DocumentFactory(project=a).tags.add(tag)
        b = ProjectFactory()
        DocumentFactory(project=b, title="Bravo Doc")
        client_logged_in.get(f"{reverse('documents:index', args=[a.slug])}?all&tag={tag.pk}")
        # project B has no remembered tag — its own list is unfiltered
        body = client_logged_in.get(f"{reverse('documents:index', args=[b.slug])}?all").content
        assert b"Bravo Doc" in body

    def test_index_clears_remembered_tag(self, client_logged_in):
        # #212: selecting "All" (empty tag) clears a remembered filter.
        project = ProjectFactory()
        tag = TagFactory(project=project)
        DocumentFactory(project=project, title="Tagged Doc").tags.add(tag)
        DocumentFactory(project=project, title="Plain Doc")
        url = reverse("documents:index", args=[project.slug])
        client_logged_in.get(f"{url}?all&tag={tag.pk}")  # remember
        body = client_logged_in.get(f"{url}?all&tag=").content  # All clears it
        assert b"Tagged Doc" in body and b"Plain Doc" in body

    def test_clear_tag_link_sends_empty_tag(self, client_logged_in):
        # #212 regression guard: the Clear link must send an explicit empty tag= to clear the
        # session-remembered tag — a scope-only URL would restore it instead.
        project = ProjectFactory()
        tag = TagFactory(project=project)
        DocumentFactory(project=project).tags.add(tag)
        url = reverse("documents:index", args=[project.slug])
        body = client_logged_in.get(f"{url}?all&tag={tag.pk}").content.decode()
        assert '?all&tag="' in body  # the Clear link clears the tag while keeping scope

    def test_index_ignores_foreign_tag(self, client_logged_in):
        # #192: a tag pk from another project must never filter this list — falls back to All.
        project = ProjectFactory()
        DocumentFactory(project=project, title="Mine Doc")
        foreign_tag = TagFactory(project=ProjectFactory())
        url = reverse("documents:index", args=[project.slug])
        response = client_logged_in.get(f"{url}?all&tag={foreign_tag.pk}")
        assert response.status_code == 200
        assert b"Mine Doc" in response.content

    def test_download(self, client_logged_in):
        doc = DocumentFactory()
        response = client_logged_in.get(
            reverse("documents:download", args=[doc.project.slug, doc.pk])
        )
        assert response.status_code == 200
        assert response["Content-Disposition"].startswith("attachment")

    def test_tag_crud(self, client_logged_in):
        project = ProjectFactory()
        response = client_logged_in.post(
            reverse("documents:tag_create", args=[project.slug]),
            {"name": "methods", "color": "#ff0000"},
        )
        assert response.status_code == 302
        assert project.tags.filter(name="methods").exists()


class TestFileHandlingUpgrades:
    def test_bulk_upload_multiple_files_into_folder(self, client_logged_in):
        folder = FolderFactory()
        project = folder.project
        response = client_logged_in.post(
            reverse("documents:bulk_upload", args=[project.slug]),
            {
                "folder": folder.pk,
                "files": [
                    SimpleUploadedFile("pilot_data-v2.csv", b"a,b", "text/csv"),
                    SimpleUploadedFile("notes.txt", b"hi", "text/plain"),
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert sorted(data["created"]) == ["notes", "pilot data v2"]
        assert project.documents.filter(folder=folder).count() == 2

    def test_bulk_upload_reports_oversize_per_file(self, client_logged_in, monkeypatch):
        from core import security

        monkeypatch.setattr(security, "MAX_UPLOAD_BYTES", 5)
        project = ProjectFactory()
        response = client_logged_in.post(
            reverse("documents:bulk_upload", args=[project.slug]),
            {
                "files": [
                    SimpleUploadedFile("ok.txt", b"tiny"),
                    SimpleUploadedFile("big.txt", b"toolarge"),
                ]
            },
        )
        data = response.json()
        assert data["created"] == ["ok"]
        assert "big.txt" in data["errors"][0]

    def test_inline_rename_roundtrip(self, client_logged_in):
        doc = DocumentFactory(title="Old name")
        form = client_logged_in.get(reverse("documents:rename", args=[doc.project.slug, doc.pk]))
        assert b'name="title"' in form.content
        response = client_logged_in.post(
            reverse("documents:rename", args=[doc.project.slug, doc.pk]),
            {"title": "New name"},
        )
        doc.refresh_from_db()
        assert doc.title == "New name"
        assert b"New name" in response.content

    def test_quick_move_to_folder_and_root(self, client_logged_in):
        folder = FolderFactory()
        doc = DocumentFactory(project=folder.project)
        client_logged_in.post(
            reverse("documents:move", args=[doc.project.slug, doc.pk]), {"folder": folder.pk}
        )
        doc.refresh_from_db()
        assert doc.folder == folder
        client_logged_in.post(
            reverse("documents:move", args=[doc.project.slug, doc.pk]), {"folder": ""}
        )
        doc.refresh_from_db()
        assert doc.folder is None

    def test_move_rejects_foreign_folder(self, client_logged_in):
        doc = DocumentFactory()
        foreign = FolderFactory()  # different project
        response = client_logged_in.post(
            reverse("documents:move", args=[doc.project.slug, doc.pk]), {"folder": foreign.pk}
        )
        assert response.status_code == 404


class TestUploadProgressUI:
    def test_index_has_single_clean_upload_script(self, client_logged_in):
        """Regression: the upload script was once duplicated into the title and
        breadcrumbs blocks, redeclaring consts and breaking drag-and-drop."""
        from projects.tests.factories import ProjectFactory

        project = ProjectFactory()
        response = client_logged_in.get(reverse("documents:index", args=[project.slug]))
        content = response.content.decode()
        assert content.count("const dropOverlay") == 1
        assert content.count('id="multi-file-input"') == 1
        title = content.split("<title>")[1].split("</title>")[0]
        assert "<script" not in title and "input" not in title

    def test_index_renders_per_file_progress_markup(self, client_logged_in):
        from projects.tests.factories import ProjectFactory

        project = ProjectFactory()
        response = client_logged_in.get(reverse("documents:index", args=[project.slug]))
        content = response.content.decode()
        assert "upload-bar" in content
        assert "xhr.upload.addEventListener" in content


class TestBulkActions:
    def _docs(self, n=3):
        from documents.tests.factories import DocumentFactory

        first = DocumentFactory()
        return [first] + [DocumentFactory(project=first.project) for _ in range(n - 1)]

    def test_bulk_move_and_tag_and_delete(self, client_logged_in):
        from documents.models import Document, Folder, Tag

        docs = self._docs()
        project = docs[0].project
        folder = Folder.objects.create(project=project, name="Bulk target")
        tag = Tag.objects.create(project=project, name="bulky")
        url = reverse("documents:bulk", args=[project.slug])
        ids = [d.pk for d in docs[:2]]

        client_logged_in.post(url, {"action": "move", "ids": ids, "folder": folder.pk})
        assert Document.objects.filter(folder=folder).count() == 2

        client_logged_in.post(url, {"action": "tag", "ids": ids, "tag": tag.pk})
        assert all(tag in d.tags.all() for d in Document.objects.filter(pk__in=ids))

        response = client_logged_in.post(url, {"action": "delete", "ids": ids})
        assert response.status_code == 302
        assert Document.objects.filter(pk__in=ids).count() == 0
        assert Document.objects.filter(pk=docs[2].pk).exists()  # untouched

    def test_cross_project_ids_ignored(self, client_logged_in):
        from documents.models import Document
        from documents.tests.factories import DocumentFactory

        mine = DocumentFactory()
        other = DocumentFactory()  # different project
        url = reverse("documents:bulk", args=[mine.project.slug])
        client_logged_in.post(url, {"action": "delete", "ids": [mine.pk, other.pk]})
        assert not Document.objects.filter(pk=mine.pk).exists()
        assert Document.objects.filter(pk=other.pk).exists()  # scoping protected it

    def test_open_redirect_guard_on_next(self, client_logged_in):
        docs = self._docs(1)
        url = reverse("documents:bulk", args=[docs[0].project.slug])
        response = client_logged_in.post(
            url, {"action": "delete", "ids": [docs[0].pk], "next": "//evil.example.com"}
        )
        assert response.url.startswith("/")
        assert "evil" not in response.url

    def test_page_renders_bulk_ui(self, client_logged_in):
        docs = self._docs(1)
        response = client_logged_in.get(reverse("documents:index", args=[docs[0].project.slug]))
        content = response.content.decode()
        assert 'id="bulk-form"' in content
        assert 'name="ids"' in content
        assert "Select all documents" in content


class TestDocumentsIsland:
    """Owner idea #19: the documents table mounts as a React island."""

    def test_island_mount_point_and_props(self, client_logged_in):
        from documents.tests.factories import DocumentFactory

        doc = DocumentFactory(title="Island doc")
        response = client_logged_in.get(reverse("documents:index", args=[doc.project.slug]))
        content = response.content.decode()
        assert 'data-island="documents-table"' in content
        assert 'id="documents-table-props"' in content  # json_script payload
        assert "Island doc" in content  # server fallback still renders the table
        assert "islands-loader.js" in content

    def test_props_payload_shape(self, client_logged_in):
        import json

        from documents.tests.factories import DocumentFactory

        doc = DocumentFactory()
        response = client_logged_in.get(reverse("documents:index", args=[doc.project.slug]))
        content = response.content.decode()
        payload = content.split('id="documents-table-props"')[1]
        payload = payload.split(">", 1)[1].split("</script>")[0]
        props = json.loads(payload)
        assert props["bulkUrl"].endswith("/documents/bulk/")
        assert props["documents"][0]["id"] == doc.pk
        assert "downloadUrl" in props["documents"][0]

    def test_built_island_artifacts_committed(self):
        from pathlib import Path

        islands = Path("static/js/islands")
        assert (islands / "documents-table.js").exists()
        assert (islands / "assistant.js").exists()
        # React itself lives in the shared chunk both islands import (Vite 8 names it
        # jsx-runtime-chunk.js; it was client-chunk.js under Vite 6 — see #159)
        chunk = islands / "jsx-runtime-chunk.js"
        assert chunk.exists() and chunk.stat().st_size > 100_000
