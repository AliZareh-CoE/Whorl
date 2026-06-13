"""The built-in terminal is desktop-only and never web-reachable (Owner #30, slice 5).

A terminal is arbitrary local code execution by design — fine in the single-user desktop
shell (like VS Code), but it must NEVER be exposed through the Django web API, the URL
routes, or the MCP server. This fails the build if any PTY/terminal surface leaks out of
the desktop/ crate into the web/MCP layers.
"""

import re
from pathlib import Path

from django.conf import settings

ROOT = Path(settings.BASE_DIR)
# PTY / terminal-spawn signatures that must not appear outside desktop/
FORBIDDEN = re.compile(r"portable[_-]pty|terminal_spawn|openpty|pty\.spawn|ConPTY|/bin/bash", re.I)
WEB_DIRS = ["api", "mcp_server", "core", "documents", "writing", "config"]


def test_no_terminal_surface_in_web_or_mcp():
    offenders = []
    for d in WEB_DIRS:
        for path in (ROOT / d).rglob("*.py"):
            if "test_terminal_isolation" in path.name:
                continue  # this guard names the patterns on purpose
            if FORBIDDEN.search(path.read_text()):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, "Terminal/PTY surface leaked into the web/MCP layer:\n" + "\n".join(
        offenders
    )


def test_terminal_lives_only_in_desktop_crate():
    assert (ROOT / "desktop" / "src" / "terminal.rs").exists()
    main = (ROOT / "desktop" / "src" / "main.rs").read_text()
    assert "terminal_spawn" in main  # registered as a desktop IPC command


def test_terminal_handlers_registered_once():
    main = (ROOT / "desktop" / "src" / "main.rs").read_text()
    for cmd in ("terminal_spawn", "terminal_write", "terminal_resize"):
        assert main.count(cmd) == 1
