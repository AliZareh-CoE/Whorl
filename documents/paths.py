"""Path rules + file-kind classification for the unified project file tree.

File-workspace epic (Owner idea #30), slice 1a. `validate_manuscript_path` and the
strict path constants live here as the single source of truth; writing/models.py
re-imports them so `writing.models.validate_manuscript_path` (referenced by the
historical 0006 migration) keeps resolving. Manuscript-source nodes keep the strict
regime; general tree nodes get the looser `kind_for_node_path` classification.
"""

import re

from django.core.exceptions import ValidationError

PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,79}$")
MAX_PATH_SEGMENTS = 8

KIND_TEX = "tex"
KIND_BIB = "bib"
KIND_ASSET = "asset"
KIND_OTHER = "other"


def validate_manuscript_path(path: str) -> str:
    """Workbench file paths are deliberately strict (Owner idea #24 slice 6).

    ASCII-only kills unicode tricks; segments can't start with a dot, which
    rejects "..", ".", and dotfiles in one rule; no absolute/drive/backslash
    forms. Compile has a resolve()-based guard as the second line of defense.
    """
    if not path or len(path) > 200:
        raise ValidationError("Path must be 1-200 characters.")
    if not path.isascii():
        raise ValidationError("Path must be ASCII.")
    if "\\" in path:
        raise ValidationError("Use forward slashes.")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise ValidationError("Path must be relative.")
    segments = path.split("/")
    if len(segments) > MAX_PATH_SEGMENTS:
        raise ValidationError(f"At most {MAX_PATH_SEGMENTS} path segments.")
    for segment in segments:
        if not PATH_SEGMENT_RE.match(segment):
            raise ValidationError(f"Invalid path segment: {segment!r}")
    return path


TEX_EXTENSIONS = {".tex", ".sty", ".cls", ".bst"}

# Text-ish extensions that the unified tree can open in the editor (GENERAL nodes).
# Deliberately NOT applied inside a manuscript scope, where .txt/.csv stay "asset"
# so the manuscript-files contract (upload allowlist, compile tree writes) is unchanged.
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".py",
    ".r",
    ".sh",
    ".rst",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".xml",
    ".log",
    ".ini",
    ".cfg",
}


def _suffix(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return ("." + name.rsplit(".", 1)[-1]).lower() if "." in name else ""


def kind_for_node_path(path: str) -> str:
    """Generalized kind for any node in the unified tree: tex/bib/asset/other(-text)."""
    suffix = _suffix(path)
    if suffix in TEX_EXTENSIONS:
        return KIND_TEX
    if suffix == ".bib":
        return KIND_BIB
    if suffix in TEXT_SUFFIXES:
        return KIND_OTHER
    return KIND_ASSET
