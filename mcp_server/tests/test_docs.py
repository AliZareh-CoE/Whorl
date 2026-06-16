"""The README's MCP tool list must stay in sync with the actual @mcp.tool functions (#261).

The list was hand-maintained and had drifted (the manuscript/LaTeX + figures tools were
missing, and the intro count was stale). This guard fails the build if a tool is added to
server.py without being documented, so it can't silently drift again.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _tool_names() -> set[str]:
    src = (ROOT / "mcp_server" / "server.py").read_text()
    # every function decorated with @mcp.tool() is a tool the README should list
    return set(re.findall(r"@mcp\.tool\(\)\s*\ndef\s+([a-z_]+)\s*\(", src))


def test_readme_documents_every_mcp_tool():
    readme = (ROOT / "README.md").read_text()
    tools = _tool_names()
    assert tools, "no @mcp.tool functions found — the parser is broken"
    missing = sorted(t for t in tools if f"`{t}`" not in readme)
    assert not missing, f"README MCP tool list is missing: {missing}"


def test_readme_tool_count_is_accurate():
    readme = (ROOT / "README.md").read_text()
    count = len(_tool_names())
    # the intro brags about the tool count; it must match reality (was stuck at "16 tools")
    assert f"{count} tools" in readme, f"README should say '{count} tools'"
