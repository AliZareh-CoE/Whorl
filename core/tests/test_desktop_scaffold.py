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
    # #242: a running atlas-server.exe holds its files open, so an update over a running app
    # fails with "Error opening file for writing". The NSIS pre-install hook taskkills it first.
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    hook = cfg["bundle"]["windows"]["nsis"]["installerHooks"]
    nsh = (DESKTOP / hook).read_text()
    assert "NSIS_HOOK_PREINSTALL" in nsh and "NSIS_HOOK_PREUNINSTALL" in nsh
    assert "atlas-server.exe" in nsh and "taskkill" in nsh


def test_window_auto_reloads_when_server_becomes_ready():
    # #225: the bundled server's first launch (migrate+collectstatic) can be slow; the window must
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
    # AppImage is not built (#210f: linuxdeploy choked on the bundled native libraries);
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
    # #210f: the release CI freezes the server before the tauri build, and the frozen server is
    # the ONLY bundled resource (#266: SQLite — no database binaries to ship).
    wf = (Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml").read_text()
    assert "pyinstaller desktop/server/atlas_server.spec" in wf
    assert "pyinstaller desktop/server/atlas_mcp.spec" in wf  # the MCP server ships too
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    resources = cfg["bundle"]["resources"]
    assert resources == {
        "server/dist/atlas-server": "atlas-server",
        "server/dist/atlas-mcp": "atlas-mcp",
    }
    # the shell tells the server where the bundled atlas-mcp lives, for the Connect page
    main = (DESKTOP / "src" / "main.rs").read_text()
    server = (DESKTOP / "src" / "server.rs").read_text()
    assert 'bundled_bin(app, "atlas-mcp")' in main and "ATLAS_MCP_BIN" in server


def test_release_workflow_rebuilds_on_frozen_server_sources():
    # #228: the frozen server bundles these Django files, so a change to them must trigger the
    # installer rebuild — they live outside desktop/, so they have to be in the push paths.
    wf = (Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml").read_text()
    assert "core/management/commands/run_desktop.py" in wf
    assert "config/settings/desktop.py" in wf
    assert "mcp_server/**" in wf
    assert "templates/**" in wf and "static/**" in wf


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
    # backlog #304: download progress is emitted per chunk and rendered; release notes are
    # shown before installing; the silent check repeats while the window stays open
    assert '"update-progress"' in updater_rs and "UpdateProgress" in updater_rs
    assert 'listen("update-progress"' in button and "update-progress" in button
    assert "confirmDialog" in button and "RECHECK_MS" in button
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    updater = cfg["plugins"]["updater"]
    assert updater["endpoints"] and "pubkey" in updater
    caps = json.loads((DESKTOP / "capabilities" / "default.json").read_text())
    assert "updater:default" in caps["permissions"]


def test_startup_failure_shows_an_in_app_diagnostic():
    # #263: when the bundled server crashes or never binds, the window must show a diagnostic
    # page with the real logs (not WebView2's blank "can't reach this page"), so a failure
    # self-reports instead of leaving us debugging blind.
    main = (DESKTOP / "src" / "main.rs").read_text()
    server = (DESKTOP / "src" / "server.rs").read_text()
    # the failure path renders the captured server log, the data folder, and the port it used
    assert "diagnostic_html" in main and "splash_html" in main
    assert "atlas-server.log" in main and "Data folder" in main
    assert "127.0.0.1:{port}" in main
    # it detects an early crash (try_wait) instead of only waiting out the timeout
    assert "try_wait" in main
    # server.rs provides the log-tail + escaping helpers the diagnostic uses
    assert "tail_file" in server and "escape_html" in server


def test_shell_steps_aside_when_port_8000_is_taken():
    # A developer's `runserver` (or any other app) on 8000 must not break the desktop launch:
    # without ATLAS_PORT the shell asks choose_port for 8000-or-a-free-port and hands the
    # result to the server, and the diagnostic page names the port it actually used.
    main = (DESKTOP / "src" / "main.rs").read_text()
    server = (DESKTOP / "src" / "server.rs").read_text()
    assert "pub fn choose_port" in server and "TcpListener::bind" in server
    assert "server::choose_port(8000)" in main
    assert 'env("ATLAS_PORT", port.to_string())' in server


def test_release_builds_css_before_freezing():
    # static/css/app.css is a gitignored build artifact, so CI must compile Tailwind before the
    # freeze bundles static/ — otherwise the desktop app serves an unstyled page (#269).
    wf = (Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml").read_text()
    assert "Build Tailwind CSS" in wf
    assert "static/css/app.css" in wf and "tailwindcss" in wf
    # it must come before the freeze step that bundles static/
    assert wf.index("Build Tailwind CSS") < wf.index("Freeze the Atlas server")


def test_in_app_updates_are_live_wired():
    # Owner 2026-09-06: "auto update or update button". The shell checks silently on launch
    # (check_update), installs on click (install_update), restarts (restart_app); the feed is
    # the published desktop-preview release, verified with the real public key; CI signs the
    # updater artifacts whenever the TAURI_SIGNING_PRIVATE_KEY secret exists.
    main = (DESKTOP / "src" / "main.rs").read_text()
    updater_rs = (DESKTOP / "src" / "updater.rs").read_text()
    assert "updater::check_update" in main and "updater::install_update" in main
    assert "pub async fn check_update" in updater_rs and "pub async fn install_update" in updater_rs
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    updater = cfg["plugins"]["updater"]
    assert "REPLACE_ME" not in updater["pubkey"] and len(updater["pubkey"]) > 80
    # the PUBLIC mirror feed first (this repo is private: an unauthenticated app gets 404 from
    # its releases), then this repo's own feed for the day it goes public
    assert updater["endpoints"] == [
        "https://github.com/alizareh-coe/atlas-releases/releases/download/desktop-preview/latest.json",
        "https://github.com/alizareh-coe/project-manager/releases/download/desktop-preview/latest.json",
    ]
    assert cfg["bundle"]["createUpdaterArtifacts"] is False  # CI flips it when the secret exists
    wf = (Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml").read_text()
    assert "secrets.TAURI_SIGNING_PRIVATE_KEY != ''" in wf
    assert ".bundle.createUpdaterArtifacts = true" in wf
    assert "TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}" in wf
    assert "Prune older installers" in wf
    assert "releaseDraft: ${{ startsWith(github.ref, 'refs/tags/') }}" in wf  # preview is published
    button = (DESKTOP.parent / "frontend" / "src" / "app" / "UpdaterButton.tsx").read_text()
    assert 'invoke("check_update")' in button and 'invoke("install_update")' in button
    assert "get it manually" in button  # fallback when the feed is unreachable
    bundle = (DESKTOP.parent / "static" / "js" / "spa.js").read_text(errors="ignore")
    assert "check_update" in bundle and "install_update" in bundle


def test_release_workflow_mirrors_to_the_public_feed():
    """Owner 2026-09-06: "is auto-update working?" — not from a private repo. The workflow
    mirrors installers + .sig + a rewritten latest.json to RELEASES_REPO, and the app says so
    when the feed 404s instead of failing silently."""
    workflow = (
        Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml"
    ).read_text()
    assert "mirror:" in workflow and "needs: build" in workflow
    for needle in (
        "RELEASES_REPO",
        "RELEASES_TOKEN",
        "latest.json",
        'sed -i "s#github.com/$SRC_REPO/',
    ):
        assert needle in workflow
    button = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "UpdaterButton.tsx"
    ).read_text()
    assert "private GitHub repository" in button and "Updates unavailable" in button
    readme = (Path(settings.BASE_DIR) / "README.md").read_text()
    assert "## Auto-update" in readme and "RELEASES_REPO" in readme


def test_external_links_open_in_the_os_browser():
    """Owner 2026-09-06: "the button to get it manually failed" — the shell blocks off-origin
    navigation, so outbound links go through open_external (http/https/mailto only)."""
    main = (DESKTOP / "src" / "main.rs").read_text()
    external = (DESKTOP / "src" / "external.rs").read_text()
    assert "external::open_external" in main
    assert 'starts_with("https://")' in external and "javascript:" in external
    layout = (Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "Layout.tsx").read_text()
    assert "installExternalLinkHandler()" in layout
    button = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "UpdaterButton.tsx"
    ).read_text()
    assert "openExternal(RELEASES)" in button


def test_capability_covers_the_local_server_origin():
    """Owner 2026-09-06: "command … not allowed by ACL". The webview loads
    http://127.0.0.1:<port>, a remote origin to Tauri; the capability must name it or every
    command is refused."""
    cap = json.loads((DESKTOP / "capabilities" / "default.json").read_text())
    urls = cap["remote"]["urls"]
    assert any(u.startswith("http://127.0.0.1") for u in urls)
    assert any(u.startswith("http://localhost") for u in urls)
    assert "main" in cap["windows"] and "core:default" in cap["permissions"]


def test_release_workflow_smoke_tests_the_frozen_server():
    """Owner reports 2026-09-06: every failure lived only in the installed build. CI boots the
    frozen server on the target OS and checks login, diagnostics (bundled engine) and the SPA."""
    workflow = (
        Path(settings.BASE_DIR) / ".github" / "workflows" / "desktop-release.yml"
    ).read_text()
    assert "Smoke-test the frozen server" in workflow
    assert "--setup-only" in workflow and "/api/v1/diagnostics/" in workflow
    assert (
        "tectonic"
        in workflow.split("Smoke-test the frozen server", 1)[1].split("Build and release", 1)[0]
    )
    assert workflow.index("Smoke-test the frozen server") < workflow.index(
        "Build and release the desktop app"
    )


def test_app_icon_is_not_the_placeholder():
    """Owner report 2026-09-07: the installed app had a flat square for an icon. The icons
    are rendered by scripts/make_icon.py and regenerated with `tauri icon`."""
    icons = DESKTOP / "icons"
    assert (icons / "source.png").stat().st_size > 50_000  # a real drawing, not a flat fill
    assert (icons / "icon.png").stat().st_size > 20_000
    ico = (icons / "icon.ico").read_bytes()
    assert ico[:4] == b"\x00\x00\x01\x00" and ico[4] >= 4  # several sizes inside
    assert (DESKTOP.parent / "scripts" / "make_icon.py").exists()
    cfg = json.loads((DESKTOP / "tauri.conf.json").read_text())
    assert "icons/icon.ico" in cfg["bundle"]["icon"]


def test_release_notes_come_from_commits():
    """#370/#375: the updater's release notes are the recent feat/fix subjects, not a slogan."""
    workflow = (DESKTOP.parent / ".github" / "workflows" / "desktop-release.yml").read_text()
    assert "Write release notes" in workflow
    assert "releaseBody: ${{ steps.notes.outputs.body }}" in workflow
    assert "fetch-depth: 40" in workflow  # a shallow clone has no history to list
