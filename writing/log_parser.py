"""Tectonic compile-log parsing (Owner idea #24, parity slice 1).

Turns raw compiler output into structured diagnostics the editor can render as
inline markers: [{"level", "file", "line", "message"}]. Tectonic's surface format
is much cleaner than raw TeX logs:

    error: main.tex:4: Undefined control sequence
    warning: main.tex:12: Citation `nokey' undefined
    error: halted on potentially-recoverable error as specified

LaTeX's own warnings can also appear inside captured logs:

    LaTeX Warning: Reference `nolabel' on page 1 undefined on input line 3.
"""

import re

LOCATED = re.compile(r"^(error|warning):\s+([^\s:]+\.\w+):(\d+):\s*(.+)$")
BARE = re.compile(r"^(error|warning):\s*(.+)$")
LATEX_WARNING = re.compile(r"^LaTeX Warning:\s*(.+?)(?:\s+on input line (\d+)\.?)?$")

# Process chatter, not actionable for the author.
NOISE = (
    "halted on potentially-recoverable error",
    "the TeX engine had an issue",
)


def parse_compile_log(log: str) -> list[dict]:
    """Structured diagnostics from a Tectonic run, source-located ones first."""
    diagnostics = []
    for raw in (log or "").splitlines():
        line = raw.strip()
        match = LOCATED.match(line)
        if match:
            level, filename, lineno, message = match.groups()
            diagnostics.append(
                {"level": level, "file": filename, "line": int(lineno), "message": message}
            )
            continue
        match = LATEX_WARNING.match(line)
        if match:
            message, lineno = match.groups()
            diagnostics.append(
                {
                    "level": "warning",
                    "file": "main.tex",
                    "line": int(lineno) if lineno else None,
                    "message": message,
                }
            )
            continue
        match = BARE.match(line)
        if match:
            level, message = match.groups()
            if any(noise in message for noise in NOISE):
                continue
            diagnostics.append({"level": level, "file": None, "line": None, "message": message})
    diagnostics.sort(key=lambda d: (d["line"] is None, d["line"] or 0))
    return diagnostics
