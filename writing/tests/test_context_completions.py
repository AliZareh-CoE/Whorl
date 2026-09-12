"""#459 (backlog #117): LaTeX completions rank by the enclosing environment."""

import shutil
import subprocess
from pathlib import Path

import pytest
from django.conf import settings

BASE = Path(settings.BASE_DIR)

NODE_CHECK = """
import { enclosingEnvironment, boostFor } from "%s";
const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { console.error("FAIL", m, a, b); process.exit(1); } };
eq(enclosingEnvironment("\\\\begin{document}\\n\\\\begin{itemize}\\n\\\\item a\\n"), "itemize", "innermost open env");
eq(enclosingEnvironment("\\\\begin{itemize}\\\\item a\\\\end{itemize}\\ntext"), null, "closed env");
eq(enclosingEnvironment("\\\\begin{figure}[t]\\\\begin{center}\\\\end{center}"), "figure", "closed inner, open outer");
eq(enclosingEnvironment("\\\\begin{equation*}x"), "equation*", "starred");
eq(enclosingEnvironment("no environments here"), null, "top level");
eq(boostFor("itemize", "\\\\item"), 99, "item in a list");
eq(boostFor("itemize", "\\\\includegraphics"), 0, "graphics not in a list");
eq(boostFor("figure", "\\\\includegraphics{}"), 99, "graphics in a figure");
eq(boostFor("figure", "\\\\caption{}"), 90, "caption in a figure");
eq(boostFor("tabular", "\\\\hline"), 99, "hline in a table");
eq(boostFor("align", "\\\\label{}"), 99, "label in math");
eq(boostFor(null, "\\\\item"), 0, "nothing at top level");
console.log("context OK");
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_scanner_and_boosts_under_node(tmp_path):
    src = (BASE / "frontend" / "src" / "editor" / "context.ts").resolve().as_posix()
    script = tmp_path / "check.mjs"
    script.write_text(NODE_CHECK % src)
    run = subprocess.run(
        ["node", "--experimental-strip-types", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "context OK" in run.stdout


def test_editor_wires_the_wrapper():
    src = (BASE / "frontend" / "src" / "editor" / "index.ts").read_text()
    assert "contextAwareLatex(latexCompletionSource(true))" in src
    assert 'from "./context"' in src and "boostFor(env, o.label)" in src
