"""Toolsets (#540): a small default, the rest one enable_toolset away."""

import asyncio
import os
import sys
from collections import Counter

import pytest

from mcp_server import server, toolsets

ALL = toolsets.all_tools()


def _loaded() -> set[str]:
    return {t.name for t in server.mcp._tool_manager.list_tools()}


def test_every_registered_tool_is_in_exactly_one_area():
    registered = set(server._REGISTRY)
    assert registered == ALL, {
        "not in an area": sorted(registered - ALL),
        "in an area but not registered": sorted(ALL - registered),
    }
    counts = Counter(t for _, tools in toolsets.AREAS.values() for t in tools)
    assert [t for t, c in counts.items() if c > 1] == []


def test_core_is_small_and_real():
    assert set(toolsets.CORE) <= ALL
    assert len(toolsets.CORE) == len(set(toolsets.CORE)) <= toolsets.CORE_LIMIT
    assert {"list_toolsets", "enable_toolset"} <= set(toolsets.CORE)
    # the daily loop is covered without enabling anything
    for name in (
        "get_dashboard",
        "get_plan",
        "complete_milestone",
        "add_reference_by_doi",
        "quick_capture",
        "add_note",
        "get_diagnostics",
    ):
        assert name in toolsets.CORE, name


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, ["core"]),
        ("", ["core"]),
        ("  ", ["core"]),
        ("core", ["core"]),
        ("CORE, Library", ["core", "library"]),
        ("library writing library", ["library", "writing"]),
        ("all", list(toolsets.AREAS)),
        ("core,all", list(toolsets.AREAS)),
        ("nope", ["core"]),
        ("nope, studio", ["studio"]),
    ],
)
def test_parse(raw, expected):
    assert toolsets.parse(raw) == expected


def test_unknown_names_are_reported_not_fatal():
    assert toolsets.unknown("core, nope, Studio, x_y") == ["nope", "x_y"]
    assert toolsets.unknown(None) == []


def test_resolve_always_keeps_core():
    assert toolsets.resolve(["studio"]) >= set(toolsets.CORE)
    assert toolsets.resolve(["studio"]) >= set(toolsets.AREAS["studio"][1])
    assert toolsets.resolve(list(toolsets.AREAS)) == ALL


def test_describe_rows_carry_what_claude_needs():
    rows = toolsets.describe(set(toolsets.CORE))
    assert [r["name"] for r in rows] == ["core", *toolsets.AREAS]
    core = rows[0]
    assert (
        core["default"] is True and core["enabled"] is True and core["count"] == len(toolsets.CORE)
    )
    lib = next(r for r in rows if r["name"] == "library")
    assert lib["default"] is False and lib["enabled"] is False
    assert lib["loaded"] == len(set(lib["tools"]) & set(toolsets.CORE))
    assert lib["use_when"] and "add_feed" in lib["tools"]


def test_apply_prunes_to_the_spec_and_load_puts_tools_back():
    assert server.apply_toolsets(None) == ["core"]
    assert _loaded() == set(toolsets.CORE)
    added = server._load(toolsets.tools_for("library"))
    assert set(added) == set(toolsets.AREAS["library"][1]) - set(toolsets.CORE)
    assert _loaded() == set(toolsets.CORE) | set(toolsets.AREAS["library"][1])
    assert server._load(toolsets.tools_for("library")) == []  # idempotent, no duplicates
    assert server.apply_toolsets("all") == list(toolsets.AREAS)
    assert _loaded() == ALL
    assert server.apply_toolsets("nope") == ["core"]
    assert _loaded() == set(toolsets.CORE)


def test_unknown_spec_goes_to_stderr_never_stdout(capsys):
    server.apply_toolsets("core, nope")
    out, err = capsys.readouterr()
    assert out == ""
    assert "unknown toolset 'nope'" in err


def test_list_toolsets_tool_reports_loaded_state():
    server.apply_toolsets("core")
    out = server.list_toolsets()
    assert out["loaded"] == len(toolsets.CORE) and out["total"] == len(ALL)
    names = {r["name"]: r for r in out["toolsets"]}
    assert names["core"]["enabled"] is True and names["studio"]["enabled"] is False


def test_enable_toolset_tool_adds_and_notifies():
    server.apply_toolsets("core")

    class Session:
        sent = 0

        async def send_tool_list_changed(self):
            Session.sent += 1

    class Ctx:
        session = Session()

    out = asyncio.run(server.enable_toolset("Studio", Ctx()))
    assert out["ok"] is True and out["toolset"] == "studio"
    assert set(out["added"]) == set(toolsets.AREAS["studio"][1])
    assert Session.sent == 1
    again = asyncio.run(server.enable_toolset("studio", Ctx()))
    assert again["added"] == [] and Session.sent == 1  # nothing new, no notification
    bad = asyncio.run(server.enable_toolset("nope", Ctx()))
    assert bad["ok"] is False and "nope" in bad["error"]


def test_self_check_reports_loaded_and_total(monkeypatch):
    import httpx

    from mcp_server import client

    monkeypatch.setenv("ATLAS_API_URL", "http://testserver")
    monkeypatch.setenv("ATLAS_API_KEY", "k")
    monkeypatch.setenv(toolsets.ENV, "core,writing")

    def fake_client():
        return httpx.Client(
            base_url="http://testserver/api/v1",
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"count": 1, "results": []})
            ),
        )

    monkeypatch.setattr(client, "_client", fake_client)
    server.apply_toolsets("core,writing")
    out = server.self_check()
    assert out["tools"] == len(set(toolsets.CORE) | set(toolsets.AREAS["writing"][1]))
    assert out["tools_total"] == len(ALL)
    assert out["toolsets"] == ["core", "writing"]


def _run_client(env_toolsets: str | None, enable: str | None):
    """Drive the real server over stdio with the SDK client, like Claude Code would."""
    from mcp import ClientSession, StdioServerParameters, types
    from mcp.client.stdio import stdio_client

    env = {
        "ATLAS_API_URL": "http://127.0.0.1:9",
        "ATLAS_API_KEY": "k",
        "PATH": os.environ.get("PATH", "/usr/bin"),
    }
    if env_toolsets is not None:
        env[toolsets.ENV] = env_toolsets
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server.server"], env=env
    )
    notes: list[str] = []

    async def handler(message):
        if isinstance(message, types.ServerNotification):
            notes.append(type(message.root).__name__)

    async def go():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w, message_handler=handler) as session:
                init = await session.initialize()
                before = [t.name for t in (await session.list_tools()).tools]
                result = None
                after = before
                if enable:
                    result = await session.call_tool("enable_toolset", {"name": enable})
                    after = [t.name for t in (await session.list_tools()).tools]
                return init, before, result, after

    return (*asyncio.run(asyncio.wait_for(go(), 60)), notes)


def test_stdio_client_sees_core_then_enables_library():
    init, before, result, after, notes = _run_client(None, "library")
    assert init.capabilities.tools is not None and init.capabilities.tools.listChanged is True
    assert "Only the core toolset is loaded by default" in (init.instructions or "")
    assert set(before) == set(toolsets.CORE)
    assert result.isError is False
    assert set(after) == set(toolsets.CORE) | set(toolsets.AREAS["library"][1])
    assert len(after) == len(set(after))
    assert "ToolListChangedNotification" in notes


def test_stdio_client_with_all_sees_everything():
    _init, before, _result, _after, _notes = _run_client("all", None)
    assert set(before) == ALL
