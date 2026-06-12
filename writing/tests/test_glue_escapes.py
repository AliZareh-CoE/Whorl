"""Escape discipline guard (Backlog #151, from AUDIT #14).

The LaTeX editor glue builds some DOM with innerHTML templates. Reference titles,
authors, note titles, and hypothesis statements reach the research panel from
external metadata (Crossref/OpenAlex/BibTeX), so every `${...}` interpolated into
an innerHTML string MUST go through esc(). This static check fails the build if a
new unescaped interpolation slips in — cheaper than catching it in another audit.
"""

import re
from pathlib import Path

from django.conf import settings

GLUE = Path(settings.BASE_DIR) / "static" / "js" / "latex-editor.js"

# innerHTML = <one or more string literals / parenthesised exprs joined by +>
_INNERHTML_RHS = re.compile(
    r"""innerHTML\s*=\s*((?:`[^`]*`|'[^']*'|"[^"]*"|\s*\+\s*|\([^)]*\))+)""",
)
_INTERP = re.compile(r"\$\{([^}]*)\}")


def test_every_innerhtml_interpolation_is_escaped():
    source = GLUE.read_text()
    offenders = []
    for match in _INNERHTML_RHS.finditer(source):
        for interp in _INTERP.finditer(match.group(1)):
            expr = interp.group(1).strip()
            if not expr.startswith("esc("):
                offenders.append(expr)
    assert not offenders, (
        "Unescaped innerHTML interpolation(s) in latex-editor.js — wrap in esc(): "
        + ", ".join(offenders)
    )


def test_esc_helper_exists():
    assert "function esc(" in GLUE.read_text()
