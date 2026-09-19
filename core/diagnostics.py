"""Diagnostics report (2026-09-06): one page that answers "why didn't it work?" — version,
where things live, the LaTeX engine, the update feed, the last compile failure and the tail of
the server log — with a copyable text form, so a report from the desktop is one paste."""

from __future__ import annotations

import os
import platform
import shutil
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
    report = {
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
        "frame_ancestors": list(getattr(settings, "ATLAS_FRAME_ANCESTORS", []) or []),  # #539
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
        "disk": _disk(data_dir),  # #572
        "media_writable": _media_writable(),  # #572
    }
    # #572: what is wrong, and the fix — guarded like every other section: this is the one
    # page that must render when things are broken, so a malformed cache entry cannot 500 it
    try:
        report["findings"] = findings(report)
        report["verdict"] = verdict(report["findings"])
    except Exception:  # noqa: BLE001
        report["findings"] = []
        report["verdict"] = {
            "state": "warn",
            "text": "The verdict could not be computed — copy the report anyway.",
        }
    return report


def _disk(data_dir) -> dict | None:
    """Free space where Atlas writes (the data folder, else MEDIA_ROOT) — a full disk is the
    failure nobody's log explains (#572)."""
    try:
        where = Path(data_dir) if data_dir else Path(settings.MEDIA_ROOT)
        while not where.exists() and where.parent != where:
            where = where.parent
        usage = shutil.disk_usage(where)
        return {"path": str(where), "free_bytes": usage.free, "total_bytes": usage.total}
    except Exception:  # noqa: BLE001 - an odd mount must not break the page
        return None


def _media_writable() -> bool | None:
    """Can uploads land? `os.access`, not a probe file: this runs on every load of the page."""
    try:
        media = Path(settings.MEDIA_ROOT)
        target = media if media.exists() else media.parent
        return os.access(target, os.W_OK)
    except Exception:  # noqa: BLE001
        return None


LOW_DISK_BYTES = 1 << 30  # 1 GB: warn
NO_DISK_BYTES = 200 << 20  # 200 MB: the next upload, snapshot or compile fails


FAILED_LOGINS = 3  # failed logins in the access window before the verdict mentions them
COMPILE_DAYS = 7  # a compile failure older than this is history, not a finding


def _recent(at) -> bool:
    """True when `at` (a datetime, an ISO string, or nothing) is within COMPILE_DAYS."""
    from datetime import datetime, timedelta

    from django.utils import timezone

    if at is None:
        return True
    if isinstance(at, str):
        try:
            at = datetime.fromisoformat(at)
        except ValueError:
            return True
    if not isinstance(at, datetime):
        return True
    if timezone.is_naive(at):
        at = timezone.make_aware(at)
    return timezone.now() - at <= timedelta(days=COMPILE_DAYS)


def _finding(id_, level, title, detail, fix, link=None) -> dict:
    return {"id": id_, "level": level, "title": title, "detail": detail, "fix": fix, "link": link}


