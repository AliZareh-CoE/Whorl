"""Letting another app embed Atlas (#539, owner ask: "add the whole project to OpenManus as a tab").

Atlas answers every page with ``X-Frame-Options: DENY`` — nothing may put it in a frame. That is
the right default for a tool that holds your research, and it is exactly what stops a host app
(OpenManus, a lab portal, a personal dashboard) from showing Atlas in a tab. ``ATLAS_FRAME_ANCESTORS``
names the origins that may: when it is set, the ``DENY`` header is dropped and a
``Content-Security-Policy: frame-ancestors`` header lists Atlas itself plus those origins, which is
the modern header browsers consult first and the only one that can name a specific origin. An
empty setting (the default) changes nothing.

This module is imported by ``config/settings/base.py`` and must not import Django.
"""

from urllib.parse import urlsplit

MAX_ANCESTORS = 20


def parse_ancestors(raw: str | None) -> list[str]:
    """``"http://localhost:3000, https://lab.example.org"`` → ``["http://localhost:3000", …]``.

    Only whole origins count — ``scheme://host[:port]`` over http or https. A value with a path,
    query, credentials, a wildcard or another scheme is dropped, not guessed at (a wrong origin
    in a ``frame-ancestors`` list is a silent hole). Lower-cased, de-duplicated, order kept.
    """
    if not raw:
        return []
    out: list[str] = []
    for piece in str(raw).replace(",", " ").split():
        origin = _origin(piece)
        if origin and origin not in out:
            out.append(origin)
    return out[:MAX_ANCESTORS]


def _origin(piece: str) -> str | None:
    text = piece.strip().rstrip("/")
    if not text or "*" in text or len(text) > 253:
        return None
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    if parts.username or parts.password or parts.path or parts.query or parts.fragment:
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    host = parts.hostname.lower()
    if ":" in host:  # IPv6 literal keeps its brackets in the header
        host = f"[{host}]"
    return f"{parts.scheme}://{host}" + (f":{port}" if port else "")


def policy(ancestors: list[str]) -> str:
    """The header value: Atlas may always frame itself, then the listed origins."""
    return "frame-ancestors 'self' " + " ".join(ancestors)


class FrameAncestorsMiddleware:
    """After ``XFrameOptionsMiddleware`` has spoken, replace its DENY with a frame-ancestors list.

    Listed *before* the clickjacking middleware in ``MIDDLEWARE`` so it runs after it on the way
    out. Reads the setting per request (tests override it). A response marked
    ``xframe_options_exempt`` is left exactly as the view made it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        from django.conf import settings

        ancestors = getattr(settings, "ATLAS_FRAME_ANCESTORS", None) or []
        if not ancestors or getattr(response, "xframe_options_exempt", False):
            return response
        if "Content-Security-Policy" in response.headers:
            return response
        response.headers.pop("X-Frame-Options", None)
        response.headers["Content-Security-Policy"] = policy(list(ancestors))
        return response
