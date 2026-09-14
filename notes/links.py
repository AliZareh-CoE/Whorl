"""#499: link captures know their page.

A capture that is a URL (or carries one) is worth more with the page's title next to it —
"https://arxiv.org/abs/2406.01234" says nothing, "Attention Is Not Enough — arXiv" does. The
fetch is small and careful: http(s) only, no private or loopback hosts, four seconds, at most
256 KB read, redirects followed a few times; the title comes from ``<title>`` (or ``og:title``
when it is more specific). Failures are recorded (``link_fetched_at``) so the inbox does not
retry on every load; ``enrich_capture(capture, force=True)`` tries again on demand.
"""

from __future__ import annotations

import html
import ipaddress
import re
import socket
from urllib.parse import urlsplit

import httpx
from django.utils import timezone

TIMEOUT = httpx.Timeout(4.0)
MAX_BYTES = 256 * 1024
MAX_REDIRECTS = 4
USER_AGENT = "Atlas (research project manager; link titles)"
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
OG_RE = re.compile(
    r"""<meta[^>]+(?:property|name)=["']og:title["'][^>]*content=["']([^"']{1,300})["']""",
    re.IGNORECASE,
)
OG_RE_REVERSED = re.compile(
    r"""<meta[^>]+content=["']([^"']{1,300})["'][^>]*(?:property|name)=["']og:title["']""",
    re.IGNORECASE,
)


class LinkError(Exception):
    """A link that must not or could not be fetched; the message is user-readable."""


def _host_is_private(host: str) -> bool:
    if not host or "." not in host and host != "localhost" and ":" not in host:
        return True  # bare names resolve to the LAN
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return True  # unresolvable: nothing to fetch anyway
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return True
        if not ip.is_global:
            return True
    return False


def check_url(url: str) -> str:
    """The URL as it will be fetched, or LinkError."""
    parts = urlsplit((url or "").strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise LinkError("only http(s) links are fetched")
    if _host_is_private(parts.hostname):
        raise LinkError("that host is private or unresolvable")
    return parts.geturl()


def _clean(title: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(title)).strip()[:300]


def title_from_html(body: str) -> str:
    """The page title: og:title when present and longer than a bare site name, else <title>."""
    head = body[:MAX_BYTES]
    plain = TITLE_RE.search(head)
    og = OG_RE.search(head) or OG_RE_REVERSED.search(head)
    candidates = [_clean(m.group(1)) for m in (og, plain) if m]
    candidates = [c for c in candidates if c]
    return candidates[0] if candidates else ""


def fetch_link_title(url: str, client: httpx.Client | None = None) -> str:
    """The title of the page at `url`, "" when the page has none. Raises LinkError."""
    target = check_url(url)
    own = client is None
    client = client or httpx.Client(
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
    )
    try:
        with client.stream("GET", target) as response:
            if response.status_code >= 400:
                raise LinkError(f"the page answered {response.status_code}")
            kind = response.headers.get("content-type", "")
            if "html" not in kind and "xml" not in kind and kind:
                return ""  # a PDF or an image: nothing to read a title from
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= MAX_BYTES:
                    break
            body = b"".join(chunks)[:MAX_BYTES].decode(response.encoding or "utf-8", "replace")
    except LinkError:
        raise
    except httpx.HTTPError as exc:
        raise LinkError(f"could not fetch the page ({exc.__class__.__name__})") from exc
    finally:
        if own:
            client.close()
    return title_from_html(body)


def site_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def enrich_capture(capture, *, force: bool = False, client: httpx.Client | None = None) -> dict:
    """Look the capture's link up once and remember the title; {url, site, title, error}."""
    from notes.capture import detect

    url = detect(capture.text)["url"]
    out = {
        "url": url,
        "site": site_of(url) if url else "",
        "title": capture.link_title,
        "error": "",
    }
    if not url:
        out["error"] = "no link in the capture"
        return out
    if capture.link_fetched_at and not force:
        return out
    try:
        title = fetch_link_title(url, client=client)
    except LinkError as exc:
        title, out["error"] = "", str(exc)
    capture.link_title = title
    capture.link_fetched_at = timezone.now()
    capture.save(update_fields=["link_title", "link_fetched_at", "updated_at"])
    out["title"] = title
    return out
