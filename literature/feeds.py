"""Journal and arXiv feeds inside the Library (#531, the field watch): the researcher follows
the RSS / Atom feeds of the journals and arXiv categories they skim, new entries land in the
Library's "Feeds" list with the authors, the abstract and the identifier, and one click adds
a paper to the library (and a project) or marks it seen — Zotero's Feeds pane, in the same
place the papers live and with the same one-click Add the citation watch has.

Three dialects are read without a feed library: RSS 2.0 (arXiv's `rss.arxiv.org/rss/<cat>`),
Atom (`rss.arxiv.org/atom/<cat>`, most blogs) and RSS 1.0 / RDF (Nature, Cell and the other
Atypon / Springer journals, which carry `prism:doi` or `dc:identifier`). An entry's DOI or
arXiv id is read from the dedicated elements first, then from the link, then from the text.

Rules: the body is untrusted XML — a DTD or an entity declaration is refused before parsing
and the download stops at MAX_BYTES; the URL passes the same http(s) + public-host guard the
inbox's link titles use (a feed is fetched from the server), and so does every redirect hop; an entry is deduplicated per feed
by its guid and its first-seen stamp never moves; arXiv's replacement announcements
(`announce_type` replace / replace-cross) are skipped — they re-version the guid and flood the
list; a fetch that fails stores its reason on the feed and moves only the fetched stamp; a
conditional request (ETag / Last-Modified) keeps a quiet feed to one small answer.
"""

from __future__ import annotations

import datetime
import email.utils
import html
import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

import httpx
import nh3
from django.db.models import Count, F, Max, Q
from django.utils import timezone

from notes.links import LinkError, check_url

from .models import Feed, FeedItem, Reference
from .services import (
    TIMEOUT,
    USER_AGENT,
    add_reference_by_identifier,
    normalize_arxiv_id,
    normalize_doi,
)

log = logging.getLogger(__name__)

MAX_BYTES = 2 * 1024 * 1024  # cs.CL's daily feed is ~700 KB
MAX_ENTRIES = 500  # per fetch; a first fetch of a big category is bounded
KEEP_ITEMS = 500  # per feed; the oldest entries not in the library are pruned past this
MAX_AUTHORS = 20
MAX_SUMMARY = 2000
STALE_HOURS = 12
MAX_STALE_HOURS = 24 * 365
SWEEP_LIMIT = 50
MAX_CONSECUTIVE_ERRORS = 3
MAX_REDIRECTS = 4
FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/rdf+xml")

DTD_RE = re.compile(rb"<!(?:DOCTYPE|ENTITY)", re.IGNORECASE)
HTML_RE = re.compile(rb"<!DOCTYPE\s+html|<html[\s>]", re.IGNORECASE)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)")
DOI_URL_RE = re.compile(r"doi\.org/(10\.\d{4,9}/[^\s\"'<>?#]+)", re.IGNORECASE)
ARXIV_NEW_RE = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(?:v\d+)?(?![\d.])")
ARXIV_URL_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf)/((?:\d{4}\.\d{4,5})|(?:[a-z-]+(?:\.[A-Z]{2})?/\d{7}))(?:v\d+)?",
    re.IGNORECASE,
)
ARXIV_OAI_RE = re.compile(r"oai:arXiv\.org:((?:\d{4}\.\d{4,5})|(?:[a-z-]+/\d{7}))", re.IGNORECASE)
ARXIV_PREFIX_RE = re.compile(r"^\s*arXiv:\S+\s+Announce Type:\s*\S+\s*(?:Abstract:)?\s*", re.I)
ALT_LINK_RE = re.compile(r"<link\b[^>]{0,600}>", re.IGNORECASE)
ATTR_RE = re.compile(r"""\b(rel|type|href)\s*=\s*["']([^"']{0,500})["']""", re.IGNORECASE)
SKIPPED_ANNOUNCES = {"replace", "replace-cross"}


class FeedError(Exception):
    """A feed that must not or could not be followed; the message is user-readable."""


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})


# --- parsing ------------------------------------------------------------------------------------


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _children(el, *names):
    return [c for c in el if _local(c.tag) in names]