def findings(report: dict) -> list[dict]:
    """Why didn't it work — the rules over the collected report (#572). Pure: no I/O, every
    optional section may be None. Two levels only: "fail" (broken now) before "warn" (will
    bite, or is drifting). Each row says what is wrong and what to do about it."""
    rows: list[dict] = []
    latex = report.get("latex") or {}
    if not report.get("engine"):
        rows.append(
            _finding(
                "engine",
                "fail",
                "No LaTeX engine",
                "Every compile fails until Tectonic is found.",
                "Desktop builds bundle it; on a server run `make tectonic`.",
            )
        )
    elif latex.get("state") == "failed":
        last = (latex.get("log") or "").strip().splitlines()
        rows.append(
            _finding(
                "latex_failed",
                "fail",
                "The TeX bundle warm-up failed",
                (last[-1][:160] if last else "no log captured"),
                "Warm up again from this page; a proxy or an offline machine is the usual cause.",
            )
        )
    elif not latex.get("warm") and latex.get("state") != "running":
        rows.append(
            _finding(
                "latex_cold",
                "warn",
                "The TeX bundle is not cached yet",
                "The first compile downloads it — a few hundred MB, minutes on a slow line — "
                "and looks stuck meanwhile.",
                "Warm up now from this page, while nothing is waiting on it.",
            )
        )
    if not report.get("api_key_configured"):
        rows.append(
            _finding(
                "api_key",
                "fail",
                "No API key",
                "Claude Code, the MCP server and every script are refused.",
                "Set ATLAS_API_KEY — the Connect page shows it; on a server `manage.py rotate_api_key`.",
                "/connect",
            )
        )
    if report.get("media_writable") is False:
        rows.append(
            _finding(
                "media",
                "fail",
                "The files folder is not writable",
                "Uploads, PDFs and compiles cannot be saved.",
                "Fix the permissions on MEDIA_ROOT (the data folder on the desktop).",
            )
        )
    disk = report.get("disk") or {}
    free = disk.get("free_bytes")
    if free is not None and free < NO_DISK_BYTES:
        rows.append(
            _finding(
                "disk",
                "fail",
                "The disk is full",
                f"{free / 1048576:.0f} MB free at {disk.get('path')} — the next upload, "
                "snapshot or compile fails.",
                "Free space, or move the data folder to a bigger disk.",
            )
        )
    elif free is not None and free < LOW_DISK_BYTES:
        rows.append(
            _finding(
                "disk",
                "warn",
                "The disk is nearly full",
                f"{free / 1073741824:.1f} GB free at {disk.get('path')}.",
                "Snapshots and PDFs will stop fitting; free space soon.",
            )
        )
    snaps = report.get("snapshots") or {}
    if snaps.get("last_error"):
        rows.append(
            _finding(
                "snapshot_error",
                "fail",
                "The last automatic snapshot failed",
                str(snaps["last_error"].get("detail", "")),
                "Snapshot now from this page to see whether it still fails.",
            )
        )
    elif report.get("desktop") and snaps and not snaps.get("scheduler"):
        rows.append(
            _finding(
                "snapshot_scheduler",
                "warn",
                "Automatic snapshots are not running",
                "The scheduler thread is not alive, so no backup zip is being written.",
                "Restart Atlas; if it stays off, copy this report into a bug report.",
            )
        )
    dest = report.get("backup_destination") or {}
    if dest.get("enabled"):
        if dest.get("last_error"):
            rows.append(
                _finding(
                    "destination_error",
                    "fail",
                    "The last copy to the backup destination failed",
                    str(dest["last_error"].get("detail", "")),
                    "Copy newest now from this page; check the drive or the sync client.",
                )
            )
        elif not dest.get("reachable"):
            rows.append(
                _finding(
                    "destination_unreachable",
                    "fail",
                    "The backup destination is not reachable",
                    f"{dest.get('dir')} — unplugged, or the sync client is not running.",
                    "Plug the drive in or start the sync client; copies resume on their own.",
                )
            )
        elif dest.get("in_sync") is False:
            rows.append(
                _finding(
                    "destination_behind",
                    "warn",
                    "The newest snapshot has not reached the backup destination",
                    f"{dest.get('dir')} holds an older copy.",
                    "Copy newest now from this page.",
                )
            )
    backups = report.get("backups") or {}
    if backups.get("has_data") and backups.get("stale"):
        last = backups.get("last")
        rows.append(
            _finding(
                "backup_stale",
                "warn",
                "No recent backup" if last else "No backup yet",
                (
                    f"The last one is {last['days_ago']} days old."
                    if last
                    else "Nothing has been backed up since this install began."
                ),
                "Download a backup, or Snapshot now, from this page.",
            )
        )
    failed = report.get("last_failed_compile")
    if failed and _recent(failed.get("at")):  # an abandoned draft must not warn forever
        rows.append(
            _finding(
                "compile_failed",
                "warn",
                f"The last compile of “{failed.get('title', '')}” failed",
                "Its log is further down this page.",
                "Open the manuscript in the Studio; the Problems panel names the line.",
                f"/manuscripts/{failed.get('manuscript')}/editor",
            )
        )
    errors = report.get("client_errors") or []
    if errors:
        rows.append(
            _finding(
                "client_errors",
                "warn",
                f"{len(errors)} front-end error{'s' if len(errors) != 1 else ''} recorded",
                f"The newest at {errors[0].get('where', '?')}, {errors[0].get('at', '')}.",
                "The messages are further down this page; copy the report when asking for help.",
            )
        )
    access = (report.get("access") or {}).get("summary") or {}
    counts = access.get("counts") or {}
    problem = access.get("last_problem") or {}
    stamp = (
        f" (last {problem['at'].replace('T', ' ')[:16]} from {problem.get('address') or '?'})"
        if problem.get("at")
        else ""
    )
    rejected = counts.get("api_key_rejected", 0)
    if rejected:
        rows.append(
            _finding(
                "access_rejected",
                "warn",
                f"{rejected} request{'s' if rejected != 1 else ''} carried a wrong API key",
                f"In the last {access.get('days', 7)} days{stamp}.",
                "A client with a stale key — re-copy it from the Connect page — or "
                "something probing the port.",
                "/connect",
            )
        )
    # one mistyped password is not a finding; a lockout, or three misses, is
    if counts.get("login_locked", 0) or counts.get("login_failed", 0) >= FAILED_LOGINS:
        rows.append(
            _finding(
                "access_logins",
                "warn",
                f"{counts.get('login_failed', 0)} failed login"
                f"{'s' if counts.get('login_failed', 0) != 1 else ''} · "
                f"{counts.get('login_locked', 0)} lockout"
                f"{'s' if counts.get('login_locked', 0) != 1 else ''}",
                f"In the last {access.get('days', 7)} days{stamp}.",
                "A mistyped password is fine; an unknown address is not — the list below names it.",
            )
        )
    uv = report.get("update_verdict") or {}
    if uv.get("state") in ("unreachable", "unsigned", "wrong_key"):
        rows.append(
            _finding(
                "update",
                "warn",
                "This install cannot update itself",
                uv.get("text", ""),
                "Get the newest build by hand from the releases page.",
            )
        )
    elif uv.get("state") == "offline":
        rows.append(
            _finding(
                "update_offline",
                "warn",
                "The update feed could not be reached",
                uv.get("text", ""),
                "Check the connection or a proxy; try the probe again later.",
            )
        )
    log = report.get("server_log") or ""
    if "Traceback (most recent call last)" in log or " ERROR " in log:
        rows.append(
            _finding(
                "server_log",
                "warn",
                "The server log carries errors",
                "A traceback or an ERROR line is in the tail further down this page.",
                "Copy the report when asking for help; the last lines say what broke.",
            )
        )
    order = {"fail": 0, "warn": 1}
    rows.sort(key=lambda r: order[r["level"]])
    return rows


