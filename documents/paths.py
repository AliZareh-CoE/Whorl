"""Path rules for the unified project file tree (file-workspace epic, slice 1).

`validate_manuscript_path` and `kind_for_path` moved here verbatim from
writing/models.py — manuscript-source nodes keep the strict regime; general
documents get the looser `kind_for_node_path` classification on top.
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

# Loose text-ish extensions for GENERAL tree nodes only. Deliberately NOT used in the
# manuscript scope: there .txt/.csv stay "asset" so the manuscript-files contract
# (upload allowlist, editability, compile tree writes) is byte-identical.
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


def kind_for_path(path: str) -> str:
    """Manuscript-scope kind (tex/bib/asset) — moved verbatim, same semantics."""
    suffix = ("." + path.rsplit(".", 1)[-1]).lower() if "." in path else ""
    if suffix in TEX_EXTENSIONS:
        return KIND_TEX
    if suffix == ".bib":
        return KIND_BIB
    return KIND_ASSET


def kind_for_node_path(path: str) -> str:
    """Generalized kind for the unified tree: tex/bib/asset/other(-text)."""
    kind = kind_for_path(path)
    if kind == KIND_ASSET and _suffix(path) in TEXT_SUFFIXES:
        return KIND_OTHER
    return kind
