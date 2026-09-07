"""Diagnostics report (2026-09-06): one page that answers "why didn't it work?" — version,
where things live, the LaTeX engine, the update feed, the last compile failure and the tail of
the server log — with a copyable text form, so a report from the desktop is one paste."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from django.conf import settings

from core import client_errors
from core.backups import backup_status


def _tail(path: Path, lines: int = 120) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-lines:])


def update_feed_status(check_network: bool = False) -> list[dict]:
    conf = Path(settings.BASE_DIR) / "desktop" / "tauri.conf.json"
    rows: list[dict] = []
    try:
        import json

        endpoints = json.loads(conf.read_text())["plugins"]["updater"]["endpoints"]
    except Exception:
        return rows
    for url in endpoints:
        row = {"url": url, "status": None}
        if check_network:
            try:
                import httpx

                row["status"] = httpx.head(url, follow_redirects=True, timeout=4).status_code
            except Exception as exc:  # offline, DNS, proxy
                row["status"] = exc.__class__.__name__
        rows.append(row)
    return rows


def _latex_state() -> dict:
    """Engine cache + warm-up state (writing/warmup.py); never lets a cache-dir error break
    the report."""
    try:
        from writing.warmup import status

        return status()
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "state": "unknown",
            "log": str(exc),
            "warm": False,
            "dir": "",
            "size_mb": 0,
            "seconds": None,
        }


def collect(check_network: bool = False) -> dict:
    from writing.compile import tectonic_path
    from writing.models import Manuscript

    data_dir = getattr(settings, "DATA_DIR", None)
    engine = tectonic_path()
    failed = (
        Manuscript.objects.filter(compile_status="failed")
        .order_by("-updated_at")
        .values("id", "title", "compile_log", "updated_at")
        .first()
    )
    db = settings.DATABASES["default"]
    return {
        "version": os.environ.get("ATLAS_VERSION", "dev"),
        "desktop": bool(getattr(settings, "ATLAS_DESKTOP", False)),
        "platform": f"{platform.system()} {platform.release()} · Python {sys.version.split()[0]}",
        "frozen": bool(getattr(sys, "frozen", False)),
        "settings_module": os.environ.get("DJANGO_SETTINGS_MODULE", ""),
        "data_dir": str(data_dir) if data_dir else None,
        "database": db.get("ENGINE", "").rsplit(".", 1)[-1] + " · " + str(db.get("NAME", "")),
        "engine": str(engine) if engine else None,
        "latex": _latex_state(),
        "jobs": "in-process (immediate)" if settings.HUEY.get("immediate") else "worker (huey)",
        "api_key_configured": bool(settings.ATLAS_API_KEY),
        "update_feed": update_feed_status(check_network),
        "last_failed_compile": (
            {
                "manuscript": failed["id"],
                "title": failed["title"],
                "log": failed["compile_log"][-2500:],
                "at": failed["updated_at"],
            }
            if failed
            else None
        ),
        "server_log": _tail(Path(data_dir) / "atlas-server.log") if data_dir else "",
        "client_errors": client_errors.recent(),
        "access": _access(),
        "backups": backup_status(),  # #424
    }


def _access() -> dict:
    try:
        from core.access import recent, summary

        return {"summary": summary(), "events": recent(12)}
    except Exception:  # noqa: BLE001 - a missing table (pre-migration) must not break the page
        return {"summary": None, "events": []}


def as_text(report: dict) -> str:
    """The paste-into-a-bug-report form."""
    lines = [
        f"Atlas {report['version']} · {'desktop' if report['desktop'] else 'server'} · {report['platform']}",
        f"frozen: {report['frozen']} · settings: {report['settings_module']}",
        f"data dir: {report['data_dir']}",
        f"database: {report['database']}",
        f"LaTeX engine: {report['engine'] or 'NOT FOUND'}",
        f"TeX bundle cache: {'warm' if report['latex']['warm'] else 'cold'} "
        f"({report['latex']['size_mb']} MB at {report['latex']['dir']}) · warm-up {report['latex']['state']}",
        f"jobs: {report['jobs']} · API key configured: {report['api_key_configured']}",
    ]
    for row in report["update_feed"]:
        lines.append(
            f"update feed: {row['url']} → {row['status'] if row['status'] is not None else 'not checked'}"
        )
    if report["last_failed_compile"]:
        f = report["last_failed_compile"]
        lines += ["", f"last failed compile: #{f['manuscript']} {f['title']} ({f['at']})", f["log"]]
    backups = report.get("backups") or {}
    if backups:
        last = backups.get("last")
        lines.append(
            "last backup: "
            + (f"{last['at']} ({last['days_ago']} days ago)" if last else "never")
            + (" — STALE" if backups.get("stale") else "")
        )
    access = report.get("access") or {}
    if access.get("summary"):
        c = access["summary"]["counts"]
        lines.append(
            f"access ({access['summary']['days']} days): {c.get('login_ok', 0)} logins · "
            f"{c.get('login_failed', 0)} failed · {c.get('login_locked', 0)} lockouts · "
            f"{c.get('api_key_rejected', 0)} rejected API keys"
        )
    if report.get("client_errors"):
        lines += ["", "front-end errors (most recent first):"]
        for entry in report["client_errors"]:
            lines.append(
                f"  {entry['at']} · {entry['where']} · {entry['url']} · {entry['version'] or 'dev'}"
            )
            lines += [f"    {e}" for e in entry["errors"]] or ["    (no message captured)"]
    if report["server_log"]:
        lines += ["", "server log (tail):", report["server_log"]]
    return "\n".join(lines)