def _clean_text(value: str | None, limit: int = 1000) -> str:
    """Element text as plain text: tags stripped, entities decoded, whitespace collapsed."""
    if not value:
        return ""
    text = nh3.clean(value, tags=set(), attributes={}, link_rel=None)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _text(el, *names, limit: int = 1000) -> str:
    for child in _children(el, *names):
        text = _clean_text(child.text, limit)
        if text:
            return text
    return ""


def _attr(el, name: str) -> str:
    for key, value in el.attrib.items():
        if _local(key) == name:
            return (value or "").strip()
    return ""


def _date(value: str) -> datetime.date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError:
        pass
    try:
        return email.utils.parsedate_to_datetime(value).date()
    except (TypeError, ValueError, IndexError):
        return None


def _strip_doi(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"^(?:info:doi/|doi:|https?://(?:dx\.)?doi\.org/)", "", value, flags=re.I)
    match = DOI_RE.match(value)
    return normalize_doi(match.group(1).rstrip(".,;)")) if match else ""


def _find_doi(item, link: str, raw_text: str) -> str:
    for child in _children(item, "doi"):  # prism:doi
        doi = _strip_doi(child.text or "")
        if doi:
            return doi
    for child in _children(item, "identifier"):  # dc:identifier: "doi:10.…" or bare
        doi = _strip_doi(child.text or "")
        if doi:
            return doi
    match = DOI_URL_RE.search(link or "") or DOI_URL_RE.search(raw_text)
    return normalize_doi(match.group(1).rstrip(".,;)")) if match else ""


def _find_arxiv(link: str, guid: str, raw_text: str) -> str:
    for source, pattern in ((link, ARXIV_URL_RE), (guid, ARXIV_OAI_RE), (guid, ARXIV_URL_RE)):
        match = pattern.search(source or "")
        if match:
            return normalize_arxiv_id(match.group(1))
    match = re.search(r"arXiv:(\S+)", raw_text[:200])
    if match:
        candidate = normalize_arxiv_id(match.group(1).rstrip(".,;"))
        if ARXIV_NEW_RE.fullmatch(candidate) or re.fullmatch(r"[a-z-]+/\d{7}", candidate):
            return candidate
    return ""


def _authors(item) -> list[str]:
    names: list[str] = []
    for child in _children(item, "creator"):  # dc:creator, one per author or "A, B, C"
        text = _clean_text(child.text, 2000)
        if ", " in text:
            names.extend(part.strip() for part in text.split(", "))
        elif text:
            names.append(text)
    for child in _children(item, "author"):  # Atom <author><name>; RSS <author> is an e-mail
        name = _text(child, "name", limit=200) or _clean_text(child.text, 200)
        if name and "@" not in name:
            names.append(name)
    seen: set[str] = set()
    out = []
    for name in names:
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name[:200])
    return out[:MAX_AUTHORS]


def _link(item, kind: str) -> str:
    if kind == "atom":
        alternate = ""
        for child in _children(item, "link"):
            href = _attr(child, "href")
            rel = _attr(child, "rel")
            if href and rel in ("", "alternate"):
                alternate = alternate or href
        return alternate[:500]
    text = _text(item, "link", limit=500)
    if not text and kind == "rdf":
        text = _attr(item, "about")[:500]
    return text


def _entry(item, kind: str) -> dict | None:
    """One feed entry → the FeedItem fields, or None for an entry to skip."""
    announce = _text(item, "announce_type", limit=40).lower()
    if announce in SKIPPED_ANNOUNCES:
        return None
    title = _text(item, "title", limit=1000)
    if not title:
        return None
    link = _link(item, kind)
    guid = _text(item, "guid", "id", limit=500) or _attr(item, "about")[:500] or link or title[:500]
    raw_summary = ""
    for child in _children(item, "description", "summary", "content", "encoded"):
        if child.text and child.text.strip():
            raw_summary = child.text
            break
    summary = ARXIV_PREFIX_RE.sub("", _clean_text(raw_summary, 20000))[:MAX_SUMMARY]
    published = None
    for child in _children(item, "pubDate", "date", "publicationDate", "published", "updated"):
        published = _date(child.text or "")
        if published:
            break
    return {
        "guid": guid,
        "title": title,
        "authors": _authors(item),
        "summary": summary,
        "link": link,
        "doi": _find_doi(item, link, raw_summary or "")[:255],
        "arxiv_id": _find_arxiv(link, guid, raw_summary or "")[:50],
        "published_on": published,
    }


