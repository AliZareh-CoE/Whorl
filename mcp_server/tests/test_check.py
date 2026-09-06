"""`python -m mcp_server.server --check` proves the wiring without an MCP client."""

import json

import httpx
import pytest

from mcp_server import client, server


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("ATLAS_API_URL", "http://testserver")
    monkeypatch.setenv("ATLAS_API_KEY", "k")
    state = {"status": 200}

    def fake_client():
        def handler(request):
            return httpx.Response(state["status"], json={"count": 3, "results": []})

        return httpx.Client(
            base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(client, "_client", fake_client)
    return state


def test_self_check_counts_tools_and_projects(api):
    out = server.self_check()
    assert out["ok"] is True
    assert out["projects"] == 3
    assert out["tools"] >= 80
    assert out["api_url"] == "http://testserver"


def test_self_check_reports_api_failures(api):
    api["status"] = 401
    out = server.self_check()
    assert out["ok"] is False
    assert "401" in out["error"]


def test_main_check_prints_json_and_exit_code(api, capsys):
    assert server.main(["--check"]) == 0
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert printed["ok"] is True
    api["status"] = 500
    assert server.main(["--check"]) == 1


def test_entry_point_is_the_last_statement():
    """`python -m mcp_server.server` must register every tool before main() runs."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(server.__file__).read_text())
    last = tree.body[-1]
    assert isinstance(last, ast.If) and "__main__" in ast.unparse(last.test)
    decorated = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.decorator_list]
    assert tree.body.index(decorated[-1]) < tree.body.index(last)


def test_module_run_counts_every_tool(monkeypatch):
    import subprocess
    import sys

    env = {"ATLAS_API_URL": "http://127.0.0.1:9", "ATLAS_API_KEY": "k", "PATH": "/usr/bin"}
    # the API is unreachable on purpose: the check must still start, i.e. the whole module
    # loads and the failure is reported as JSON, not a traceback
    proc = subprocess.run(
        [sys.executable, "-m", "mcp_server.server", "--check"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 1
    assert '"ok": false' in proc.stdout
