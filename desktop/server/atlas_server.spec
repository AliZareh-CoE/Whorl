# PyInstaller spec for the bundled Atlas server (#210d).
#
# Freezes `atlas_server.py` (which runs `manage.py run_desktop` under the SQLite desktop
# settings) into a standalone, one-folder executable named `atlas-server`. Django discovers
# apps / migrations / templates dynamically, so we collect every local app's submodules +
# data and bundle the project-level templates/ and static/ at the root (where BASE_DIR
# resolves to inside the frozen bundle).
#
#   pyinstaller desktop/server/atlas_server.spec --noconfirm
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))  # noqa: F821  (spec lives in desktop/server)
# collect_submodules below imports the local packages to walk them, so the project root
# must be importable while the spec runs (pathex only applies to the later Analysis).
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.desktop")
os.environ.setdefault("DEBUG", "False")
os.environ.setdefault("ATLAS_API_KEY", "")

LOCAL_APPS = [
    "config",
    "core",
    "projects",
    "documents",
    "plans",
    "literature",
    "writing",
    "notes",
    "research",
    "api",
    "prompts",
    "bots",
]
THIRD_PARTY = [
    "django",
    "rest_framework",
    "drf_spectacular",
    "waitress",
    "whitenoise",
    "huey",
    "environ",
    "markdown",
    "nh3",
    "corsheaders",
    "pypdf",
]

hiddenimports = []
datas = [
    (os.path.join(ROOT, "templates"), "templates"),
    (os.path.join(ROOT, "static"), "static"),
    # #534: Diagnostics reads the updater endpoints + public key from the Tauri config so the
    # "Update check" verdict on an installed app looks at the same feed the app does.
    (os.path.join(ROOT, "desktop", "tauri.conf.json"), "desktop"),
    # #535: the Claude Code skills the Connect page installs (core/skills.py reads them from
    # mcp_server/skills beside core/) — a directory copy, so a new skill folder ships by itself.
    (os.path.join(ROOT, "mcp_server", "skills"), os.path.join("mcp_server", "skills")),
]
# The LaTeX engine (Tectonic) rides along when the release workflow fetched it into bin/,
# so Recompile works out of the box on an installed desktop app (writing/compile.py looks
# in BASE_DIR/bin first). PyInstaller keeps the executable bit.
for engine in ("tectonic", "tectonic.exe"):
    if os.path.exists(os.path.join(ROOT, "bin", engine)):
        datas.append((os.path.join(ROOT, "bin", engine), "bin"))
for pkg in LOCAL_APPS + THIRD_PARTY:
    hiddenimports += collect_submodules(pkg)
    datas += collect_data_files(pkg, include_py_files=True)

a = Analysis(  # noqa: F821
    [os.path.join(SPECPATH, "atlas_server.py")],  # noqa: F821
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "factory"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="atlas-server",
    # windowed (no console): the server is a background process the Tauri window owns, so a
    # black console box would only confuse (#245). Output already goes to atlas-server.log.
    console=False,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="atlas-server",
)
