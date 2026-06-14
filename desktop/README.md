# Atlas desktop shell (Tauri)

A thin native window over the local Atlas server — Owner idea #30, slice 3. The web
app stays the single source of truth; this just wraps `http://localhost:8000` in a
real app window (and is the host for the built-in terminal, slice 5).

This container is headless, so the binary is built on **your** machine.

## One-time setup
1. Install Rust: https://rustup.rs
2. Install the Tauri CLI: `cargo install tauri-cli --version "^2"`
3. System webview deps:
   - **macOS**: nothing (uses WKWebView)
   - **Windows**: WebView2 (preinstalled on Win 11; else the Evergreen runtime)
   - **Linux**: `webkit2gtk-4.1` + `libappindicator` + `librsvg` (e.g.
     `sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev`)

## Run / build
From the repo root, with Atlas already running (`docker compose up -d` +
`manage.py runserver`):

```
make desktop        # dev run — opens the Atlas window
make desktop-build  # release build -> desktop/target/release/bundle/
```

Point the shell at a different server with `ATLAS_URL=http://host:port/`.

## Download / install (ready-to-install binaries)
You don't have to build it yourself — the **Desktop release** GitHub Actions workflow
(`.github/workflows/desktop-release.yml`) produces ready-to-install binaries for Linux
and Windows and attaches them to a GitHub Release:

- **Tag a version** to publish: `git tag v0.1.0 && git push origin v0.1.0` (or run the
  workflow manually from the Actions tab). It builds on Ubuntu + Windows runners.
- **Grab your installer** from the release's assets:
  - **Linux** — `.AppImage` (run it directly), `.deb` (Debian/Ubuntu), or `.rpm` (Fedora).
  - **Windows** — the `.exe` (NSIS) or `.msi` installer.
- The release is created as a **draft** first so you can review the assets before
  publishing it.

> Note: these installers ship the native shell. Atlas itself (the Django server) still
> runs separately for now — see "NOT YET" below.

## What it is / isn't (v1)
- IS: a native window loading the running Atlas, native window controls + size.
- Local-disk: 'Open from disk…' on the Files page reads a file you explicitly pick
  (text-only, 5MB cap, no directory traversal — only the chosen file).
- NOT YET: bundling the Django server into the binary (you run Atlas separately).
