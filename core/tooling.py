"""What is installed on this machine (Connect page, 2026-09-06): the terminal's "Claude" tab
runs `claude`, the studio needs the LaTeX engine, git/node are nice to know. Detection is a
PATH lookup plus a guarded `--version`, never anything slower."""

from __future__ import annotations

import shutil
import subprocess
import sys

TOOLS = [
    ("claude", "Claude Code", "npm i -g @anthropic-ai/claude-code"),
    ("node", "Node.js", "https://nodejs.org"),
    ("git", "git", "https://git-scm.com"),
]


def _version(path: str) -> str:
    try:
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=6,
            encoding="utf-8",
            errors="replace",
            **kwargs,
        )
        line = (out.stdout or out.stderr).strip().splitlines()
        return line[0][:60] if line else ""
    except Exception:
        return ""


def detect_tools(which=shutil.which, version=_version) -> list[dict]:
    from writing.compile import tectonic_path

    rows = []
    for cmd, label, install in TOOLS:
        path = which(cmd)
        rows.append(
            {
                "key": cmd,
                "label": label,
                "found": bool(path),
                "path": path or None,
                "version": version(path) if path else "",
                "install": install,
            }
        )
    engine = tectonic_path()
    rows.append(
        {
            "key": "tectonic",
            "label": "LaTeX engine (Tectonic)",
            "found": engine is not None,
            "path": str(engine) if engine else None,
            "version": "",
            "install": "bundled with the desktop app · `make tectonic` in a checkout",
        }
    )
    return rows
