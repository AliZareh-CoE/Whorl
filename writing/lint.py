"""LaTeX style lint (#470): the mistakes a compile never reports.

Pure functions over the manuscript's .tex files. Every finding names the file, line and
column, a stable rule id, a level (``error`` for text that will print wrong, ``warning`` for
style), a one-line message and, where one is obvious, the suggested replacement. Comments,
``verbatim``-like environments and ``\\url{}`` arguments are skipped so a rule never fires on
text LaTeX itself ignores.
"""

from __future__ import annotations

import re

SKIP_ENVS = ("verbatim", "lstlisting", "minted", "comment", "Verbatim", "BVerbatim")
TABLE_ENVS = (
    "tabular",
    "tabularx",
    "tabu",
    "longtable",
    "array",
    "matrix",
    "pmatrix",
    "bmatrix",
    "align",
    "align*",
    "aligned",
    "cases",
    "eqnarray",
    "split",
    "gather",
    "gather*",
    "tabbing",
    "verse",
)
FLOAT_ENVS = ("figure", "figure*", "table", "table*", "wrapfigure", "subfigure", "algorithm")
REF_MACROS = r"(?:ref|eqref|cref|Cref|autoref|pageref|vref|nameref)"
UNITS = (
    r"(?:ms|s|Hz|kHz|MHz|GHz|mm|cm|km|kg|mg|µs|us|ns|nm|µm|dB|mV|mA|GB|MB|TB|kB|px|"
    r"fps|min|h|rpm|bpm|Da|kDa|mol|mM|µM|nM|K|°C)"
)

RULES: dict[str, str] = {
    "percent": "Unescaped % after a number comments out the rest of the line.",
    "label-before-caption": "\\label placed before \\caption refers to the previous number.",
    "duplicate-label": "The same \\label appears more than once.",
    "undefined-ref": "\\ref to a label that is not defined anywhere in the sources.",
    "nbsp-ref": "A plain space before \\ref lets the number wrap to the next line.",
    "unit-space": "A plain space between a number and its unit can wrap.",
    "ellipsis": "Three dots print too tight; use \\ldots.",
    "quotes": "Straight double quotes print as closing quotes in LaTeX.",
    "display-math": "$$ is plain TeX; use \\[ ... \\] so spacing and fleqn options apply.",
    "center-env": "\\begin{center} inside a float adds vertical space; use \\centering.",
    "linebreak": "\\\\ at the end of a prose line is not a paragraph break; use a blank line.",
    "unlabeled-float": "A captioned float without a \\label cannot be referenced.",
    "abbrev": "e.g. / i.e. read better followed by a comma.",
    "unmatched-env": "An environment is opened and never closed, or closed without being opened.",
    "unclosed-brace": "A { is never closed, or a } closes nothing — the compile stops here.",
}

NBSP_REF = re.compile(
    r"\b(Fig\.|Figs\.|Figure|Figures|Table|Tables|Section|Sections|Sec\.|Eq\.|Eqs\.|Equation|"
    r"Chapter|Appendix|Algorithm|Theorem|Lemma|Listing|Definition|Corollary|Proposition)"
    r"( )(\(?\\" + REF_MACROS + r"\{)"
)
UNIT_SPACE = re.compile(r"(?<![\w.\\])(\d+(?:\.\d+)?)( )(" + UNITS + r")(?![\w])")
ELLIPSIS = re.compile(r"(?<!\.)\.\.\.(?!\.)")
QUOTES = re.compile(r'(?<![\\\w])"([^"\n]{1,200})"')
DISPLAY = re.compile(r"(?<!\\)\$\$")
ABBREV = re.compile(r"\b(e\.g\.|i\.e\.)( )(?=[a-z])")
LABEL = re.compile(r"\\label\{([^}]*)\}")
REF = re.compile(r"\\" + REF_MACROS + r"\{([^}]*)\}")
CAPTION = re.compile(r"\\caption(?:\[[^\]]*\])?\s*\{")
BEGIN = re.compile(r"\\begin\{([^}]*)\}")
END = re.compile(r"\\end\{([^}]*)\}")
LINEBREAK = re.compile(r"(?<!\\)\\\\(?:\[[^\]]*\])?\s*$")
URL_ARG = re.compile(r"\\(?:url|href|path|texttt|verb)\{[^}]*\}")


def _strip_comment(line: str) -> str:
    """Drop everything after an unescaped % (the percent rule runs on the raw line first)."""
    out = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            out.append(line[i : i + 2])
            i += 2
            continue
        if ch == "%":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def _finding(path, line, col, rule, level, message, fix=None) -> dict:
    out = {
        "file": path,
        "line": line,
        "col": col,
        "rule": rule,
        "level": level,
        "message": message,
    }
    if fix:
        out["fix"] = fix
    return out


