"""Everything the "Connect Claude Code" page needs to hand the user a working one-liner.

Two shapes of install:
- **Desktop build** (ATLAS_MCP_BIN set by the Tauri shell): the frozen `atlas-mcp` sits inside
  the installed app and discovers the URL + API key from the data dir by itself, so the
  registration line carries no secrets: `claude mcp add atlas -- "<path to atlas-mcp>"`.
- **Dev / server install**: the MCP server runs from this checkout's Python, and the line
  passes ATLAS_API_URL + ATLAS_API_KEY explicitly.
"""

import json
import os
import shlex
import sys
from pathlib import Path

from django.conf import settings

from mcp_server import desktop_config

SERVER_NAME = "atlas"


def _quote(arg: str) -> str:
    """Quote one shell argument for the machine the command will be pasted on: the app runs
    on the same machine as the browser, so os.name decides (cmd/PowerShell vs POSIX)."""
    if os.name == "nt":
        return f'"{arg}"' if (" " in arg or not arg) else arg
    return shlex.quote(arg)


def _custom_data_dir() -> str | None:
    """The data dir when it is NOT one atlas-mcp would find on its own (then the command must
    pass it along); None when discovery will work unaided."""
    explicit = os.environ.get("ATLAS_DATA_DIR")
    if not explicit:
        return None
    env = {k: v for k, v in os.environ.items() if k != "ATLAS_DATA_DIR"}
    defaults = {Path(d).resolve() for d in desktop_config.default_data_dirs(environ=env)}
    return None if Path(explicit).resolve() in defaults else explicit


def connection_info(request) -> dict:
    api_url = f"{request.scheme}://{request.get_host()}".rstrip("/")
    api_key = settings.ATLAS_API_KEY
    mcp_bin = os.environ.get("ATLAS_MCP_BIN") or ""
    desktop = bool(mcp_bin)

    if desktop:
        command, args = mcp_bin, []
        env = {}
        custom = _custom_data_dir()
        if custom:
            env["ATLAS_DATA_DIR"] = custom
    else:
        command, args = sys.executable, ["-m", "mcp_server.server"]
        env = {"ATLAS_API_URL": api_url, "ATLAS_API_KEY": api_key}

    parts = ["claude", "mcp", "add", SERVER_NAME]
    for key, value in env.items():
        parts += ["--env", f"{key}={value}"]
    parts += ["--", command, *args]
    claude_command = " ".join(_quote(part) for part in parts)

    mcp_json = json.dumps(
        {"mcpServers": {SERVER_NAME: {"command": command, "args": args, "env": env}}},
        indent=2,
    )
    return {
        "desktop": desktop,
        "api_url": api_url,
        "api_key": api_key,
        "api_key_configured": bool(api_key),
        "command": command,
        "args": args,
        "env": env,
        "claude_command": claude_command,
        "mcp_json": mcp_json,
        "data_dir": str(getattr(settings, "DATA_DIR", "")) or None,
    }
