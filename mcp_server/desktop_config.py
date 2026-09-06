"""Zero-config discovery for the desktop build's MCP server.

The installed Atlas desktop app keeps an API key and a `server.json` (the URL it is serving
on) in its per-user data directory. When the frozen `atlas-mcp` binary starts with no
ATLAS_API_URL / ATLAS_API_KEY in its environment, it looks there — so registering Atlas in
Claude Code is one line with no secrets to copy:

    claude mcp add atlas -- /path/to/atlas-mcp

Deliberately Django-free (like the rest of mcp_server): plain files and env vars only.
"""

import json
import os
import sys
from pathlib import Path

APP_ID = "com.atlas.research"  # Tauri identifier → the OS app-data folder name
API_KEY_FILE = "api_key"
SERVER_FILE = "server.json"
DEFAULT_URL = "http://127.0.0.1:8000"


def default_data_dirs(platform: str | None = None, environ=None) -> list[Path]:
    """Candidate data dirs, most specific first: ATLAS_DATA_DIR if set, else the Tauri
    app-data folder for this OS, then the standalone-server fallback (~/.atlas)."""
    env = os.environ if environ is None else environ
    explicit = env.get("ATLAS_DATA_DIR")
    if explicit:
        return [Path(explicit)]
    platform = platform or sys.platform
    home = Path(env.get("HOME") or Path.home()) if platform != "win32" else Path.home()
    dirs: list[Path] = []
    if platform == "win32":
        appdata = env.get("APPDATA")
        if appdata:
            dirs.append(Path(appdata) / APP_ID)
    elif platform == "darwin":
        dirs.append(home / "Library" / "Application Support" / APP_ID)
    else:
        xdg = env.get("XDG_DATA_HOME")
        dirs.append(Path(xdg) / APP_ID if xdg else home / ".local" / "share" / APP_ID)
    dirs.append(home / ".atlas")
    return dirs


def discover(platform: str | None = None, environ=None) -> dict:
    """Find the desktop app's API key (+ current URL). Raises LookupError with an actionable
    message when no launched desktop install is found."""
    candidates = default_data_dirs(platform, environ)
    for data_dir in candidates:
        key_file = data_dir / API_KEY_FILE
        if not key_file.is_file():
            continue
        api_key = key_file.read_text(encoding="utf-8").strip()
        if not api_key:
            continue
        url = DEFAULT_URL
        server_file = data_dir / SERVER_FILE
        if server_file.is_file():
            try:
                url = json.loads(server_file.read_text(encoding="utf-8")).get("url") or url
            except (OSError, ValueError):
                pass
        return {"data_dir": str(data_dir), "api_key": api_key, "url": url.rstrip("/")}
    looked = ", ".join(str(d) for d in candidates)
    raise LookupError(
        "No Atlas desktop data directory found (looked in: "
        f"{looked}). Launch the Atlas desktop app once so it creates its API key, or set "
        "ATLAS_API_URL and ATLAS_API_KEY (or ATLAS_DATA_DIR) in the MCP server's environment."
    )


def apply_env(environ=None) -> dict | None:
    """Fill in ATLAS_API_URL / ATLAS_API_KEY from the desktop install when they are missing.
    Explicit values always win. Returns the discovered info, or None when nothing was needed."""
    env = os.environ if environ is None else environ
    if env.get("ATLAS_API_KEY") and env.get("ATLAS_API_URL"):
        return None
    try:
        info = discover(environ=env)
    except LookupError:
        if env.get("ATLAS_API_KEY"):
            return None  # key given explicitly; the URL falls back to the client's default
        raise
    env.setdefault("ATLAS_API_URL", info["url"])
    env.setdefault("ATLAS_API_KEY", info["api_key"])
    return info