def lint_text(
    path: str, text: str
) -> tuple[list[dict], list[tuple[str, int]], list[tuple[str, int]]]:
    """Lint one file. Returns (findings, labels, refs) where labels/refs are (key, line) pairs
    so the caller can run the cross-file rules."""
    findings: list[dict] = []
    labels: list[tuple[str, int]] = []
    refs: list[tuple[str, int]] = []
    env_stack: list[str] = []
    # per open float: (env, line, seen_caption, seen_label, label_before_caption_line)
    floats: list[dict] = []
    for n, raw in enumerate(text.splitlines(), 1):
        if env_stack and env_stack[-1] in SKIP_ENVS:
            if END.search(raw) and END.search(raw).group(1) == env_stack[-1]:
                env_stack.pop()
            continue
        stripped = raw.lstrip()
        if stripped.startswith("%"):
            continue
        # the percent rule looks at the FIRST unescaped %: when a digit precedes it, the
        # author meant a literal percent and the rest of the line silently became a comment
        line = _strip_comment(raw)
        cut = len(line)
        if cut < len(raw) and cut > 0 and raw[cut - 1].isdigit() and not URL_ARG.search(raw):
            digit = raw[cut - 1]
            findings.append(
                _finding(
                    path,
                    n,
                    cut + 1,
                    "percent",
                    "error",
                    f"'{digit}%' — the rest of this line is a comment. Write {digit}\\%.",
                    f"{digit}\\%",
                )
            )
        clean = URL_ARG.sub(lambda mm: " " * len(mm.group(0)), line)
        for m in BEGIN.finditer(clean):
            env = m.group(1)
            env_stack.append(env)
            if env in FLOAT_ENVS:
                floats.append({"env": env, "line": n, "caption": False, "label": False})
            elif env == "center" and floats:
                findings.append(
                    _finding(
                        path,
                        n,
                        m.start() + 1,
                        "center-env",
                        "warning",
                        f"\\begin{{center}} inside {floats[-1]['env']} — use \\centering.",
                        "\\centering",
                    )
                )
        if floats:
            fl = floats[-1]
            if CAPTION.search(clean):
                fl["caption"] = True
            for m in LABEL.finditer(clean):
                fl["label"] = True
                if not fl["caption"]:
                    findings.append(
                        _finding(
                            path,
                            n,
                            m.start() + 1,
                            "label-before-caption",
                            "error",
                            f"\\label{{{m.group(1)}}} comes before \\caption — it will number the previous float or section.",
                        )
                    )
        for m in LABEL.finditer(clean):
            labels.append((m.group(1).strip(), n))
        for m in REF.finditer(clean):
            for key in m.group(1).split(","):
                key = key.strip()
                if key and "#" not in key and "\\" not in key:
                    refs.append((key, n))
        in_table = any(e in TABLE_ENVS for e in env_stack)
        if not in_table:
            for m in NBSP_REF.finditer(clean):
                findings.append(
                    _finding(
                        path,
                        n,
                        m.start(2) + 1,
                        "nbsp-ref",
                        "warning",
                        f"'{m.group(1)} \\ref' — tie them with ~ so the number cannot wrap.",
                        f"{m.group(1)}~{m.group(3)}",
                    )
                )
            for m in UNIT_SPACE.finditer(clean):
                findings.append(
                    _finding(
                        path,
                        n,
                        m.start(2) + 1,
                        "unit-space",
                        "warning",
                        f"'{m.group(1)} {m.group(3)}' — use {m.group(1)}\\,{m.group(3)} or {m.group(1)}~{m.group(3)}.",
                        f"{m.group(1)}\\,{m.group(3)}",
                    )
                )
            m = LINEBREAK.search(clean)
            if m and not clean.strip().startswith("\\") and not floats:
                findings.append(
                    _finding(
                        path,
                        n,
                        m.start() + 1,
                        "linebreak",
                        "warning",
                        "\\\\ at the end of a prose line — leave a blank line for a paragraph break.",
                    )
                )
        for m in ELLIPSIS.finditer(clean):
            findings.append(
                _finding(
                    path, n, m.start() + 1, "ellipsis", "warning", "'...' — use \\ldots.", "\\ldots"
                )
            )
        for m in QUOTES.finditer(clean):
            findings.append(
                _finding(
                    path,
                    n,
                    m.start() + 1,
                    "quotes",
                    "warning",
                    f"\"{m.group(1)[:30]}\" — LaTeX quotes are ``like this''.",
                    f"``{m.group(1)}''",
                )
            )
        m = DISPLAY.search(clean)
        if m:
            findings.append(
                _finding(
                    path,
                    n,
                    m.start() + 1,
                    "display-math",
                    "warning",
                    "$$ … $$ — use \\[ … \\].",
                    "\\[",
                )
            )
        for m in ABBREV.finditer(clean):
            findings.append(
                _finding(
                    path,
                    n,
                    m.start() + 1,
                    "abbrev",
                    "warning",
                    f"'{m.group(1)}' — follow it with a comma.",
                    f"{m.group(1)},",
                )
            )
        for m in END.finditer(clean):
            env = m.group(1)
            if env_stack and env_stack[-1] == env:
                env_stack.pop()
            elif env in env_stack:
                while env_stack and env_stack[-1] != env:
                    env_stack.pop()
                if env_stack:
                    env_stack.pop()
            if env in FLOAT_ENVS and floats:
                fl = floats.pop()
                if fl["caption"] and not fl["label"]:
                    findings.append(
                        _finding(
                            path,
                            fl["line"],
                            1,
                            "unlabeled-float",
                            "warning",
                            f"This {fl['env']} has a caption but no \\label — it cannot be referenced.",
                        )
                    )
    findings.extend(_structure(path, text))
    return findings, labels, refs