def parse_feed(body: bytes | str) -> dict:
    """{title, site_url, kind, entries: [entry, …]} from an RSS 2.0, Atom or RSS 1.0 body.
    Raises FeedError when the body is not a feed (or carries a DTD / entity declaration)."""
    data = body.encode("utf-8") if isinstance(body, str) else bytes(body)
    if HTML_RE.search(data[:2048]):
        raise FeedError("that address did not answer with a feed")
    if DTD_RE.search(data):
        raise FeedError("the feed carries a document type declaration, which is not read")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise FeedError("that address did not answer with a feed") from exc
    name = _local(root.tag)
    if name == "rss":
        kind = "rss"
        channel = next(iter(_children(root, "channel")), root)
        items = _children(channel, "item")
        title = _text(channel, "title", limit=300)
        site = _text(channel, "link", limit=500)
    elif name == "feed":
        kind = "atom"
        items = _children(root, "entry")
        title = _text(root, "title", limit=300)
        site = ""
        for child in _children(root, "link"):
            if _attr(child, "rel") in ("", "alternate") and _attr(child, "href"):
                site = _attr(child, "href")[:500]
                break
    elif name == "RDF":
        kind = "rdf"
        channel = next(iter(_children(root, "channel")), None)
        items = _children(root, "item")
        title = _text(channel, "title", limit=300) if channel is not None else ""
        site = _text(channel, "link", limit=500) if channel is not None else ""
    else:
        raise FeedError("that address did not answer with a feed")
    entries = []
    for item in items[:MAX_ENTRIES]:
        entry = _entry(item, kind)
        if entry:
            entries.append(entry)
    return {"title": title, "site_url": site, "kind": kind, "entries": entries}


def discover_feed_url(body: bytes, base_url: str) -> str:
    """The feed a web page advertises (`<link rel="alternate" type="application/rss+xml">`),
    or "" — so a journal's home page can be pasted instead of its feed address."""
    head = bytes(body[:200_000]).decode("utf-8", errors="replace")
    for tag in ALT_LINK_RE.findall(head):
        attrs = {k.lower(): v for k, v in ATTR_RE.findall(tag)}
        if "alternate" in attrs.get("rel", "").lower() and (
            attrs.get("type", "").lower() in FEED_TYPES
        ):
            href = html.unescape(attrs.get("href", ""))
            if href:
                return urljoin(base_url, href)[:500]
    return ""


# --- fetching -----------------------------------------------------------------------------------


def _download(url: str, headers: dict, client: httpx.Client) -> tuple[int, dict, bytes]:
    """(status, response headers, body up to MAX_BYTES). Redirects are followed by hand, at
    most MAX_REDIRECTS, and every hop passes the same public-host guard as the typed address
    (a public host answering "302 → http://127.0.0.1/…" must not be fetched). Raises
    httpx.HTTPError when the host did not answer and FeedError when a hop is refused or the
    body is too large."""
    for _ in range(MAX_REDIRECTS + 1):
        with client.stream("GET", url, headers=headers, follow_redirects=False) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location", "")
                if not location:
                    return response.status_code, dict(response.headers), b""
                try:
                    url = check_url(urljoin(url, location))
                except LinkError as exc:
                    raise FeedError(
                        f"the feed redirects to an address not fetched ({exc})"
                    ) from exc
                continue
            if response.status_code != 200:
                return response.status_code, dict(response.headers), b""
            buf = bytearray()
            for chunk in response.iter_bytes():
                buf += chunk
                if len(buf) > MAX_BYTES:
                    raise FeedError("the feed is larger than 2 MB")
            return 200, dict(response.headers), bytes(buf)
    raise FeedError("the feed redirects too many times")


