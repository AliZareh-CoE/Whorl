# Bundled Atlas server (PyInstaller)

This freezes the Atlas Django app into a **standalone `atlas-server` executable** so the
desktop app can run it with no Python / Postgres / Redis / Docker on the user's machine
(Owner epic #210). The Tauri shell spawns this binary on launch (#210e), and the release
CI builds it per-OS before bundling the installers (#210f).

It runs `manage.py run_desktop` under `config/settings/desktop.py`: SQLite in
`ATLAS_DATA_DIR` (default `~/.atlas`), in-process background jobs, WhiteNoise static, served
by waitress on `ATLAS_PORT` (default 8000).

## Build it

```
uv sync --group build           # installs PyInstaller
pyinstaller desktop/server/atlas_server.spec --noconfirm \
    --distpath desktop/server/dist --workpath desktop/server/build
```

Output: `desktop/server/dist/atlas-server/atlas-server` (+ an `_internal/` folder). Run it:

```
ATLAS_PORT=8077 desktop/server/dist/atlas-server/atlas-server
# → serves Atlas at http://127.0.0.1:8077 (login: atlas / atlas)
```

Verified on Linux: the frozen binary serves the login page and static assets against a
fresh SQLite database with nothing else installed. Windows/macOS builds happen on their
own CI runners (PyInstaller can't cross-compile).