def _structure(path: str, text: str) -> list[dict]:
    """#471: the two checks a compile does report, but only as the first cryptic error —
    environment pairing and brace balance across the whole file, comments and verbatim
    skipped. Ported from the editor's per-file linter so the panel is the one place."""
    out: list[dict] = []
    env_stack: list[tuple[str, int]] = []
    brace_stack: list[tuple[int, int]] = []  # (line, col)
    skip: str | None = None
    for n, raw in enumerate(text.splitlines(), 1):
        if skip:
            m = END.search(raw)
            if m and m.group(1) == skip:
                skip = None
            continue
        line = _strip_comment(URL_ARG.sub(lambda mm: " " * len(mm.group(0)), raw))
        # \verb|...| and \verb#...# take everything between their delimiters literally
        line = re.sub(r"\\verb\*?(\S)(.*?)\1", lambda mm: " " * len(mm.group(0)), line)
        for m in re.finditer(r"\\(begin|end)\{([^}]*)\}", line):
            kind, env = m.group(1), m.group(2).strip()
            if kind == "begin":
                if env in SKIP_ENVS:
                    skip = env
                    break
                env_stack.append((env, n))
            elif env_stack and env_stack[-1][0] == env:
                env_stack.pop()
            elif any(e == env for e, _ in env_stack):
                # closes an outer environment: everything opened since is unclosed
                while env_stack and env_stack[-1][0] != env:
                    inner, at = env_stack.pop()
                    out.append(
                        _finding(
                            path,
                            at,
                            1,
                            "unmatched-env",
                            "error",
                            f"\\begin{{{inner}}} is closed by \\end{{{env}}} at line {n} — missing \\end{{{inner}}}.",
                        )
                    )
                env_stack.pop()
            else:
                out.append(
                    _finding(
                        path,
                        n,
                        m.start() + 1,
                        "unmatched-env",
                        "error",
                        f"\\end{{{env}}} without a matching \\begin{{{env}}}.",
                    )
                )
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\":
                i += 2
                continue
            if ch == "{":
                brace_stack.append((n, i + 1))
            elif ch == "}":
                if brace_stack:
                    brace_stack.pop()
                else:
                    out.append(
                        _finding(
                            path, n, i + 1, "unclosed-brace", "error", "This } closes nothing."
                        )
                    )
            i += 1
    for env, at in env_stack:
        out.append(
            _finding(path, at, 1, "unmatched-env", "error", f"\\begin{{{env}}} is never closed.")
        )
    if brace_stack:
        ln, col = brace_stack[0]
        out.append(
            _finding(
                path,
                ln,
                col,
                "unclosed-brace",
                "error",
                f"{len(brace_stack)} unclosed {{ — the first is here.",
            )
        )
    return out


def lint_files(files: list[tuple[str, str]]) -> dict:
    """Lint every (path, text) pair plus the cross-file label rules."""
    findings: list[dict] = []
    all_labels: dict[str, list[tuple[str, int]]] = {}
    all_refs: list[tuple[str, str, int]] = []
    for path, text in files:
        f, labels, refs = lint_text(path, text or "")
        findings.extend(f)
        for key, line in labels:
            all_labels.setdefault(key, []).append((path, line))
        all_refs.extend((path, key, line) for key, line in refs)
    for key, places in all_labels.items():
        if len(places) > 1:
            first = places[0]
            for path, line in places[1:]:
                findings.append(
                    _finding(
                        path,
                        line,
                        1,
                        "duplicate-label",
                        "error",
                        f"\\label{{{key}}} is also defined at {first[0]}:{first[1]}.",
                    )
                )
    for path, key, line in all_refs:
        if key not in all_labels:
            findings.append(
                _finding(
                    path,
                    line,
                    1,
                    "undefined-ref",
                    "error",
                    f"\\ref{{{key}}} — no \\label{{{key}}} in the sources.",
                )
            )
    findings.sort(key=lambda f: (f["file"], f["line"], f["col"]))
    errors = sum(1 for f in findings if f["level"] == "error")
    return {
        "count": len(findings),
        "errors": errors,
        "warnings": len(findings) - errors,
        "files": len(files),
        "findings": findings,
        "rules": RULES,
    }


def lint_manuscript(manuscript) -> dict:
    files = list(manuscript.files.filter(kind="tex").order_by("path"))
    if files:
        pairs = [(f.path, f.content) for f in files]
    else:
        pairs = [("main.tex", manuscript.latex_source or "")]
    out = lint_files(pairs)
    out["manuscript"] = manuscript.id
    return out
