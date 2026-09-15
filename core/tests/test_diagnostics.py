"""The diagnostics report (2026-09-06)."""

from pathlib import Path

import pytest
from django.conf import settings

from core import diagnostics

pytestmark = pytest.mark.django_db


def test_report_and_text(client_logged_in, monkeypatch, tmp_path, settings):
    from writing import compile as compile_mod
    from writing.models import Manuscript

    monkeypatch.setattr(compile_mod, "tectonic_path", lambda: tmp_path / "tectonic")
    settings.DATA_DIR = tmp_path
    (tmp_path / "atlas-server.log").write_text("line one\nAtlas is running\n")
    from projects.tests.factories import ProjectFactory

    Manuscript.objects.create(
        project=ProjectFactory(),
        title="Broken",
        compile_status="failed",
        compile_log="! Undefined control sequence.",
    )
    data = client_logged_in.get("/api/v1/diagnostics/").json()
    assert data["engine"].endswith("tectonic") and data["jobs"].startswith("in-process")
    assert data["last_failed_compile"]["title"] == "Broken"
    assert "Atlas is running" in data["server_log"]
    assert [r["status"] for r in data["update_feed"]] == [
        None
    ] * 3  # three endpoints; no network by default
    text = data["text"]
    assert (
        "LaTeX engine:" in text
        and "Undefined control sequence" in text
        and "server log (tail)" in text
    )
    assert diagnostics.as_text(diagnostics.collect())  # standalone call works too


PUBKEY_ID = "71f2b5f3b358e8dc"  # the key id inside desktop/tauri.conf.json's updater pubkey


def _sig(key_id_hex: str) -> str:
    """A minisign-shaped signature (base64 of the two-line file) carrying `key_id_hex`."""
    import base64

    raw = b"ED" + bytes.fromhex(key_id_hex) + b"\x00" * 64
    text = "untrusted comment: x\n" + base64.b64encode(raw).decode() + "\n"
    return base64.b64encode(text.encode()).decode()


def _feed(version: str, key_id: str | None = PUBKEY_ID) -> bytes:
    import json

    platform = {"url": "https://x/y.exe"}
    if key_id:
        platform["signature"] = _sig(key_id)
    return json.dumps(
        {
            "version": version,
            "platforms": {"windows-x86_64-nsis": platform, "linux-x86_64": platform},
        }
    ).encode()


class _Resp:
    def __init__(self, status, body=b""):
        self.status_code, self._body = status, body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_bytes(self):
        yield self._body


def _network(monkeypatch, answers):
    """answers: url-suffix → _Resp | Exception, in the app's endpoint order."""
    import httpx

    def stream(method, url, **kw):
        for suffix, answer in answers.items():
            if suffix in url:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        return _Resp(404)

    monkeypatch.setattr(httpx, "stream", stream)


@pytest.mark.parametrize(
    ("answers", "version", "state", "needle"),
    [
        ({"Whorl": _Resp(200, _feed("0.1.999"))}, "0.1.242", "available", "0.1.999 is available"),
        ({"Whorl": _Resp(200, _feed("0.1.242"))}, "0.1.242", "current", "up to date"),
        ({"Whorl": _Resp(200, _feed("0.1.999"))}, "dev", "unknown_version", "cannot compare"),
        (
            {"Whorl": _Resp(200, _feed("0.1.999", "0000000000000000"))},
            "0.1.1",
            "wrong_key",
            "different key",
        ),
        ({"Whorl": _Resp(200, _feed("0.1.999", None))}, "0.1.1", "unsigned", "without signatures"),
        # the first endpoint 404s, the second answers — the app falls through the same way
        ({"project-manager": _Resp(200, _feed("0.1.300"))}, "0.1.242", "available", "0.1.300"),
        ({}, "0.1.242", "unreachable", "no endpoint answered"),
        ({"Whorl": _Resp(200, b"<html>")}, "0.1.242", "unreachable", "not a feed"),
        (
            {
                "Whorl": __import__("httpx").ConnectError("x"),
                "project-manager": __import__("httpx").ConnectError("x"),
                "atlas-releases": __import__("httpx").ConnectError("x"),
            },
            "0.1.242",
            "offline",
            "could not reach",
        ),
    ],
)
def test_update_feed_verdicts(monkeypatch, answers, version, state, needle):
    """#534 (owner: "the update link doesn't work"): Diagnostics fetches the feed the way the
    app does and says whether this install can update — newer build, up to date, a build
    without a comparable version, a feed signed with another key, unsigned, unreachable,
    not a feed, offline."""
    _network(monkeypatch, answers)
    rows = diagnostics.update_feed_status(check_network=True)
    assert [r["url"].split("/")[4] for r in rows] == ["Whorl", "project-manager", "atlas-releases"]
    verdict = diagnostics.update_verdict(rows, version)
    assert verdict["state"] == state and needle in verdict["text"], verdict
    text = diagnostics.as_text(
        {
            **diagnostics.collect(),
            "update_feed": rows,
            "update_verdict": verdict,
            "version": version,
        }
    )
    assert f"update check: {verdict['text']}" in text


