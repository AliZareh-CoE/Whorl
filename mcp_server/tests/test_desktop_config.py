"""atlas-mcp's zero-config discovery of the desktop install (API key + server URL)."""

import json
from pathlib import Path

import pytest

from mcp_server import desktop_config as dc


def _install(tmp_path, key="k-123", url="http://127.0.0.1:8123"):
    (tmp_path / "api_key").write_text(key + "\n")
    (tmp_path / "server.json").write_text(json.dumps({"url": url, "port": 8123}))


def test_explicit_data_dir_wins():
    env = {"ATLAS_DATA_DIR": "/somewhere"}
    assert dc.default_data_dirs(environ=env) == [Path("/somewhere")]


def test_default_dirs_follow_the_tauri_app_data_folder_per_os():
    linux = dc.default_data_dirs("linux", {"HOME": "/home/u"})
    assert linux[0] == Path("/home/u/.local/share/com.atlas.research")
    assert linux[-1] == Path("/home/u/.atlas")
    xdg = dc.default_data_dirs("linux", {"HOME": "/home/u", "XDG_DATA_HOME": "/xdg"})
    assert xdg[0] == Path("/xdg/com.atlas.research")
    mac = dc.default_data_dirs("darwin", {"HOME": "/Users/u"})
    assert mac[0] == Path("/Users/u/Library/Application Support/com.atlas.research")
    win = dc.default_data_dirs("win32", {"APPDATA": r"C:\Users\u\AppData\Roaming"})
    assert win[0] == Path(r"C:\Users\u\AppData\Roaming") / "com.atlas.research"


def test_discover_reads_key_and_live_url(tmp_path):
    _install(tmp_path)
    info = dc.discover(environ={"ATLAS_DATA_DIR": str(tmp_path)})
    assert info == {
        "data_dir": str(tmp_path),
        "api_key": "k-123",
        "url": "http://127.0.0.1:8123",
    }


def test_discover_defaults_url_without_server_json(tmp_path):
    (tmp_path / "api_key").write_text("k")
    info = dc.discover(environ={"ATLAS_DATA_DIR": str(tmp_path)})
    assert info["url"] == dc.DEFAULT_URL


def test_discover_explains_when_nothing_is_installed(tmp_path):
    with pytest.raises(LookupError) as exc:
        dc.discover(environ={"ATLAS_DATA_DIR": str(tmp_path / "missing")})
    msg = str(exc.value)
    assert "Launch the Atlas desktop app once" in msg
    assert str(tmp_path / "missing") in msg


def test_apply_env_fills_only_the_missing_values(tmp_path):
    _install(tmp_path)
    env = {"ATLAS_DATA_DIR": str(tmp_path), "ATLAS_API_KEY": "explicit"}
    dc.apply_env(env)
    assert env["ATLAS_API_KEY"] == "explicit"  # explicit wins
    assert env["ATLAS_API_URL"] == "http://127.0.0.1:8123"  # discovered


def test_apply_env_is_a_noop_when_fully_configured():
    env = {"ATLAS_API_KEY": "k", "ATLAS_API_URL": "http://x"}
    assert dc.apply_env(env) is None
    assert env == {"ATLAS_API_KEY": "k", "ATLAS_API_URL": "http://x"}


def test_apply_env_tolerates_no_install_when_key_is_explicit(tmp_path):
    env = {"ATLAS_DATA_DIR": str(tmp_path / "nope"), "ATLAS_API_KEY": "k"}
    assert dc.apply_env(env) is None


def test_apply_env_raises_when_nothing_configured_and_nothing_installed(tmp_path):
    with pytest.raises(LookupError):
        dc.apply_env({"ATLAS_DATA_DIR": str(tmp_path / "nope")})
