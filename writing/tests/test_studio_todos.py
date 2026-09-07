"""Studio to-do panel (#377): `% TODO` / `% FIXME` / `\\todo{}` markers across the sources."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# the same expression the studio uses (frontend/src/app/pages/Studio.tsx TODO_RE)
TODO_RE = re.compile(r"%\s*(TODO|FIXME|XXX|HACK)\b[:\s-]*(.*)|\\todo(?:\[[^\]]*\])?\{([^}]*)\}")


def test_marker_grammar():
    assert TODO_RE.search("% TODO: fix the table").group(2) == "fix the table"
    assert TODO_RE.search("%FIXME power analysis").group(1) == "FIXME"
    assert TODO_RE.search(r"text \todo[inline]{cite the replication} more").group(3) == "cite the replication"
    assert TODO_RE.search("% just a comment") is None
    assert TODO_RE.search(r"\section{TODO list}") is None  # a heading, not a marker


def test_demo_source_carries_markers_and_the_studio_lists_them():
    seed = (ROOT / "core/management/commands/seed_demo.py").read_text()
    assert "% TODO Replace the pilot numbers" in seed and "% FIXME The power analysis" in seed
    studio = (ROOT / "frontend/src/app/pages/Studio.tsx").read_text()
    assert "const TODO_RE" in studio and 'data-testid="studio-todos"' in studio
    assert "recomputeTodos" in studio
