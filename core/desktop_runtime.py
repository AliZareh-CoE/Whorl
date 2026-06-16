"""Bundled-Postgres lifecycle for the self-contained desktop app (#210g).

The owner wants the real Postgres (full parity, incl. full-text search) shipped inside the
installer and started automatically — no Docker, no manual setup. This module runs `initdb`
into the per-user data dir on first launch, starts a local `postgres` listening only on
127.0.0.1, creates the `atlas` role + database, and tears it down on exit. The desktop
runtime calls `ensure_postgres()` before Django connects.

Postgres binaries are located via ATLAS_PG_BIN (set by the Tauri shell to the bundled
`bin/` dir), then the PATH, then the usual system locations.
"""

import atexit
import os
import shutil
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path

DB_NAME = "atlas"
DB_USER = "atlas"


def _log(msg: str) -> None:
    """Flush a setup-progress line to the captured server log (atlas_server.py points stdout at
    atlas-server.log). ensure_postgres used to be silent, so a hang here left the log empty and
    us debugging blind (#265) — now every step announces itself, flushed immediately."""
    try:
        print(f"[setup] {msg}", flush=True)
    except Exception:
        pass


def _wait_for_tcp(port: int, timeout: float = 60.0) -> bool:
    """Bounded wait until something accepts a TCP connection on 127.0.0.1:port. A raw socket
    with settimeout() is reliably bounded on Windows — unlike libpq's connect_timeout, which we
    suspect was being ignored, letting the psycopg wait loop block forever with no log (#265)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            try:
                sock.connect(("127.0.0.1", port))
                return True
            except OSError:
                time.sleep(0.5)
    return False


# On Windows, start the Postgres helpers in their OWN process group with no console window, so
# a console control event (Ctrl+C / close) can't propagate to Postgres and Ctrl+C its background
# workers — which crash-looped it with 0xC000013A (#245). 0 elsewhere (POSIX ignores it).
_CREATIONFLAGS = (0x00000200 | 0x08000000) if os.name == "nt" else 0  # NEW_PROCESS_GROUP|NO_WINDOW


def _plain(path: str) -> str:
    """Drop Windows' extended-length `\\\\?\\` prefix. Tauri's resource_dir() hands us paths
    like `\\\\?\\C:\\...`, and Postgres' initdb mis-resolves its sibling `share/` dir from such
    a path (failing with exit 1), so we always invoke the binaries by their plain path."""
    return path[4:] if path.startswith("\\\\?\\") else path


def _pg_bin(name: str) -> str:
    """Resolve a postgres binary (initdb/postgres/pg_ctl/createdb/createuser/pg_isready)."""
    # on Windows the binaries carry a .exe suffix; harmlessly check both names everywhere.
    names = [name, name + ".exe"]
    # ATLAS_PG_BIN may point at the bin dir or its parent (the pg root) — try both.
    search_dirs = []
    bindir = os.environ.get("ATLAS_PG_BIN")
    if bindir:
        bindir = _plain(bindir)
        search_dirs += [Path(bindir), Path(bindir) / "bin"]
    for directory in search_dirs:
        for candidate_name in names:
            candidate = directory / candidate_name
            if candidate.exists():
                return _plain(str(candidate))
    found = shutil.which(name)
    if found:
        return _plain(found)
    for base in sorted(Path("/usr/lib/postgresql").glob("*/bin"), reverse=True):
        candidate = base / name
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(f"postgres binary '{name}' not found (set ATLAS_PG_BIN)")


def _run(args, **kw):
    """Run a Postgres helper, raising with its stderr on failure. The desktop window has no
    console, so a bare non-zero exit is invisible — we surface stdout+stderr so the captured
    server log says *why* (e.g. initdb's actual complaint), not just an exit code. A timeout
    (default 180s) keeps a wedged initdb/pg_ctl from hanging the whole launch forever (#244)."""
    name = os.path.basename(str(args[0])) if isinstance(args, (list, tuple)) else str(args)
    kw.setdefault("timeout", 180)
    kw.setdefault("creationflags", _CREATIONFLAGS)
    # the windowed (no-console) build has no valid stdin handle; a child that inherits it can
    # fail to spawn on Windows, so always give the helpers a real (empty) stdin (#248).
    kw.setdefault("stdin", subprocess.DEVNULL)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, **kw)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{name} timed out after {exc.timeout}s — giving up.") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"{name} failed (exit {proc.returncode}).\n"
            f"stdout: {(proc.stdout or '').strip()}\nstderr: {(proc.stderr or '').strip()}"
        )
    return proc


