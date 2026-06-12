"""Materialization of manuscript files into the unified tree (epic slice 1c-ii-A)."""

import pytest

from documents.models import Document, Folder
from writing.tests.factories import ManuscriptFactory
from writing.tree_sync import (
    dematerialize_manuscript_tree,
    materialize_manuscript_tree,
    root_folder_name,
)

pytestmark = pytest.mark.django_db


def _seed():
    m = ManuscriptFactory(latex_source="\\documentclass{article}")
    m.ensure_main_file()  # main.tex (is_main)
    m.files.create(path="refs.bib", content="@a{x}", kind="bib")
    m.files.create(path="sections/intro.tex", content="intro", kind="tex")
    return m


class TestMaterialize:
    def test_creates_tree_nodes_and_main(self):
        m = _seed()
        root, main_node = materialize_manuscript_tree(m, Folder=Folder, Document=Document)
        root_name = root_folder_name(m.pk)
        assert root.name == root_name and root.parent_id is None
        nodes = Document.objects.filter(role="manuscript_source")
        rel_paths = set(nodes.values_list("rel_path", flat=True))
        assert rel_paths == {
            f"{root_name}/main.tex",
            f"{root_name}/refs.bib",
            f"{root_name}/sections/intro.tex",
        }
        # nested path created the intermediate folder
        assert Folder.objects.filter(project=m.project, parent=root, name="sections").exists()
        # content + kind carried over; main points at main.tex
        intro = nodes.get(rel_path=f"{root_name}/sections/intro.tex")
        assert intro.content == "intro" and intro.kind == "tex"
        assert main_node.rel_path == f"{root_name}/main.tex"

    def test_idempotent(self):
        m = _seed()
        materialize_manuscript_tree(m, Folder=Folder, Document=Document)
        before = Document.objects.filter(role="manuscript_source").count()
        materialize_manuscript_tree(m, Folder=Folder, Document=Document)
        assert Document.objects.filter(role="manuscript_source").count() == before == 3

    def test_reverse_removes_nodes_and_root(self):
        m = _seed()
        materialize_manuscript_tree(m, Folder=Folder, Document=Document)
        dematerialize_manuscript_tree(m, Folder=Folder, Document=Document)
        assert Document.objects.filter(role="manuscript_source").count() == 0
        assert not Folder.objects.filter(name=root_folder_name(m.pk)).exists()

    def test_general_documents_untouched(self):
        m = _seed()
        general = Document.objects.create(project=m.project, title="data.csv", rel_path="data.csv")
        materialize_manuscript_tree(m, Folder=Folder, Document=Document)
        general.refresh_from_db()
        assert general.role == "general" and general.rel_path == "data.csv"
