"""Unified-tree path rules (file-workspace epic, slice 1a)."""

import pytest
from django.core.exceptions import ValidationError

from documents import paths


class TestValidateManuscriptPath:
    @pytest.mark.parametrize("good", ["main.tex", "sections/intro.tex", "a/b/c/d.png"])
    def test_accepts_clean_relative_paths(self, good):
        assert paths.validate_manuscript_path(good) == good

    @pytest.mark.parametrize(
        "bad", ["../etc/passwd", "/abs.tex", "a\\b.tex", ".hidden", "x/" * 9 + "y.tex", "é.tex"]
    )
    def test_rejects_traversal_absolute_dotfile_depth_unicode(self, bad):
        with pytest.raises(ValidationError):
            paths.validate_manuscript_path(bad)

    def test_writing_re_export_is_the_same_callable(self):
        from writing.models import validate_manuscript_path

        assert validate_manuscript_path is paths.validate_manuscript_path


class TestKindForNodePath:
    @pytest.mark.parametrize(
        "path,kind",
        [
            ("main.tex", "tex"),
            ("a.sty", "tex"),
            ("refs.bib", "bib"),
            ("notes.md", "other"),
            ("data.csv", "other"),
            ("run.py", "other"),
            ("figure.png", "asset"),
            ("archive.zip", "asset"),
            ("noext", "asset"),
        ],
    )
    def test_classifies_by_extension(self, path, kind):
        assert paths.kind_for_node_path(path) == kind