def verdict(rows: list[dict]) -> dict:
    """One line over the findings: ok / warn / fail and the sentence the page leads with."""
    fails = sum(1 for r in rows if r["level"] == "fail")
    warns = len(rows) - fails
    if not rows:
        return {"state": "ok", "text": "Nothing wrong that Atlas can see."}
    parts = []
    if fails:
        parts.append(f"{fails} thing{'s' if fails != 1 else ''} broken")
    if warns:
        parts.append(f"{warns} to watch")
    return {"state": "fail" if fails else "warn", "text": " · ".join(parts) + "."}


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
        from core.access import problems, recent, recent_logins, summary

        # #573: the problems first (windowed, capped), the last logins apart, the raw tail kept
        return {
            "summary": summary(),
            "problems": problems(),
            "logins": recent_logins(),
            "events": recent(12),
        }
    except Exception:  # noqa: BLE001 - a missing table (pre-migration) must not break the page
        return {"summary": None, "problems": [], "logins": [], "events": []}


def as_text(report: dict) -> str:
    """The paste-into-a-bug-report form — the verdict first, then the facts (#572)."""
    lines = []
    if report.get("verdict"):
        lines.append(f"verdict: {report['verdict']['text']}")
        for row in report.get("findings") or []:
            lines.append(
                f"  {row['level'].upper()}: {row['title']} — {row['detail']} → {row['fix']}"
            )
        lines.append("")
    lines += [
        f"Atlas {report['version']} · {'desktop' if report['desktop'] else 'server'} · {report['platform']}",
        f"frozen: {report['frozen']} · settings: {report['settings_module']}",
        f"data dir: {report['data_dir']}",
        f"database: {report['database']}",
        f"LaTeX engine: {report['engine'] or 'NOT FOUND'}",
        f"TeX bundle cache: {'warm' if report['latex']['warm'] else 'cold'} "
        f"({report['latex']['size_mb']} MB at {report['latex']['dir']}) · warm-up {report['latex']['state']}",
        f"jobs: {report['jobs']} · API key configured: {report['api_key_configured']}",
        "embeddable from: "
        + (", ".join(report.get("frame_ancestors") or []) or "nobody (X-Frame-Options DENY)"),
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
        for row in access.get("problems") or []:  # #573: the rows the verdict points at
            if not isinstance(row, dict):
                continue
            lines.append(
                f"  {row.get('at', '').replace('T', ' ')[:16]} · {row.get('label', row.get('kind', ''))}"
                f" · {row.get('address') or '?'}"
                + (f" · {row['detail']}" if row.get("detail") else "")
                + (f" · {row['user_agent'][:60]}" if row.get("user_agent") else "")
            )
    if report.get("client_errors"):
        lines += ["", "front-end errors (most recent first):"]
        for entry in report["client_errors"]:
            if not isinstance(entry, dict):  # #572: a malformed cache entry must not break the text
                continue
            lines.append(
                f"  {entry['at']} · {entry['where']} · {entry['url']} · {entry['version'] or 'dev'}"
            )
            lines += [f"    {e}" for e in entry["errors"]] or ["    (no message captured)"]
    if report["server_log"]:
        lines += ["", "server log (tail):", report["server_log"]]
    return "\n".join(lines)
