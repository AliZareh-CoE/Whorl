"""Tool detection for the Connect page (2026-09-06)."""

import pytest

from core import tooling


def test_detect_tools_reports_found_and_missing(monkeypatch, tmp_path):
    from writing import compile as compile_mod

    monkeypatch.setattr(compile_mod, "tectonic_path", lambda: tmp_path / "tectonic")
    rows = tooling.detect_tools(
        which=lambda cmd: "/usr/bin/claude" if cmd == "claude" else None,
        version=lambda path: "1.2.3 (Claude Code)" if path else "",
    )
    by = {r["key"]: r for r in rows}
    assert by["claude"]["found"] and by["claude"]["version"].startswith("1.2.3")
    assert not by["node"]["found"] and by["node"]["install"].startswith("https://")
    assert by["tectonic"]["found"] and by["tectonic"]["path"].endswith("tectonic")


def test_version_never_raises(monkeypatch):
    assert tooling._version("/definitely/not/a/binary") == ""


@pytest.mark.django_db
def test_connect_api_carries_tools(client_logged_in):
    data = client_logged_in.get("/api/v1/connect/").json()
    assert {t["key"] for t in data["tools"]} == {"claude", "node", "git", "tectonic"}
