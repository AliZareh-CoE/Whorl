"""The ManuscriptFile->Document tree mirror stays live via signals (epic #30, slice 1c-ii-B2)."""

import pytest

from documents.models import Document
from writing.tests.factories import ManuscriptFactory
from writing.tree_sync import root_folder_name

pytestmark = pytest.mark.django_db


def _nodes(manuscript):
    root = root_folder_name(manuscript.pk)
    return Document.objects.filter(role="manuscript_source", rel_path__startswith=root + "/")


class TestTreeMirror:
    def test_create_mirrors_node(self):
        m = ManuscriptFactory()
        m.files.create(path="sections/intro.tex", content="hello", kind="tex")
        node = _nodes(m).get(rel_path=f"{root_folder_name(m.pk)}/sections/intro.tex")
        assert node.content == "hello" and node.kind == "tex"
        m.refresh_from_db()
        assert m.root_folder is not None

    def test_edit_updates_mirror_content(self):
        m = ManuscriptFactory()
        f = m.files.create(path="main.tex", content="v1", kind="tex", is_main=True)
        f.content = "v2 edited"
        f.save()
        node = _nodes(m).get(rel_path=f"{root_folder_name(m.pk)}/main.tex")
        assert node.content == "v2 edited"
        m.refresh_from_db()
        assert m.main_file_node_id == node.pk  # is_main tracked

    def test_rename_prunes_old_node(self):
        m = ManuscriptFactory()
        f = m.files.create(path="draft.tex", content="x", kind="tex")
        f.path = "final.tex"
        f.save()
        rels = set(_nodes(m).values_list("rel_path", flat=True))
        root = root_folder_name(m.pk)
        assert f"{root}/final.tex" in rels and f"{root}/draft.tex" not in rels

    def test_delete_prunes_node(self):
        m = ManuscriptFactory()
        f = m.files.create(path="scratch.tex", content="x", kind="tex")
        assert _nodes(m).count() == 1
        f.delete()
        assert _nodes(m).count() == 0

    def test_main_switch_updates_fk(self):
        m = ManuscriptFactory()
        a = m.files.create(path="a.tex", content="a", kind="tex", is_main=True)
        m.files.create(path="b.tex", content="b", kind="tex")
        a.is_main = False
        a.save()
        b = m.files.get(path="b.tex")
        b.is_main = True
        b.save()
        m.refresh_from_db()
        node_b = _nodes(m).get(rel_path=f"{root_folder_name(m.pk)}/b.tex")
        assert m.main_file_node_id == node_b.pk
