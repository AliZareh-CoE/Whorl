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


def test_missing_key_fails_first_two_checks(settings, monkeypatch):
    settings.ATLAS_API_KEY = ""
    monkeypatch.delenv("ATLAS_MCP_BIN", raising=False)
    out = check(Req(), fetch=ok_fetch, run=ok_run, which=lambda n: None)
    by = {c["key"]: c for c in out["checks"]}
    assert out["ok"] is False
    assert not by["api_key"]["ok"] and "ATLAS_API_KEY" in by["api_key"]["fix"]
    assert not by["api"]["ok"]
    assert not by["claude"]["ok"] and "npm i -g" in by["claude"]["fix"]


def test_mcp_failure_reports_its_error(settings, monkeypatch):
    settings.ATLAS_API_KEY = "k"
    monkeypatch.delenv("ATLAS_MCP_BIN", raising=False)

    def bad_run(cmd, **kw):
        return SimpleNamespace(
            returncode=1,
            stdout=json.dumps({"ok": False, "error": "401 from /projects/"}),
            stderr="",
        )

    def bad_fetch(url, headers=None, timeout=None):
        return SimpleNamespace(status_code=401)

    out = check(Req(), fetch=bad_fetch, run=bad_run, which=lambda n: "/x/claude")
    by = {c["key"]: c for c in out["checks"]}
    assert not by["api"]["ok"] and "401" in by["api"]["detail"]
    assert not by["mcp"]["ok"] and "401 from /projects/" in by["mcp"]["detail"]


def test_missing_binary_is_named(settings, monkeypatch):
    settings.ATLAS_API_KEY = "k"
    monkeypatch.setenv("ATLAS_MCP_BIN", "/opt/atlas/atlas-mcp")

    def missing(cmd, **kw):
        raise FileNotFoundError(cmd[0])

    out = check(Req(), fetch=ok_fetch, run=missing, which=lambda n: None)
    by = {c["key"]: c for c in out["checks"]}
    assert by["mcp"]["detail"] == "/opt/atlas/atlas-mcp not found"


def test_api_endpoint(client_logged_in, settings, monkeypatch):
    settings.ATLAS_API_KEY = "k"
    monkeypatch.setattr(
        "core.mcp_connect.test_connection",
        lambda request: {"ok": True, "checks": [], "command": "x"},
    )
    response = client_logged_in.post("/api/v1/connect/test/")
    assert response.status_code == 200
    assert response.json()["ok"] is True
