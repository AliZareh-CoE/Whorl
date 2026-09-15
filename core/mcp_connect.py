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

from mcp_server import desktop_config, toolsets

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
        "toolsets": toolsets.describe(),  # #540: what is on by default, what Claude can enable
        "tools_total": len(toolsets.all_tools()),
    }


def test_connection(request, *, fetch=None, run=None, which=None) -> dict:
    """Live proof that Claude Code will be able to talk to this install (backlog #290).

    Four checks, each with a fix when it fails: the API key exists; the API answers that key
    at the URL the command carries; the exact MCP command Claude Code would launch starts and
    reaches the API (``--check``); the ``claude`` CLI is on PATH. `fetch`, `run` and `which`
    are injectable for tests.
    """
    import shutil
    import subprocess

    import httpx

    fetch = fetch or httpx.get
    run = run or subprocess.run
    which = which or shutil.which
    info = connection_info(request)
    checks: list[dict] = []

    def add(key, label, ok, detail="", fix=""):
        checks.append(
            {"key": key, "label": label, "ok": bool(ok), "detail": detail, "fix": "" if ok else fix}
        )

    add(
        "api_key",
        "API key configured",
        info["api_key_configured"],
        "" if info["api_key_configured"] else "ATLAS_API_KEY is empty",
        "Set ATLAS_API_KEY (the desktop app mints one on first launch) and restart.",
    )

    api_ok, api_detail = False, ""
    if info["api_key_configured"]:
        url = f"{info['api_url']}/api/v1/projects/?page_size=1"
        try:
            response = fetch(url, headers={"X-API-Key": info["api_key"]}, timeout=5.0)
            api_ok = response.status_code == 200
            api_detail = f"GET {url} → {response.status_code}"
        except Exception as exc:  # noqa: BLE001 - reported as a failed check
            api_detail = f"GET {url} failed: {exc}"
    add(
        "api",
        "API answers with this key",
        api_ok,
        api_detail,
        "The server must be reachable at that URL and accept the key — open Diagnostics for the log.",
    )

    mcp_ok, mcp_detail = False, ""
    cmd = [info["command"], *info["args"], "--check"]
    try:
        env = {**os.environ, **info["env"]}
        proc = run(cmd, capture_output=True, text=True, timeout=45, env=env)
        last = (proc.stdout or "").strip().splitlines()
        parsed = None
        if last:
            try:
                parsed = json.loads(last[-1])
            except ValueError:
                parsed = None
        if proc.returncode == 0 and parsed and parsed.get("ok"):
            mcp_ok = True
            mcp_detail = (
                f"{parsed.get('tools', '?')} tools · sees {parsed.get('projects', '?')} project(s)"
            )
        else:
            err = (
                (parsed or {}).get("error")
                or (proc.stderr or "").strip().splitlines()[-3:]
                or f"exit {proc.returncode}"
            )
            mcp_detail = err if isinstance(err, str) else " / ".join(err)
    except FileNotFoundError:
        mcp_detail = f"{info['command']} not found"
    except Exception as exc:  # noqa: BLE001
        mcp_detail = str(exc)
    add(
        "mcp",
        "MCP server starts and reaches the API",
        mcp_ok,
        mcp_detail,
        "This is the command in step 1. If the file is missing, reinstall the app; otherwise the error above says what it hit.",
    )

    claude_path = which("claude")
    add(
        "claude",
        "Claude Code on this machine",
        bool(claude_path),
        claude_path or "not on PATH",
        "npm i -g @anthropic-ai/claude-code, then run the step-1 command.",
    )

    return {"ok": all(c["ok"] for c in checks), "checks": checks, "command": " ".join(cmd)}