def _store_entry(feed: Feed, entry: dict) -> tuple[FeedItem, bool]:
    """Upsert one entry; the first-seen stamp never moves, changed metadata is taken, a paper
    already in the library is recorded against its reference."""
    defaults = {k: v for k, v in entry.items() if k != "guid"}
    row, created = FeedItem.objects.get_or_create(feed=feed, guid=entry["guid"], defaults=defaults)
    if not created:
        changed = [k for k, v in defaults.items() if getattr(row, k) != v]
        if changed:
            for k in changed:
                setattr(row, k, defaults[k])
            row.save(update_fields=changed + ["updated_at"])
    if row.reference_id is None and (row.doi or row.arxiv_id):
        match = Q(pk__in=[])
        if row.doi:
            match |= Q(doi__iexact=row.doi)
        if row.arxiv_id:
            match |= Q(arxiv_id__iexact=row.arxiv_id)
        own = Reference.objects.filter(match).first()
        if own is not None:
            row.reference = own
            row.save(update_fields=["reference", "updated_at"])
    return row, created


def _prune(feed: Feed) -> int:
    """Keep the newest KEEP_ITEMS entries of a feed; the library's own papers are kept."""
    keep = list(
        feed.items.order_by(F("published_on").desc(nulls_last=True), "pk").values_list(
            "pk", flat=True
        )
    )
    if len(keep) <= KEEP_ITEMS:
        return 0
    tail = feed.items.filter(pk__in=keep[KEEP_ITEMS:], reference__isnull=True)
    deleted, _ = tail.delete()
    return deleted


def fetch_feed(feed: Feed, client: httpx.Client | None = None) -> dict:
    """Fetch one feed and store its entries. Returns {new, seen, unchanged, error}. A fetch
    that fails (offline, a non-200, not a feed) stores the reason on the feed and moves only
    `last_fetched_at`; a 304 counts as unchanged."""
    own = client is None
    client = client or _client()
    now = timezone.now()
    out = {"new": 0, "seen": 0, "unchanged": False, "error": ""}
    headers = {}
    if feed.etag:
        headers["If-None-Match"] = feed.etag
    if feed.last_modified:
        headers["If-Modified-Since"] = feed.last_modified
    try:
        try:
            status, response_headers, body = _download(feed.url, headers, client)
        except httpx.HTTPError as exc:
            raise FeedError(f"the feed did not answer ({exc.__class__.__name__})") from exc
        if status == 304:
            out["unchanged"] = True
            feed.last_fetched_at = feed.last_ok_at = now
            feed.last_error = ""
            feed.save(update_fields=["last_fetched_at", "last_ok_at", "last_error", "updated_at"])
            return out
        if status != 200:
            raise FeedError(f"the feed answered {status}")
        parsed = parse_feed(body)
    except FeedError as exc:
        log.info("feed %s: %s", feed.url, exc)
        out["error"] = str(exc)
        feed.last_fetched_at = now
        feed.last_error = str(exc)[:300]
        feed.save(update_fields=["last_fetched_at", "last_error", "updated_at"])
        return out
    finally:
        if own:
            client.close()
    for entry in parsed["entries"]:
        _, created = _store_entry(feed, entry)
        out["new" if created else "seen"] += 1
    fields = ["last_fetched_at", "last_ok_at", "last_error", "etag", "last_modified", "updated_at"]
    feed.last_fetched_at = feed.last_ok_at = now
    feed.last_error = ""
    lower = {k.lower(): v for k, v in response_headers.items()}
    feed.etag = (lower.get("etag") or "")[:200]
    feed.last_modified = (lower.get("last-modified") or "")[:100]
    if not feed.title and parsed["title"]:
        feed.title = parsed["title"][:300]
        fields.append("title")
    if not feed.site_url and parsed["site_url"]:
        feed.site_url = parsed["site_url"][:500]
        fields.append("site_url")
    feed.save(update_fields=fields)
    _prune(feed)
    return out


def refresh(feeds, client: httpx.Client | None = None) -> dict:
    """Fetch these feeds in turn. Returns {feeds, new, seen, unchanged, errors, stopped}; the
    breaker stops after MAX_CONSECUTIVE_ERRORS feeds in a row that did not answer at all."""
    own = client is None
    client = client or _client()
    out = {"feeds": 0, "new": 0, "seen": 0, "unchanged": 0, "errors": 0, "stopped": False}
    streak = 0
    try:
        for feed in feeds:
            result = fetch_feed(feed, client)
            out["feeds"] += 1
            out["new"] += result["new"]
            out["seen"] += result["seen"]
            out["unchanged"] += int(result["unchanged"])
            if result["error"]:
                out["errors"] += 1
                streak = streak + 1 if "did not answer" in result["error"] else 0
                if streak >= MAX_CONSECUTIVE_ERRORS:
                    out["stopped"] = True
                    break
            else:
                streak = 0
    finally:
        if own:
            client.close()
    return out


