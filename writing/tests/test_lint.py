"""#470 — the LaTeX style lint: the mistakes a compile never reports."""

from pathlib import Path

import pytest

from projects.tests.factories import ProjectFactory
from writing import lint as L
from writing.models import Manuscript, ManuscriptFile

pytestmark = pytest.mark.django_db


def _rules(text, path="main.tex"):
    return [(f["rule"], f["line"]) for f in L.lint_files([(path, text)])["findings"]]


def test_every_rule_fires_once_on_the_fixture():
    tex = "\n".join(
        [
            r"\documentclass{article}",  # 1
            r"\begin{document}",  # 2
            r"As Figure \ref{fig:a} shows.",  # 3 nbsp-ref
            r"About 50% of trials.",  # 4 percent
            r"Each ran in 5 ms.",  # 5 unit-space
            r'They were "fast".',  # 6 quotes
            r"And so on...",  # 7 ellipsis
            r"$$x=1$$",  # 8 display-math
            r"Line one\\",  # 9 linebreak
            r"Some e.g. thing.",  # 10 abbrev
            r"\begin{figure}",  # 11
            r"\begin{center}",  # 12 center-env
            r"\label{fig:a}",  # 13 label-before-caption
            r"\caption{A}",  # 14
            r"\end{center}",  # 15
            r"\end{figure}",  # 16
            r"\begin{table}",  # 17 unlabeled-float
            r"\caption{T}",  # 18
            r"\end{table}",  # 19
            r"See \ref{fig:missing}.",  # 20 undefined-ref
            r"\label{fig:a}",  # 21 duplicate-label
            r"\end{itemize}",  # 22 unmatched-env
            r"Open \textbf{brace",  # 23 unclosed-brace
            r"\end{document}",  # 24
        ]
    )
    out = L.lint_files([("main.tex", tex)])
    got = {(f["rule"], f["line"]) for f in out["findings"]}
    assert got == {
        ("nbsp-ref", 3),
        ("percent", 4),
        ("unit-space", 5),
        ("quotes", 6),
        ("ellipsis", 7),
        ("display-math", 8),
        ("linebreak", 9),
        ("abbrev", 10),
        ("center-env", 12),
        ("label-before-caption", 13),
        ("unlabeled-float", 17),
        ("undefined-ref", 20),
        ("duplicate-label", 21),
        ("unmatched-env", 22),
        ("unclosed-brace", 23),
    }
    assert set(RULE for RULE, _ in got) == set(L.RULES)
    assert out["errors"] == 6 and out["warnings"] == 9 and out["count"] == 15
    by = {f["rule"]: f for f in out["findings"]}
    assert by["nbsp-ref"]["fix"] == r"Figure~\ref{"
    assert by["percent"]["fix"] == r"0\%" and by["percent"]["level"] == "error"
    assert by["unit-space"]["fix"] == r"5\,ms"
    assert by["quotes"]["fix"] == "``fast''"
    assert "main.tex:13" in by["duplicate-label"]["message"]


def test_comments_verbatim_urls_and_tables_are_skipped():
    tex = "\n".join(
        [
            r"% Figure \ref{x} 50% ... " + '"quoted"',
            r"Text % trailing 50% comment",
            r"\begin{verbatim}",
            r'"quoted" ... 50% Figure \ref{x}',
            r"\end{verbatim}",
            r"\url{http://a.b/50%20c} and \href{http://x/1 ms}{link}",
            r"\begin{tabular}{cc}",
            r"1 ms & Figure \ref{fig:t} \\",
            r"\end{tabular}",
            r"\begin{figure}\caption{c}\label{fig:t}\end{figure}",
            r"\begin{align}",
            r"a &= b \\",
            r"\end{align}",
            r"Already 5\,ms, 50\%, Figure~\ref{fig:t}, ``ok'' and \ldots done.",
        ]
    )
    assert _rules(tex) == []


def test_labels_and_refs_resolve_across_files():
    files = [
        ("main.tex", "\\input{intro}\nSee \\cref{sec:intro} and \\ref{eq:1,eq:2}."),
        (
            "intro.tex",
            "\\section{Intro}\\label{sec:intro}\n\\begin{equation}x\\label{eq:1}\\end{equation}",
        ),
    ]
    out = L.lint_files(files)
    assert [(f["rule"], f["file"], f["line"]) for f in out["findings"]] == [
        ("undefined-ref", "main.tex", 2)
    ]
    assert "eq:2" in out["findings"][0]["message"]


