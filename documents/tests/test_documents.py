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
