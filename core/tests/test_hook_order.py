"""Rules of hooks, statically (hotfix 2026-09-07).

A React hook placed below an early `return` changes the hook count between the loading render
and the loaded one; React then throws #310 and the whole page is blank — the desktop build
0.1.99–0.1.10x shipped a blank dashboard that way. There is no eslint in this repo, so this
walks every component and refuses a hook call after a top-level early return.
"""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
COMPONENT = re.compile(r"^(?:export default function|export function|function)\s+([A-Z]\w*)")
EARLY_RETURN = re.compile(r"^  (?:if \(.*\)\s*)?return\b")
HOOK = re.compile(r"\buse[A-Z]\w*\(")


def hooks_after_early_return() -> list[str]:
    offenders = []
    for path in FRONTEND.rglob("*.tsx"):
        lines = path.read_text().split("\n")
        component, returned = None, False
        for i, line in enumerate(lines, 1):
            m = COMPONENT.match(line)
            if m:
                component, returned = m.group(1), False
                continue
            if component is None:
                continue
            if line.startswith("}"):
                component = None
                continue
            two_line_if = (
                re.match(r"^  if \(.*\)$", line)
                and i < len(lines)
                and lines[i].lstrip().startswith("return")
            )
            if EARLY_RETURN.match(line) or two_line_if:
                returned = True
            if returned and HOOK.search(line) and not line.lstrip().startswith("//"):
                offenders.append(
                    f"{path.relative_to(FRONTEND)}:{i} in {component}: {line.strip()[:80]}"
                )
    return offenders


def test_no_hook_after_an_early_return():
    assert hooks_after_early_return() == []


def test_the_scan_catches_the_dashboard_shape(tmp_path, monkeypatch):
    sample = tmp_path / "Broken.tsx"
    sample.write_text(
        "export default function Broken() {\n  const q = useQuery();\n  if (q.isLoading) return null;\n  const w = useQuery();\n  return <div />;\n}\n"
    )
    monkeypatch.setattr("core.tests.test_hook_order.FRONTEND", tmp_path)
    assert hooks_after_early_return() == ["Broken.tsx:4 in Broken: const w = useQuery();"]
