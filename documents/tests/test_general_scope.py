"""Manuscript-source nodes stay out of the general Documents UI (epic #30, slice 1c-ii-B1)."""

import pytest

from documents.models import Document
from documents.selectors import folder_tree
from projects.tests.factories import ProjectFactory
from writing.tests.factories import ManuscriptFactory
from writing.tree_sync import materialize_manuscript_tree

pytestmark = pytest.mark.django_db


def _project_with_manuscript_and_general_doc():
    project = ProjectFactory()
    Document.objects.create(project=project, title="data.csv", rel_path="data.csv")
    m = ManuscriptFactory(project=project)
    m.ensure_main_file()
    m.files.create(path="refs.bib", content="@a{x}", kind="bib")
    root, main = materialize_manuscript_tree(
        m, Folder=Document._meta.apps.get_model("documents", "Folder"), Document=Document
    )
    m.root_folder = root
    m.save(update_fields=["root_folder"])
    return project, m


class TestGeneralScope:
    def test_general_excludes_manuscript_sources(self):
        project, _ = _project_with_manuscript_and_general_doc()
        assert project.documents.count() == 3  # 1 general + main.tex + refs.bib
        general = project.documents.general()
        assert general.count() == 1
        assert general.get().title == "data.csv"

    def test_folder_tree_hides_manuscript_root(self):
        project, _ = _project_with_manuscript_and_general_doc()
        names = [node["folder"].name for node in folder_tree(project)]
        assert all(not n.startswith("manuscript-") for n in names)

    def test_documents_index_omits_manuscript_nodes(self, client_logged_in):
        project, _ = _project_with_manuscript_and_general_doc()
        response = client_logged_in.get(f"/projects/{project.slug}/documents/?all")
        body = response.content.decode()
        assert "data.csv" in body
        assert "main.tex" not in body and "refs.bib" not in body
