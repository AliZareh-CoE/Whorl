# Atlas desktop app (Tauri)

A native, self-contained build of Atlas: one installer, no Python, no Postgres, no Docker on
the user's machine. The Tauri shell starts a bundled `atlas-server` (the Django app frozen with
PyInstaller, running on a per-user **SQLite** file, served by waitress), waits for it to answer,
and opens it in a native window. The web app stays the single source of truth — the desktop
build adds a **built-in terminal** and **Open from disk** on top of it.
**Open from disk** picks one file (async command — a blocking picker inside a sync command never
appears), previews it when it is text, and can add it to the project into any folder. Files already in
the project can be opened with the system's default app or shown in the file manager from
the explorer's right-click menu.

## Install it (no build needed)

The **Desktop release** GitHub Actions workflow (`.github/workflows/desktop-release.yml`)
builds ready-to-install binaries for Linux and Windows and attaches them to a GitHub Release.
It runs automatically on every push that touches the desktop app, the frozen server's sources,
templates, or static assets, rolling them into the draft release **"Atlas desktop preview"**
(tag `desktop-preview`); a version tag (`git tag v0.1.0 && git push origin v0.1.0`) or a manual
dispatch from the Actions tab publishes under that tag instead.

Pick the file for your OS from the release's assets:

- **Linux** — `.deb` (Debian/Ubuntu) or `.rpm` (Fedora).
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
   of `atlas-server.log`, so a failure explains itself. If the server is up but the app never
   draws (a blank window), the page's own boot watchdog shows the thrown errors after a few
   seconds and writes them to `atlas-server.log` (README › If the window is blank). F12 or
   Ctrl+Shift+I opens the web inspector in the release build (Tauri's `devtools` feature).
5. Quitting the app stops the server. A second launch focuses the existing window instead of
   starting a second server on the same database.

The data folder holds everything: `atlas.sqlite3`, `media/`, `staticfiles/`, `secret_key`,
`api_key`, `server.json` (the URL this launch is serving on), `watch.json` (the watched PDF folder), `atlas-server.log`. Back it up
to back up Atlas.

## Claude Code integration (`atlas-mcp`)

The installer also ships the Atlas MCP server, frozen as `atlas-mcp` next to `atlas-server`
(both are Tauri bundle resources). On first launch the app mints an API key into the data
folder; `atlas-mcp` reads that key and the live URL from `server.json`, so registering Atlas in
Claude Code is one line with nothing to copy:

```
claude mcp add atlas -- "<install dir>/atlas-mcp/atlas-mcp"      # .exe on Windows
claude mcp list                                                   # → atlas … ✓ Connected
```

The app's **Connect Claude Code** page (sidebar, `/connect/claude/`) prints that line with the
real installed path filled in, plus the API key and a JSON snippet for other MCP clients. The
Tauri shell passes the bundled binary's path to the server as `ATLAS_MCP_BIN`, which is how the
page knows it. Explicit `ATLAS_API_URL` / `ATLAS_API_KEY` env vars on the MCP server always win
over discovery, and `ATLAS_DATA_DIR` points it at a non-default data folder.

Both binaries are frozen with PyInstaller (`atlas_server.spec`, `atlas_mcp.spec`) — see
`make desktop-server`.

## No build at all: the server from source

Everything the shell shows is served by `manage.py run_desktop`. From a checkout, `uv sync`
then `make standalone` (PowerShell: `$env:DJANGO_SETTINGS_MODULE = "config.settings.desktop";
uv run python manage.py run_desktop`) runs it against the same SQLite data folder the app uses
when `ATLAS_DATA_DIR` points there, and any browser at http://127.0.0.1:8000 is the app.

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
# 2. freeze the Django server + the MCP server
make desktop-server
# 3. bundle: tauri.conf.json ships desktop/server/dist/{atlas-server,atlas-mcp} as resources
make desktop-build
```

To try the frozen server on its own: `ATLAS_PORT=8077 desktop/server/dist/atlas-server/atlas-server`
then open http://127.0.0.1:8077 (see `desktop/server/README.md`). To run the shell against a
frozen server without bundling, set `ATLAS_SERVER_BIN=/path/to/atlas-server` and `make desktop`.

`cargo test` in `desktop/` runs the shell's unit tests (port selection, log tailing).

## In-app updates

The app updates itself from the **desktop-preview** release (published as a prerelease so it
never shadows a tagged `v*` release). On every launch the sidebar control silently asks the
release feed (`latest.json`) whether a newer build exists; if so it becomes **Update to
0.1.NN** — one click downloads and installs, then **Restart to finish update**. "Check for
updates" stays available for a manual check, and if the feed is unreachable the control links
to the release page as a fallback.

Updates are **signed**: every `.sig` and `latest.json` is produced with a private key that
lives only in the repo secret `TAURI_SIGNING_PRIVATE_KEY`, and the app verifies downloads
against the public key in `desktop/tauri.conf.json` (`plugins.updater.pubkey`). The release
workflow turns `createUpdaterArtifacts` on automatically whenever that secret exists, so builds
stay green before the secret is added — they just don't publish an update feed until then.

**One-time setup (repo owner):** GitHub → Settings → Secrets and variables → Actions → New
repository secret → name `TAURI_SIGNING_PRIVATE_KEY`, value = the private key that pairs with
the committed public key (generated with `npx @tauri-apps/cli signer generate`; the owner holds
it). If the key has a password, add `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` too. The next push
that touches the desktop build publishes `latest.json`, and installed apps start updating.

**Commands and the ACL.** The window loads `http://127.0.0.1:<port>`, which Tauri counts as a
*remote* origin, so `capabilities/default.json` must list it under `remote.urls` — otherwise
every command (terminal, updater, file picker, external links) is refused with "not allowed
by ACL". A test pins this.

**Is it working? Ask Diagnostics (#534).** Tick *Probe the update feed* on `/diagnostics`
(or run `manage.py doctor`): the **Update check** row fetches `latest.json` the way the app
does and gives one verdict — a newer build is available and signed for this app, up to date,
signed with a different key (install that build once from the releases page), unsigned,
unreachable, or offline. The repository is public, so the app reads the feed directly; the
workflow's optional `mirror` job (secrets `RELEASES_REPO` + `RELEASES_TOKEN`) exists only for
the day it is made private again. Older builds carried the old repository address,
which GitHub redirects, so they still find updates.

Losing the private key means generating a new pair, committing the new public key, and
shipping one more manual install; keep it somewhere safe. `manage.py doctor` reports the
updater's configuration state.

The preview release keeps only the newest build: the workflow prunes installers from earlier
versions (assets sharing the current version stamp — the other platform's — are kept).

## Not yet
- **Code signing** (Windows Authenticode, macOS notarization) — needs a certificate / Apple
  developer account; without it Windows shows the unknown-publisher warning.
- **macOS installers** — Tauri and PyInstaller both support it; the release matrix currently
  builds Linux + Windows only. Add a `macos-latest` entry to the matrix to get a `.dmg`.
- **AppImage** — tried twice (#210f, #405); linuxdeploy fails to relink the bundled native
  libraries (Postgres's, then PyInstaller's). `.deb`/`.rpm` cover Linux.
