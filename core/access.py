"""The access log (#399): record and read login / API-key events. Every call is best-effort —
nothing here may ever break a login or an API request."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from .models import AccessEvent

log = logging.getLogger("atlas.access")
KEEP = 500


def _address(request) -> str:
    if request is None:
        return ""
    meta = getattr(request, "META", {}) or {}
    forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else meta.get("REMOTE_ADDR", "") or "")[
        :64
    ]


def record(kind: str, request=None, detail: str = "") -> AccessEvent | None:
    try:
        agent = ""
        if request is not None:
            agent = (getattr(request, "META", {}) or {}).get("HTTP_USER_AGENT", "")
        event = AccessEvent.objects.create(
            kind=kind,
            address=_address(request),
            user_agent=str(agent)[:200],
            detail=str(detail)[:200],
        )
        # keep the table small: the newest KEEP rows survive
        cutoff = AccessEvent.objects.order_by("-created_at", "-id").values_list("id", flat=True)[
            KEEP : KEEP + 1
        ]
        if cutoff:
            AccessEvent.objects.filter(id__lte=cutoff[0]).delete()
        if kind != AccessEvent.Kind.LOGIN_OK:
            log.warning(
                "access: %s from %s (%s) %s", kind, event.address or "?", agent[:60], detail
            )
        return event
    except Exception:  # noqa: BLE001 - the door must open even if the log does not
        log.exception("access log write failed")
        return None


def _row(e: AccessEvent) -> dict:
    return {
        "id": e.id,
        "kind": e.kind,
        "label": e.get_kind_display(),
        "address": e.address,
        "user_agent": e.user_agent,
        "detail": e.detail,
        "at": e.created_at.isoformat(timespec="seconds"),
    }


def recent(limit: int = 50) -> list[dict]:
    return [_row(e) for e in AccessEvent.objects.all()[:limit]]


def problems(days: int = 7, limit: int = 12) -> list[dict]:
    """The rows that matter (#573): failed logins, lockouts and rejected keys in the window,
    newest first — the owner's own logins would otherwise push them out of any short list."""
    since = timezone.now() - timedelta(days=days)
    rows = AccessEvent.objects.exclude(kind=AccessEvent.Kind.LOGIN_OK).filter(created_at__gte=since)
    return [_row(e) for e in rows[:limit]]


def recent_logins(limit: int = 5) -> list[dict]:
    return [_row(e) for e in AccessEvent.objects.filter(kind=AccessEvent.Kind.LOGIN_OK)[:limit]]


def summary(days: int = 7) -> dict:
    since = timezone.now() - timedelta(days=days)
    rows = AccessEvent.objects.filter(created_at__gte=since)
    counts = {k: 0 for k, _ in AccessEvent.Kind.choices}
    for kind in rows.values_list("kind", flat=True):
        counts[kind] = counts.get(kind, 0) + 1
    last_bad = (
        AccessEvent.objects.exclude(kind=AccessEvent.Kind.LOGIN_OK)
        .order_by("-created_at", "-id")
        .first()
    )
    return {
        "days": days,
        "counts": counts,
        "last_problem": (
            {
                "kind": last_bad.kind,
                "at": last_bad.created_at.isoformat(timespec="seconds"),
                "address": last_bad.address,
            }
            if last_bad
            else None
        ),
    }
