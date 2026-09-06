# Atlas desktop app (Tauri)

A native, self-contained build of Atlas: one installer, no Python, no Postgres, no Docker on
the user's machine. The Tauri shell starts a bundled `atlas-server` (the Django app frozen with
PyInstaller, running on a per-user **SQLite** file, served by waitress), waits for it to answer,
and opens it in a native window. The web app stays the single source of truth — the desktop
build adds a **built-in terminal** and **Open from disk** on top of it.

## Install it (no build needed)

The **Desktop release** GitHub Actions workflow (`.github/workflows/desktop-release.yml`)
builds ready-to-install binaries for Linux and Windows and attaches them to a GitHub Release.
It runs automatically on every push that touches the desktop app, the frozen server's sources,
templates, or static assets, rolling them into the draft release **"Atlas desktop preview"**
(tag `desktop-preview`); a version tag (`git tag v0.1.0 && git push origin v0.1.0`) or a manual
dispatch from the Actions tab publishes under that tag instead.

Pick the file for your OS from the release's assets:

- **Linux** — `.deb` (Debian/Ubuntu) or `.rpm` (Fedora). AppImage is not built.
- **Windows** — the `-setup.exe` (NSIS) or the `.msi`. Windows Smart App Control / SmartScreen
  warns about unsigned installers; the build is unsigned until a code-signing certificate is
  added (see "Not yet" below).

Every build stamps a unique version (`0.1.<run number>`), so installing over an older build is
a real upgrade. On Windows the installer first stops a running `atlas-server.exe` so the update
can replace its files (`installer-hooks.nsh`).

## What happens on launch

1. The shell picks a port: `ATLAS_PORT` if set, else **8000**, else the next free port when
   8000 is already taken (a dev `runserver` and the desktop app coexist).
2. It spawns the bundled `atlas-server` with `ATLAS_DATA_DIR` set to the OS app-data folder
   (`~/.local/share/com.atlas.research` on Linux, `%APPDATA%\com.atlas.research` on Windows)
   and opens a **"Starting Atlas…"** splash.
3. The server runs `manage.py run_desktop` under `config/settings/desktop.py`: `migrate` on
   `atlas.sqlite3`, `collectstatic` (once per build version), and creates the single login
   **atlas / atlas** (override with `ATLAS_ADMIN_USER` / `ATLAS_ADMIN_PASSWORD`). Background
   jobs run in-process; static files come from WhiteNoise.
4. The window navigates to the app the moment the port answers. If the server exits or never
   binds, the window shows an **in-app diagnostic page** with the data folder path and the tail
   of `atlas-server.log`, so a failure explains itself.
5. Quitting the app stops the server. A second launch focuses the existing window instead of
   starting a second server on the same database.

The data folder holds everything: `atlas.sqlite3`, `media/`, `staticfiles/`, `secret_key`,
`atlas-server.log`. Back it up to back up Atlas.

## Build it yourself

### One-time setup
1. Rust: https://rustup.rs, then `cargo install tauri-cli --version "^2"`.
2. System webview deps:
   - **macOS**: nothing (WKWebView)
   - **Windows**: WebView2 (preinstalled on Win 11; else the Evergreen runtime)
   - **Linux**: `sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev`
3. Python side: `uv sync --group build` (adds PyInstaller).

### Shell only, against a server you run (dev loop)
With Atlas running (`docker compose up -d` + `manage.py runserver`):

```
make desktop          # dev run — opens the Atlas window at http://localhost:8000
make desktop-build    # release build -> desktop/target/release/bundle/
```

Point the shell at another server with `ATLAS_URL=http://host:port/`. Without a bundled
`atlas-server` next to the binary and without `ATLAS_URL`, the shell just opens
`http://localhost:8000/`.

### Fully self-contained (what CI does)
```
# 1. the stylesheet is a gitignored build artifact — build it first
make css
# 2. freeze the Django server
uv run pyinstaller desktop/server/atlas_server.spec --noconfirm \
    --distpath desktop/server/dist --workpath /tmp/pyi
# 3. bundle: tauri.conf.json ships desktop/server/dist/atlas-server as a resource
make desktop-build
```

To try the frozen server on its own: `ATLAS_PORT=8077 desktop/server/dist/atlas-server/atlas-server`
then open http://127.0.0.1:8077 (see `desktop/server/README.md`). To run the shell against a
frozen server without bundling, set `ATLAS_SERVER_BIN=/path/to/atlas-server` and `make desktop`.

`cargo test` in `desktop/` runs the shell's unit tests (port selection, log tailing).

## Auto-update ("Check for updates" button)
The app has Tauri's built-in updater (OSS — no paid service). The SPA sidebar shows a
desktop-only **Check for updates** control that asks the GitHub Releases feed for a newer
signed build, installs it, and offers a restart. It is wired but **dormant until a one-time
signing setup** (updater bundles must be signed):

1. Generate the keypair once: `cargo tauri signer generate -w ~/.atlas-updater.key`
   (keep the private key secret — never commit it).
2. Put the printed **public** key into `desktop/tauri.conf.json` → `plugins.updater.pubkey`
   (replacing the `REPLACE_ME_…` placeholder).
3. Flip `bundle.createUpdaterArtifacts` to `true` in the same file.
4. Add the **private** key as a repo secret `TAURI_SIGNING_PRIVATE_KEY` (and
   `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` if you set one) — the release workflow already passes
   them through to the signed build.

Until then the installers still build fine; only the in-app update check stays inert (it
reports an error gracefully if pressed). `manage.py doctor` warns while the placeholder is in.

## Not yet
- **Code signing** (Windows Authenticode, macOS notarization) — needs a certificate / Apple
  developer account; without it Windows shows the unknown-publisher warning.
- **macOS installers** — Tauri and PyInstaller both support it; the release matrix currently
  builds Linux + Windows only. Add a `macos-latest` entry to the matrix to get a `.dmg`.
- **AppImage** — dropped because linuxdeploy could not relink the bundled native libraries;
  `.deb`/`.rpm` cover Linux.
- **Live auto-update** — the signing setup above.
