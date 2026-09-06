# PyInstaller spec for the bundled Atlas MCP server (`atlas-mcp`).
#
# Freezes `atlas_mcp.py` — the stdio MCP server Claude Code launches — into a standalone
# one-folder executable that ships in the desktop installer next to `atlas-server`, so the
# installed app is driveable from Claude Code without Python on the machine.
#
#   pyinstaller desktop/server/atlas_mcp.spec --noconfirm
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))  # noqa: F821  (spec lives in desktop/server)
sys.path.insert(0, ROOT)

PACKAGES = ["mcp_server", "mcp", "httpx", "httpcore", "anyio", "pydantic", "pydantic_core"]

hiddenimports = []
datas = []
# mcp.cli needs typer (not installed) and calls sys.exit(1) on import — skip it: the stdio
# server never touches the CLI.
_skip_cli = lambda name: not name.startswith("mcp.cli")  # noqa: E731
for pkg in PACKAGES:
    hiddenimports += collect_submodules(pkg, filter=_skip_cli)
    datas += collect_data_files(pkg, include_py_files=False)

a = Analysis(  # noqa: F821
    [os.path.join(SPECPATH, "atlas_mcp.py")],  # noqa: F821
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "factory", "django"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="atlas-mcp",
    # console=True: this is a stdio server — Claude Code talks to it over stdin/stdout, so
    # the executable must keep its standard streams (a windowed build would detach them).
    console=True,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="atlas-mcp",
)