def stale_feeds(hours: int = STALE_HOURS, limit: int = SWEEP_LIMIT):
    """Feeds never fetched, then the oldest fetches (older than `hours`)."""
    cutoff = timezone.now() - datetime.timedelta(hours=max(1, min(int(hours), MAX_STALE_HOURS)))
    qs = Feed.objects.filter(last_fetched_at__isnull=True) | Feed.objects.filter(
        last_fetched_at__lt=cutoff
    )
    return list(
        qs.order_by(F("last_fetched_at").asc(nulls_first=True), "pk")[
            : max(1, min(int(limit), 500))
        ]
    )


def refresh_stale(hours: int = STALE_HOURS, limit: int = SWEEP_LIMIT) -> dict:
    """The sweep: refresh the stale feeds (bounded). Safe to call every hour — once every feed
    was fetched within `hours` it asks nothing."""
    feeds = stale_feeds(hours, limit)
    if not feeds:
        return {"feeds": 0, "new": 0, "seen": 0, "unchanged": 0, "errors": 0, "stopped": False}
    return refresh(feeds)


# --- following ----------------------------------------------------------------------------------


def add_feed(url: str, project=None, title: str = "", client: httpx.Client | None = None):
    """Follow a feed: validate the address, fetch it once (a web page advertising a feed is
    followed to that feed), store it with its entries. Returns (feed, created). Raises
    FeedError when the address is refused or does not answer with a feed."""
    try:
        url = check_url(url)
    except LinkError as exc:
        raise FeedError(str(exc)) from exc
    existing = Feed.objects.filter(url=url).first()
    if existing is not None:
        return existing, False
    own = client is None
    client = client or _client()
    try:
        try:
            status, headers, body = _download(url, {}, client)
        except httpx.HTTPError as exc:
            raise FeedError(f"the address did not answer ({exc.__class__.__name__})") from exc
        if status != 200:
            raise FeedError(f"the address answered {status}")
        try:
            parse_feed(body)
        except FeedError:
            content_type = {k.lower(): v for k, v in headers.items()}.get("content-type", "")
            found = discover_feed_url(body, url) if "html" in content_type.lower() else ""
            if not found:
                raise
            try:
                url = check_url(found)
            except LinkError as exc:
                raise FeedError(str(exc)) from exc
            existing = Feed.objects.filter(url=url).first()
            if existing is not None:
                return existing, False
        top = Feed.objects.aggregate(m=Max("position"))["m"] or 0
        feed = Feed.objects.create(url=url, title=title[:300], project=project, position=top + 1)
        result = fetch_feed(feed, client)
        if result["error"]:
            feed.delete()
            raise FeedError(result["error"])
        return feed, True
    finally:
        if own:
            client.close()


def status() -> dict:
    newest = (
        Feed.objects.exclude(last_fetched_at__isnull=True)
        .order_by("-last_fetched_at")
        .values_list("last_fetched_at", flat=True)
        .first()
    )
    return {
        "feeds": Feed.objects.count(),
        "new": open_items().count(),
        "dismissed": FeedItem.objects.filter(dismissed_at__isnull=False).count(),
        "errors": Feed.objects.exclude(last_error="").count(),
        "last_fetched_at": newest,
    }


def open_items(qs=None):
    """Entries that are news: not dismissed, not (yet) in the library."""
    qs = FeedItem.objects.all() if qs is None else qs
    return qs.filter(dismissed_at__isnull=True, reference__isnull=True)


def feeds_with_counts():
    """Every feed with `new_count` (open entries) and `item_count`, in rail order."""
    return Feed.objects.select_related("project").annotate(
        new_count=Count(
            "items",
            filter=Q(items__dismissed_at__isnull=True, items__reference__isnull=True),
        ),
        item_count=Count("items"),
    )


