"""The Connect page's live connection test (backlog #290)."""

import json
from types import SimpleNamespace

import pytest

from core import mcp_connect

check = mcp_connect.test_connection

pytestmark = pytest.mark.django_db


class Req:
    scheme = "http"

    def get_host(self):
        return "127.0.0.1:8000"


def ok_fetch(url, headers=None, timeout=None):
    assert headers["X-API-Key"] == "k"
    return SimpleNamespace(status_code=200)


def ok_run(cmd, **kw):
    assert cmd[-1] == "--check"
    assert kw["env"]["ATLAS_API_KEY"] == "k"
    return SimpleNamespace(
        returncode=0, stdout=json.dumps({"ok": True, "tools": 88, "projects": 2}), stderr=""
    )


def test_all_green(settings, monkeypatch):
    settings.ATLAS_API_KEY = "k"
    monkeypatch.delenv("ATLAS_MCP_BIN", raising=False)
    out = check(Req(), fetch=ok_fetch, run=ok_run, which=lambda n: "/usr/bin/claude")
    assert out["ok"] is True
    assert [c["key"] for c in out["checks"]] == ["api_key", "api", "mcp", "claude"]
    assert all(c["ok"] for c in out["checks"])
    assert "88 tools" in out["checks"][2]["detail"]
    assert out["command"].endswith("-m mcp_server.server --check")


def test_connection_test_says_loaded_of_total_when_the_check_reports_it(settings, monkeypatch):
    """#540: the default is the core toolset, so the phrase reads "25 of 158 tools loaded"."""
    settings.ATLAS_API_KEY = "k"
    monkeypatch.delenv("ATLAS_MCP_BIN", raising=False)

    def run(cmd, **kw):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"ok": True, "tools": 25, "tools_total": 158, "projects": 2}),
            stderr="",
        )

    out = check(Req(), fetch=ok_fetch, run=run, which=lambda n: "/usr/bin/claude")
    assert "25 of 158 tools loaded · sees 2 project(s)" == out["checks"][2]["detail"]
