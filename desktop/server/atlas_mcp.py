"""Frozen entrypoint for the bundled Atlas MCP server (`atlas-mcp`).

PyInstaller packages this into a standalone stdio MCP server that ships inside the desktop
installer, so Claude Code can drive the installed app with one registration line:

    claude mcp add atlas -- /path/to/atlas-mcp

With no ATLAS_API_URL / ATLAS_API_KEY in the environment it discovers both from the desktop
app's data directory (api_key + server.json). Explicit env vars always win.
"""

import os
import sys

if not getattr(sys, "frozen", False):
    # running from the checkout (`python desktop/server/atlas_mcp.py`): make mcp_server importable
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def main():
    from mcp_server import desktop_config

    try:
        desktop_config.apply_env()
    except LookupError as exc:
        # stderr reaches `claude mcp list` / the MCP client's error output; stdout is the
        # MCP transport and must stay clean.
        print(f"atlas-mcp: {exc}", file=sys.stderr)
        sys.exit(2)

    from mcp_server.server import mcp

    try:
        mcp.run()
    finally:
        # The stdio transport closes sys.stdout's buffer on the way out; PyInstaller's exit
        # code then flushes sys.stdout AND sys.__stdout__ and would print "ValueError: I/O
        # operation on closed file". Point both at a fresh sink so shutdown is silent.
        sys.stdout = sys.__stdout__ = open(os.devnull, "w")  # noqa: SIM115


if __name__ == "__main__":
    main()
