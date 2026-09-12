"""Front-end crash reports (2026-09-07, #382).

The owner's desktop showed a blank window (only the shell background) for several builds and
nothing anywhere said why: a crash in the web view has no console the owner can see. The SPA
now reports three kinds of failure here — the boot watchdog in ``spa.html`` (the app script
never mounted), an unhandled error/rejection, and a React render error caught by the error
boundary — and each lands in the server log (the desktop's ``atlas-server.log``) and in the
Diagnostics report, so the next report carries the actual error text.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from django.core.cache import cache

log = logging.getLogger("atlas.client")
CACHE_KEY = "atlas-client-errors"
KEEP = 20


def _clip(value, limit: int) -> str:
    return str(value)[:limit]


def record(payload: dict, *, user_agent: str = "") -> dict:
    """Normalise one report, log it, keep the last few for Diagnostics."""
    errors = payload.get("errors") or []
    if not isinstance(errors, list):
        errors = [errors]
    entry = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "where": _clip(payload.get("where") or "app", 40),
        "url": _clip(payload.get("url") or "", 300),
        "version": _clip(payload.get("version") or "", 40),
        "errors": [_clip(e, 1500) for e in errors[:12]],
        "user_agent": _clip(user_agent, 300),
    }
    log.error(
        "front-end %s error at %s (%s): %s",
        entry["where"],
        entry["url"],
        entry["version"] or "dev",
        " | ".join(entry["errors"]) or "(no message)",
    )
    recent_entries = recent()
    recent_entries.insert(0, entry)
    cache.set(CACHE_KEY, recent_entries[:KEEP], None)
    return entry


def recent() -> list[dict]:
    value = cache.get(CACHE_KEY)
    return list(value) if isinstance(value, list) else []


def clear() -> None:
    cache.delete(CACHE_KEY)
