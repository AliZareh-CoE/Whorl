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


FEED_MAX_BYTES = 256 * 1024  # a latest.json is a few KB; never read a runaway body


def _key_id(minisign_b64: str) -> str:
    """The 8-byte key id inside a minisign public key or signature (both are base64 of a
    two-line minisign file; the id follows the two-byte algorithm tag)."""
    import base64

    try:
        lines = base64.b64decode(minisign_b64).decode().splitlines()
        raw = base64.b64decode(lines[1])
        return raw[2:10].hex()
    except Exception:
        return ""


def _version_tuple(version: str) -> tuple[int, ...] | None:
    parts = (version or "").strip().lstrip("v").split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _probe_feed(url: str, pubkey_id: str) -> dict:
    """GET one updater endpoint the way the app does and read what it says (#534)."""
    import json

    import httpx

    row: dict = {"url": url, "status": None, "version": None, "platforms": [], "key_match": None}
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=6) as resp:
            row["status"] = resp.status_code
            if resp.status_code != 200:
                return row
            body = b""
            for chunk in resp.iter_bytes():
                body += chunk
                if len(body) > FEED_MAX_BYTES:
                    row["status"] = "too large"
                    return row
    except Exception as exc:  # offline, DNS, proxy
        row["status"] = exc.__class__.__name__
        return row
    try:
        feed = json.loads(body)
        row["version"] = str(feed.get("version") or "")
        platforms = feed.get("platforms") or {}
        row["platforms"] = sorted(platforms)
        sigs = [
            _key_id(p["signature"])
            for p in platforms.values()
            if isinstance(p, dict) and p.get("signature")
        ]
        if sigs and pubkey_id:  # no signatures at all → None → "unsigned"
            row["key_match"] = all(k == pubkey_id for k in sigs)
    except Exception:
        row["status"] = "not a feed"
    return row


# What desktop/tauri.conf.json says, for an install whose bundle lacks the file (an older
# frozen server, or a source checkout without desktop/). test_diagnostics pins it to the conf.
UPDATER_FALLBACK = {
    "endpoints": [
        "https://github.com/AliZareh-CoE/Whorl/releases/download/desktop-preview/latest.json",
        "https://github.com/alizareh-coe/project-manager/releases/download/desktop-preview/latest.json",
        "https://github.com/alizareh-coe/atlas-releases/releases/download/desktop-preview/latest.json",
    ],
    "pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IERDRTg1OEIzRjNCNUYyNzEKUldSeDhyWHpzMWpvM0JOMFVNRGlxOGlEOTRhdDNPTHNoSzJlaVh6RkF5WEoyRnNGNlR5SXVtMHAK",
}


def updater_config() -> dict:
    """The updater block of desktop/tauri.conf.json, or the pinned copy when the file is not
    beside the server (#534)."""
    import json

    conf = Path(settings.BASE_DIR) / "desktop" / "tauri.conf.json"
    try:
        updater = json.loads(conf.read_text())["plugins"]["updater"]
        return {"endpoints": list(updater["endpoints"]), "pubkey": updater.get("pubkey", "")}
    except Exception:
        return UPDATER_FALLBACK


def update_feed_status(check_network: bool = False) -> list[dict]:
    """The app's updater endpoints, and — with the network — what each answers: the HTTP
    status, the build the feed offers, its platforms, and whether its signatures were made
    with the key this app trusts (#534: "the update link doesn't work" needs a verdict, not a
    status code)."""
    updater = updater_config()
    pubkey_id = _key_id(updater["pubkey"])
    rows: list[dict] = []
    for url in updater["endpoints"]:
        if check_network:
            rows.append(_probe_feed(url, pubkey_id))
        else:
            rows.append(
                {"url": url, "status": None, "version": None, "platforms": [], "key_match": None}
            )
    return rows