def feed_row(feed: Feed) -> dict:
    return {
        "id": feed.pk,
        "url": feed.url,
        "title": feed.title or feed.url,
        "site_url": feed.site_url,
        "project": feed.project.slug if feed.project_id else None,
        "position": feed.position,
        "new": getattr(feed, "new_count", None),
        "items": getattr(feed, "item_count", None),
        "last_fetched_at": feed.last_fetched_at,
        "last_ok_at": feed.last_ok_at,
        "last_error": feed.last_error,
    }


def _row(item: FeedItem) -> dict:
    url = item.link
    if not url and item.doi:
        url = f"https://doi.org/{item.doi}"
    if not url and item.arxiv_id:
        url = f"https://arxiv.org/abs/{item.arxiv_id}"
    return {
        "id": item.pk,
        "feed": {"id": item.feed_id, "title": item.feed.title or item.feed.url},
        "guid": item.guid,
        "title": item.title,
        "authors": item.authors,
        "summary": item.summary,
        "link": item.link,
        "doi": item.doi,
        "arxiv_id": item.arxiv_id,
        "published_on": item.published_on.isoformat() if item.published_on else None,
        "first_seen_at": item.created_at,
        "dismissed_at": item.dismissed_at,
        "in_library": item.reference_id,
        "addable": bool(item.doi or item.arxiv_id) and item.reference_id is None,
        "url": url,
    }


def items(
    feed_id: int | None = None,
    project: str = "",
    dismissed: bool = False,
    q: str = "",
    limit: int = 100,
) -> dict:
    """The list: entries not in the library, open (default) or dismissed, newest first;
    narrowed to one feed, to the feeds of one project, or by a word in the title / abstract.
    Across feeds the same paper (an arXiv cross-list, a journal's two feeds) is shown once."""
    qs = FeedItem.objects.filter(reference__isnull=True).select_related("feed")
    qs = (
        qs.filter(dismissed_at__isnull=False) if dismissed else qs.filter(dismissed_at__isnull=True)
    )
    if feed_id:
        qs = qs.filter(feed_id=feed_id)
    if project:
        qs = qs.filter(feed__project__slug=project)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q))
    qs = qs.order_by(F("published_on").desc(nulls_last=True), "pk")  # undated entries last
    limit = max(1, min(int(limit), 500))
    count = qs.count()
    rows: list[dict] = []
    seen: set[str] = set()
    dropped = 0
    for item in qs[: limit + 100]:
        key = item.doi or item.arxiv_id or f"{item.feed_id}:{item.guid}"
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        rows.append(_row(item))
        if len(rows) >= limit:
            break
    return {"count": max(count - dropped, len(rows)), "results": rows}


def dismiss(ids: list[int], undo: bool = False) -> int:
    """Mark entries seen (or put them back). Returns how many rows changed."""
    now = timezone.now()
    n = 0
    for row in FeedItem.objects.filter(pk__in=ids):
        target = None if undo else now
        if (row.dismissed_at is None) != (target is None):
            row.dismissed_at = target
            row.save(update_fields=["dismissed_at", "updated_at"])
            n += 1
    return n


def add_item(item: FeedItem, project=None) -> tuple[Reference, bool]:
    """Add an entry's paper to the library by its DOI or arXiv id, link it to `project` (or
    the feed's project) and record the entry against the reference. Raises FeedError when the
    entry carries no identifier and MetadataError when the identifier does not resolve."""
    identifier = item.doi or item.arxiv_id
    if not identifier:
        raise FeedError("this entry carries no DOI or arXiv id — add it by hand")
    reference, created = add_reference_by_identifier(identifier)
    item.reference = reference
    item.save(update_fields=["reference", "updated_at"])
    project = project or item.feed.project
    if project is not None:
        from .models import ProjectReference

        ProjectReference.objects.get_or_create(project=project, reference=reference)
    return reference, created


def link_reference(reference: Reference) -> int:
    """A paper that just joined the library: the feed entries that *are* this paper stop being
    news (post_save hook). Returns how many rows were linked."""
    match = Q(pk__in=[])
    if reference.doi:
        match |= Q(doi__iexact=normalize_doi(reference.doi))
    if reference.arxiv_id:
        match |= Q(arxiv_id__iexact=normalize_arxiv_id(reference.arxiv_id))
    n = 0
    for row in FeedItem.objects.filter(match, reference__isnull=True):
        row.reference = reference
        row.save(update_fields=["reference", "updated_at"])
        n += 1
    return n
