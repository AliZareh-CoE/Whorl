"""The Tauri desktop shell scaffold stays well-formed (Owner #30, slice 3).

The GUI binary is built on the owner's machine (headless CI can't run a webview), so
this guards the scaffold's structure + config instead — cheap, and it fails the build
if the desktop project loses a required piece.
"""

import json
from pathlib import Path

from django.conf import settings

DESKTOP = Path(settings.BASE_DIR) / "desktop"


def test_required_files_exist():
    for rel in [
        "Cargo.toml",
        "Cargo.lock",
        "build.rs",
        "tauri.conf.json",
        "src/main.rs",
        "capabilities/default.json",
        "icons/icon.png",
        "README.md",
    ]:
        assert (DESKTOP / rel).exists(), f"missing desktop/{rel}"


def test_tauri_config_is_valid_and_complete():
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    assert cfg["identifier"] == "com.atlas.research"
    assert cfg["productName"] == "Atlas"
    assert "build" in cfg and "app" in cfg and "bundle" in cfg


def test_main_wraps_the_local_atlas_server():
    main = (DESKTOP / "src" / "main.rs").read_text()
    assert "WebviewWindowBuilder" in main
    assert "localhost:8000" in main  # default server the shell wraps
    assert "ATLAS_URL" in main  # env override


def test_webview_navigation_is_origin_locked():
    # security hardening (#160): the shell restricts navigation to the Atlas host
    main = (DESKTOP / "src" / "main.rs").read_text()
    assert "on_navigation" in main and "allowed_host" in main


def test_installer_kills_running_server_before_install():
    # #242: a running atlas-server.exe/postgres.exe locks pg\bin\postgres.exe, so an update
    # over a running app fails with "Error opening file for writing". The NSIS pre-install hook
    # taskkills them first.
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    hook = cfg["bundle"]["windows"]["nsis"]["installerHooks"]
    nsh = (DESKTOP / hook).read_text()
    assert "NSIS_HOOK_PREINSTALL" in nsh
    assert "atlas-server.exe" in nsh and "postgres.exe" in nsh and "taskkill" in nsh


def test_window_auto_reloads_when_server_becomes_ready():
    # #225: the bundled server's first launch (initdb+migrate) can be slow; the window must
    # not get stuck on a "can't reach this page". It opens immediately and a background thread
    # reloads it (navigate) once wait_for_port answers — no manual refresh.
    main = (DESKTOP / "src" / "main.rs").read_text()
    assert "thread::spawn" in main
    assert "wait_for_port" in main and ".navigate(" in main


def test_cargo_depends_on_tauri_2():
    cargo = (DESKTOP / "Cargo.toml").read_text()
    assert "tauri" in cargo and "tauri-build" in cargo


def test_icon_is_rgba_png():
    # Tauri requires an RGBA icon; PNG color-type byte (IHDR offset 25) must be 6.
    data = (DESKTOP / "icons" / "icon.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[25] == 6, "icon must be RGBA (color type 6)"


def test_bundle_targets_cover_linux_and_windows_installers():
    # Owner-requested D1: ready-to-install binaries for Linux + Windows.
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    targets = cfg["bundle"]["targets"]
    assert isinstance(targets, list)
    # AppImage is dropped (#210f): linuxdeploy can't bundle our native Postgres .so's;
    # .deb/.rpm cover Linux, .nsis/.msi cover Windows.
    for fmt in ("deb", "rpm", "nsis", "msi"):
        assert fmt in targets, f"bundle target {fmt} missing"


def test_desktop_release_workflow_exists():
    wf = Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml"
    assert wf.exists(), "missing the desktop-release workflow"
    text = wf.read_text()
    assert "tauri-apps/tauri-action" in text  # builds + uploads the installers
    assert "windows-latest" in text and "ubuntu-22.04" in text  # both OSes


def test_release_workflow_assembles_the_bundled_server():
    # #210f/#210i: the release CI freezes the server and bundles Postgres before tauri build.
    wf = (Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml").read_text()
    assert "pyinstaller desktop/server/atlas_server.spec" in wf
    assert "embedded-postgres-binaries" in wf  # the portable Postgres source
    assert "desktop/resources/pg" in wf
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    resources = cfg["bundle"]["resources"]
    assert "server/dist/atlas-server" in resources  # the frozen server ships as a resource
    assert "resources/pg" in resources  # the Postgres binaries ship as a resource


def test_release_workflow_rebuilds_on_frozen_server_sources():
    # #228: the frozen server bundles these Django files, so a change to them must trigger the
    # installer rebuild — they live outside desktop/, so they have to be in the push paths.
    wf = (Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml").read_text()
    assert "core/desktop_runtime.py" in wf
    assert "config/settings/desktop.py" in wf


def test_release_workflow_stamps_a_unique_version():
    # #230: every build bumps the version (0.1.<run_number>) so the .msi actually upgrades and
    # the installer filename is unique — a fixed version left the owner running old code.
    wf = (Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml").read_text()
    assert "github.run_number" in wf
    assert ".version = $v" in wf  # the jq edit to tauri.conf.json
    assert "desktop/Cargo.toml" in wf  # #241: Cargo.toml stamped too, so the server reads it
    main = (DESKTOP / "src" / "server.rs").read_text()
    assert "ATLAS_VERSION" in main and "CARGO_PKG_VERSION" in main


def test_updater_is_wired():
    # Owner-requested D2: in-app "Check for updates" button (auto-update).
    cargo = (DESKTOP / "Cargo.toml").read_text()
    assert "tauri-plugin-updater" in cargo
    main = (DESKTOP / "src" / "main.rs").read_text()
    assert "tauri_plugin_updater" in main  # plugin registered
    assert "check_for_updates" in main  # command exposed to the UI
    # an installed update only takes effect on a real process restart, not a webview reload,
    # so the restart command must be exposed and the button must call it (not location.reload).
    assert "restart_app" in main
    updater_rs = (DESKTOP / "src" / "updater.rs").read_text()
    assert "restart_app" in updater_rs and "app.restart()" in updater_rs
    button = (DESKTOP.parent / "frontend" / "src" / "app" / "UpdaterButton.tsx").read_text()
    assert "restart_app" in button
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    updater = cfg["plugins"]["updater"]
    assert updater["endpoints"] and "pubkey" in updater
    caps = json.loads((DESKTOP / "capabilities" / "default.json").read_text())
    assert "updater:default" in caps["permissions"]