def ensure_postgres(data_dir: Path, port: int):
    """Init (first run), start, and provision a local postgres; returns a stop() callable.

    Idempotent: re-launches reuse the existing cluster + database. Registers an atexit hook
    so the server process is stopped when the app quits.
    """
    data_dir = Path(data_dir)
    pgdata = data_dir / "pgdata"
    socket_dir = data_dir / "pgsock"
    socket_dir.mkdir(parents=True, exist_ok=True)
    _log(f"ensure_postgres: data_dir={data_dir} port={port}")

    if not (pgdata / "PG_VERSION").exists():
        _log("no cluster yet — running initdb")
        # A previous failed launch can leave a partial, non-empty pgdata with no PG_VERSION.
        # initdb refuses a non-empty target ("directory exists but is not empty"), which would
        # make every retry fail — so clear the half-built cluster first. Safe: without
        # PG_VERSION there is no real database here yet.
        if pgdata.exists():
            shutil.rmtree(pgdata, ignore_errors=True)
        _run(
            [
                _pg_bin("initdb"),
                "-D",
                str(pgdata),
                "-U",
                DB_USER,
                "--auth=trust",
                "--encoding=UTF8",
                "--no-locale",
            ]
        )

    # self-healing: if a previous run was hard-killed (postgres is detached by pg_ctl, so
    # an unclean app exit can orphan it), stop that instance before starting a fresh one.
    _log("self-heal: stopping any orphaned cluster")
    try:
        subprocess.run(
            [_pg_bin("pg_ctl"), "-D", str(pgdata), "-m", "immediate", "stop"],
            check=False,
            capture_output=True,
            timeout=60,
            creationflags=_CREATIONFLAGS,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        pass

    logfile = data_dir / "postgres.log"
    # Postgres options. The app always connects over TCP loopback (127.0.0.1:port), so the
    # unix socket is incidental — and on Windows there is none: passing a `-k <windows path>`
    # (which is also space-split inside this `-o` string, breaking on usernames with spaces)
    # makes `pg_ctl start` fail, which is exactly the "127.0.0.1 refused to connect" the owner
    # saw. Only add the private socket dir on POSIX, where it works and adds a little privacy.
    pg_opts = [f"-p {port}", "-c listen_addresses=127.0.0.1"]
    if os.name != "nt":
        pg_opts.insert(1, f"-k {socket_dir}")
    _log(f"starting postgres on 127.0.0.1:{port}")
    try:
        _run(
            [
                _pg_bin("pg_ctl"),
                "-D",
                str(pgdata),
                "-l",
                str(logfile),
                "-w",
                "start",
                "-o",
                " ".join(pg_opts),
            ]
        )
    except RuntimeError as exc:
        # surface *why* it failed (the server log is the only window the owner has) instead of
        # a bare non-zero exit that just bubbles up as a blank connection-refused page.
        tail = logfile.read_text(errors="ignore")[-2000:] if logfile.exists() else ""
        raise RuntimeError(f"{exc}\n--- postgres.log (tail) ---\n{tail}") from exc

    def stop():
        try:
            _run([_pg_bin("pg_ctl"), "-D", str(pgdata), "-m", "fast", "-w", "stop"])
        except Exception:
            pass

    atexit.register(stop)

    # Wait until the server accepts connections, then ensure the database exists — all through
    # psycopg, the driver the frozen server already ships. The Windows Postgres bundle contains
    # ONLY initdb/pg_ctl/postgres, not the pg_isready/psql/createdb CLIENT tools (#231), so we
    # must never shell out to those. (Cross-platform: psycopg talks TCP loopback everywhere.)
    import psycopg

    def _connect(dbname):
        # connect_timeout bounds the connection; statement_timeout (15s) bounds any query so a
        # wedged CREATE DATABASE / SELECT can't hang the launch forever (#244).
        return psycopg.connect(
            host="127.0.0.1",
            port=port,
            user=DB_USER,
            dbname=dbname,
            connect_timeout=3,
            options="-c statement_timeout=15000",
        )

    # First wait for the TCP port with a raw, reliably-bounded socket (#265 — pg_ctl -w already
    # reported ready, but this confirms it and never blocks). THEN open psycopg under a hard
    # thread timeout, so even if libpq ignores connect_timeout on Windows the launch can't hang
    # silently — it surfaces an error instead.
    _log("waiting for postgres to accept TCP connections")
    if not _wait_for_tcp(port, timeout=120):
        tail = logfile.read_text(errors="ignore")[-2000:] if logfile.exists() else ""
        raise RuntimeError(
            f"Postgres never opened 127.0.0.1:{port}.\n--- postgres.log (tail) ---\n{tail}"
        )
    _log("port open — opening a psycopg connection")

    def _create_db():
        with _connect("postgres") as conn:
            conn.autocommit = True  # CREATE DATABASE cannot run inside a transaction
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
                if cur.fetchone() is None:
                    _log(f"creating the {DB_NAME} database")
                    cur.execute(f'CREATE DATABASE "{DB_NAME}"')  # DB_NAME is a hardcoded constant

    last_err = None
    for attempt in range(1, 21):
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            executor.submit(_create_db).result(timeout=20)
            last_err = None
            break
        except FuturesTimeout:
            last_err = "psycopg connect/CREATE DATABASE exceeded 20s"
            _log(f"attempt {attempt}: {last_err} — retrying")
        except Exception as exc:  # OperationalError + anything libpq raises
            last_err = f"{type(exc).__name__}: {exc}"
            _log(f"attempt {attempt}: {last_err} — retrying")
            time.sleep(1.0)
        finally:
            executor.shutdown(wait=False)  # don't block on a hung connect thread
    if last_err is not None:
        tail = logfile.read_text(errors="ignore")[-2000:] if logfile.exists() else ""
        raise RuntimeError(
            f"Postgres accepted TCP but provisioning failed on 127.0.0.1:{port}: {last_err}\n"
            f"--- postgres.log (tail) ---\n{tail}"
        )
    _log("postgres ready")
    return stop