def test_update_feed_rows_carry_what_the_feed_says(monkeypatch):
    _network(monkeypatch, {"Whorl": _Resp(200, _feed("0.1.999"))})
    rows = diagnostics.update_feed_status(check_network=True)
    assert rows[0]["status"] == 200 and rows[0]["version"] == "0.1.999"
    assert rows[0]["platforms"] == ["linux-x86_64", "windows-x86_64-nsis"]
    assert rows[0]["key_match"] is True and rows[1]["status"] == 404
    assert diagnostics._key_id("not base64!") == ""
    assert diagnostics._version_tuple("v0.1.242") == (0, 1, 242)
    assert diagnostics._version_tuple("dev") is None
    # a runaway body is cut off, not read into memory
    _network(monkeypatch, {"Whorl": _Resp(200, b"x" * (diagnostics.FEED_MAX_BYTES + 1))})
    assert diagnostics.update_feed_status(check_network=True)[0]["status"] == "too large"


def test_diagnostics_api_carries_the_verdict(client_logged_in):
    data = client_logged_in.get("/api/v1/diagnostics/").json()
    assert data["update_verdict"]["state"] == "unchecked"
    assert data["update_feed"][0]["version"] is None
    tsx = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Diagnostics.tsx"
    page = tsx.read_text()
    assert 'data-testid="update-verdict"' in page and "signed with a different key" in page


def test_doctor_uses_the_verdict(monkeypatch, capsys):
    from django.core.management import call_command

    _network(monkeypatch, {"Whorl": _Resp(200, _feed("0.1.999"))})
    monkeypatch.setenv("ATLAS_VERSION", "0.1.242")
    call_command("doctor")
    out = capsys.readouterr().out
    assert "update feed — 0.1.999 is available and signed for this app (you run 0.1.242)" in out


def test_updater_fallback_matches_the_tauri_config_and_ships_in_the_frozen_server(monkeypatch):
    """#534: an installed app must get the same verdict as a source checkout — the frozen
    server bundles desktop/tauri.conf.json, and the pinned fallback never drifts from it."""
    import json

    conf = json.loads((Path(settings.BASE_DIR) / "desktop" / "tauri.conf.json").read_text())
    updater = conf["plugins"]["updater"]
    assert diagnostics.UPDATER_FALLBACK == {
        "endpoints": updater["endpoints"],
        "pubkey": updater["pubkey"],
    }
    assert diagnostics.updater_config() == diagnostics.UPDATER_FALLBACK
    monkeypatch.setattr(settings, "BASE_DIR", Path("/nowhere"))
    assert diagnostics.updater_config() == diagnostics.UPDATER_FALLBACK
    rows = diagnostics.update_feed_status()
    assert [r["url"] for r in rows] == updater["endpoints"]
    spec_text = Path("desktop/server/atlas_server.spec").read_text()
    assert '(os.path.join(ROOT, "desktop", "tauri.conf.json"), "desktop")' in spec_text