def update_verdict(rows: list[dict], version: str) -> dict:
    """One sentence for the researcher: can this install update, and if not, why. `state`
    is one of unchecked / offline / unreachable / unsigned / wrong_key / current / available /
    unknown_version."""
    probed = [r for r in rows if r["status"] is not None]
    if not probed:
        return {"state": "unchecked", "text": 'not checked — tick "Probe the update feed"'}
    feeds = [r for r in probed if r["status"] == 200 and r["version"]]
    if not feeds:
        if all(
            isinstance(r["status"], str) and r["status"] not in ("too large", "not a feed")
            for r in probed
        ):
            return {
                "state": "offline",
                "text": "could not reach GitHub — offline, or a proxy in the way",
            }
        codes = ", ".join(f"{r['url'].split('/')[4]}: {r['status']}" for r in probed)
        return {
            "state": "unreachable",
            "text": f"no endpoint answered with a feed ({codes}) — the release has no latest.json "
            "yet (CI publishes one when the signing secret is set) or the address moved",
        }
    feed = feeds[0]  # the app takes the first endpoint that answers, the same way
    if feed["key_match"] is False:
        return {
            "state": "wrong_key",
            "text": f"the feed offers {feed['version']} but it is signed with a different key than "
            "this app trusts — install that build once from the releases page; updates work "
            "in-app after that",
        }
    if feed["key_match"] is None:
        return {
            "state": "unsigned",
            "text": f"the feed offers {feed['version']} without signatures — the app refuses "
            "unsigned updates; CI signs them when TAURI_SIGNING_PRIVATE_KEY is set",
        }
    mine, theirs = _version_tuple(version), _version_tuple(feed["version"])
    if mine is None:
        return {
            "state": "unknown_version",
            "text": f"the feed offers {feed['version']} (signed for this app); this build reports "
            f'"{version or "dev"}", so the app cannot compare — a server or source install '
            "does not update itself",
        }
    if theirs is not None and theirs > mine:
        return {
            "state": "available",
            "text": f"{feed['version']} is available and signed for this app (you run {version}) — "
            'the sidebar offers it; click "Check for updates" if it does not',
        }
    return {
        "state": "current",
        "text": f"up to date — the feed offers {feed['version']}, you run {version}",
    }


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
    version = os.environ.get("ATLAS_VERSION", "dev")
    feed_rows = update_feed_status(check_network)
    return {
        "version": version,
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
        "update_feed": feed_rows,
        "update_verdict": update_verdict(feed_rows, version),  # #534
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
        "snapshots": _snapshots(),  # #462
        "backup_destination": _destination(),  # #536
    }


def _destination() -> dict | None:
    try:
        from core.destination import destination_status

        return destination_status()
    except Exception:  # noqa: BLE001 - an unplugged drive must not break the page
        return None


def _snapshots() -> dict | None:
    try:
        from core.snapshots import snapshot_status

        return snapshot_status()
    except Exception:  # noqa: BLE001 - an unreadable folder must not break the page
        return None


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
        answer = row["status"] if row["status"] is not None else "not checked"
        if row.get("version"):
            answer = (
                f"{answer} · offers {row['version']} · signed for this app: {row.get('key_match')}"
            )
        lines.append(f"update feed: {row['url']} → {answer}")
    verdict = report.get("update_verdict")
    if verdict:
        lines.append(f"update check: {verdict['text']}")
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
    snaps = report.get("snapshots") or {}
    if snaps:
        last = snaps.get("last")
        lines.append(
            f"snapshots: {snaps['count']} kept in {snaps['dir']} · last "
            + (f"{last['at']} ({last['hours_ago']} h ago)" if last else "none")
            + (f" · scheduler {'on' if snaps.get('scheduler') else 'off'}")
            + (
                f" · LAST FAILED: {snaps['last_error']['detail']}"
                if snaps.get("last_error")
                else ""
            )
        )
    dest = report.get("backup_destination") or {}
    if dest.get("dir"):
        newest = dest.get("newest_copy")
        lines.append(
            f"backup destination: {dest['dir']} ({dest['label']}) · "
            + ("reachable" if dest["reachable"] else "NOT REACHABLE")
            + f" · {dest['copies']} copies"
            + (f" · newest {newest['name']}" if newest else "")
            + (
                " · newest snapshot copied"
                if dest.get("in_sync")
                else " · NEWEST SNAPSHOT NOT COPIED YET"
                if dest.get("in_sync") is False
                else ""
            )
            + (f" · LAST FAILED: {dest['last_error']['detail']}" if dest.get("last_error") else "")
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
