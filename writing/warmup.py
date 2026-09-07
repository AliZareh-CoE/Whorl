"""LaTeX engine warm-up (2026-09-06, after the owner's "latex didn't compile").

Tectonic downloads the TeX bundle it needs on first use — a few hundred megabytes on a slow
link, minutes of silence behind a "Compiling…" spinner. This module answers two questions
the Diagnostics page asks — *is the engine's cache warm?* and *warm it now* — by compiling
a small document that pulls the packages a typical paper uses, on a background thread, with
the state kept in the Django cache so the page can poll it.
"""

import logging
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from django.core.cache import cache

log = logging.getLogger(__name__)

CACHE_KEY = "latex-warmup"
LOCK = threading.Lock()
WARM_TIMEOUT = 900
# the packages nearly every manuscript pulls in; compiling this once fills the cache for them
HELLO = r"""\documentclass{article}
\usepackage{amsmath,amssymb,graphicx,hyperref,natbib,booktabs,xcolor,geometry}
\begin{document}
Warm-up: $\int_0^1 x^2\,dx = \tfrac{1}{3}$.
\end{document}
"""


def cache_dir() -> Path:
    """Where Tectonic keeps its bundle files (respecting TECTONIC_CACHE_DIR)."""
    env = os.environ.get("TECTONIC_CACHE_DIR")
    if env:
        return Path(env)
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
        return base / "TectonicProject" / "Tectonic" / "cache"
    if system == "Darwin":
        return home / "Library" / "Caches" / "Tectonic"
    return Path(os.environ.get("XDG_CACHE_HOME") or home / ".cache") / "Tectonic"


def cache_state() -> dict:
    """{dir, warm, size_mb}: warm when the bundle cache holds files already."""
    d = cache_dir()
    files = d / "files"
    size = 0
    if d.is_dir():
        for p in d.rglob("*"):
            if p.is_file():
                try:
                    size += p.stat().st_size
                except OSError:
                    pass
    warm = files.is_dir() and any(files.iterdir())
    return {"dir": str(d), "warm": bool(warm), "size_mb": round(size / 1_048_576)}


def status() -> dict:
    """The current warm-up state merged with the cache state."""
    return {
        "state": "idle",
        "log": "",
        "seconds": None,
        **(cache.get(CACHE_KEY) or {}),
        **cache_state(),
    }


def run_warm_up() -> dict:
    """Compile the warm-up document synchronously and record the outcome."""
    from .compile import COMPILE_TIMEOUT, MISSING_ENGINE, tectonic_path

    engine = tectonic_path()
    if engine is None:
        cache.set(CACHE_KEY, {"state": "failed", "log": MISSING_ENGINE, "seconds": None}, None)
        return status()
    cache.set(CACHE_KEY, {"state": "running", "log": "", "seconds": None}, None)
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        (work / "warmup.tex").write_text(HELLO)
        run_kwargs = {}
        if sys.platform == "win32":
            run_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(
                [str(engine), "--untrusted", "--chatter", "minimal", "warmup.tex"],
                cwd=work,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(WARM_TIMEOUT, COMPILE_TIMEOUT),
                **run_kwargs,
            )
            ok = proc.returncode == 0 and (work / "warmup.pdf").exists()
            tail = (proc.stdout + proc.stderr).strip()[-3000:]
        except subprocess.TimeoutExpired:
            ok, tail = False, "Warm-up timed out — the bundle download did not finish."
        except OSError as exc:
            ok, tail = False, str(exc)
    seconds = round(time.monotonic() - started, 1)
    cache.set(CACHE_KEY, {"state": "ok" if ok else "failed", "log": tail, "seconds": seconds}, None)
    return status()


def start_warm_up() -> dict:
    """Kick off a warm-up on a daemon thread unless one is already running."""
    with LOCK:
        current = cache.get(CACHE_KEY) or {}
        if current.get("state") == "running":
            return status()
        cache.set(CACHE_KEY, {"state": "running", "log": "", "seconds": None}, None)

    def worker():
        from django.db import connection

        try:
            run_warm_up()
        except Exception:  # pragma: no cover - recorded, never raised into the thread
            log.exception("LaTeX warm-up crashed")
            cache.set(
                CACHE_KEY,
                {"state": "failed", "log": "warm-up crashed; see the server log", "seconds": None},
                None,
            )
        finally:
            connection.close()

    threading.Thread(target=worker, name="latex-warmup", daemon=True).start()
    return status()