def test_lint_manuscript_uses_the_file_tree_or_the_legacy_source():
    m = Manuscript.objects.create(project=ProjectFactory(), title="P")
    ManuscriptFile.objects.filter(manuscript=m).delete()
    Manuscript.objects.filter(pk=m.pk).update(latex_source="Figure \\ref{fig:x}")
    out = L.lint_manuscript(Manuscript.objects.get(pk=m.pk))
    assert out["files"] == 1 and out["manuscript"] == m.id
    assert {f["rule"] for f in out["findings"]} == {"nbsp-ref", "undefined-ref"}
    ManuscriptFile.objects.create(manuscript=m, path="a.tex", kind="tex", content="Clean text.")
    ManuscriptFile.objects.create(manuscript=m, path="b.tex", kind="tex", content="Some e.g. thing")
    out = L.lint_manuscript(Manuscript.objects.get(pk=m.pk))
    assert out["files"] == 2 and [f["file"] for f in out["findings"]] == ["b.tex"]


def test_preflight_row_points_at_the_first_finding():
    from writing.preflight import preflight

    m = Manuscript.objects.create(project=ProjectFactory(), title="P")
    ManuscriptFile.objects.filter(manuscript=m).delete()
    ManuscriptFile.objects.create(
        manuscript=m, path="main.tex", kind="tex", content="ok\nAbout 50% done\nAnd 5 ms"
    )
    row = {c["key"]: c for c in preflight(Manuscript.objects.get(pk=m.pk))["checks"]}["lint"]
    assert row["state"] == "warn"
    assert row["detail"].startswith("2 findings (1 serious) — first at main.tex:2")
    assert row["fix"] == {"kind": "line", "path": "main.tex", "line": 2}
    ManuscriptFile.objects.filter(manuscript=m).update(content="Clean.")
    row = {c["key"]: c for c in preflight(Manuscript.objects.get(pk=m.pk))["checks"]}["lint"]
    assert row["state"] == "ok"


def test_lint_api_action(client_logged_in):
    m = Manuscript.objects.create(project=ProjectFactory(), title="P")
    ManuscriptFile.objects.filter(manuscript=m).delete()
    ManuscriptFile.objects.create(manuscript=m, path="main.tex", kind="tex", content="$$x$$")
    r = client_logged_in.get(f"/api/v1/manuscripts/{m.id}/lint/")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1 and body["findings"][0]["rule"] == "display-math"
    assert "display-math" in body["rules"]


def test_studio_merges_the_lint_into_the_problems_panel():
    tsx = Path("frontend/src/app/pages/Studio.tsx").read_text()
    for needle in (
        "/lint/`",
        'data-testid="lint-toggle"',
        "const problems: Diag[] = lintOn",
        'source: "lint"',
        "Run the style lint",
        "refreshWords(); void refreshLint();",
    ):
        assert needle in tsx, needle


def test_structure_rules_pair_environments_and_braces():
    """#471: the checks ported from the editor's per-file linter, now one source."""
    tex = "\n".join(
        [
            r"\begin{document}",  # 1
            r"\begin{figure}",  # 2: closed by \end{document} → missing \end{figure}
            r"\caption{x}\label{f}",
            r"\end{table}",  # 3: closes nothing
            r"Text \verb|{| and \{ escaped and \% fine % { comment",
            r"\begin{verbatim}",
            r"\begin{itemize} { {",  # verbatim: ignored
            r"\end{verbatim}",
            r"Balanced {ok} then } stray",  # 8: } closes nothing
            r"Open {one and {two",  # 9: two unclosed
            r"\end{document}",  # 10
        ]
    )
    got = [
        (f["rule"], f["line"], f["message"])
        for f in L.lint_files([("m.tex", tex)])["findings"]
        if f["rule"] in ("unmatched-env", "unclosed-brace")
    ]
    assert [(r, ln) for r, ln, _ in got] == [
        ("unmatched-env", 2),
        ("unmatched-env", 4),
        ("unclosed-brace", 9),
        ("unclosed-brace", 10),
    ]
    assert "missing \\end{figure}" in got[0][2] and "2 unclosed {" in got[3][2]
    clean = "\\begin{document}\\section{A {nested} one}\\begin{itemize}\\item x\\end{itemize}\\end{document}"
    assert L.lint_files([("m.tex", clean)])["count"] == 0


def test_the_editor_relies_on_the_one_lint():
    src = Path("frontend/src/editor/index.ts").read_text()
    assert "enableLinting: false" in src
