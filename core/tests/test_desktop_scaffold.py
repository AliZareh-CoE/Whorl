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
    for fmt in ("deb", "appimage", "rpm", "nsis", "msi"):
        assert fmt in targets, f"bundle target {fmt} missing"


def test_desktop_release_workflow_exists():
    wf = Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml"
    assert wf.exists(), "missing the desktop-release workflow"
    text = wf.read_text()
    assert "tauri-apps/tauri-action" in text  # builds + uploads the installers
    assert "windows-latest" in text and "ubuntu-22.04" in text  # both OSes
