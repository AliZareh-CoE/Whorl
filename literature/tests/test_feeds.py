"""#531: journal and arXiv feeds inside the Library."""

import datetime
import json
from pathlib import Path

import httpx
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from literature import feeds
from literature.models import Feed, FeedItem, ProjectReference, Reference
from literature.tests.factories import ReferenceFactory
from projects.tests.factories import ProjectFactory

RSS_ARXIV = b"""<?xml version='1.0' encoding='UTF-8'?>
<rss xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">
  <channel>
    <title>cs.CL updates on arXiv.org</title>
    <link>http://rss.arxiv.org/rss/cs.CL</link>
    <item>
      <title>Token Merging for  Multilingual Speech Recognition</title>
      <link>https://arxiv.org/abs/2609.13151</link>
      <description>arXiv:2609.13151v1 Announce Type: new
Abstract: Leading multilingual &amp; low-resource models &lt;b&gt;are&lt;/b&gt; expensive.</description>
      <guid isPermaLink="false">oai:arXiv.org:2609.13151v1</guid>
      <pubDate>Tue, 15 Sep 2026 00:00:00 -0400</pubDate>
      <arxiv:announce_type>new</arxiv:announce_type>
      <dc:creator>Dylan Holyoak, Mei Chen</dc:creator>
    </item>
    <item>
      <title>A replaced paper</title>
      <link>https://arxiv.org/abs/2501.00001</link>
      <description>arXiv:2501.00001v3 Announce Type: replace
Abstract: Nothing new.</description>
      <guid isPermaLink="false">oai:arXiv.org:2501.00001v3</guid>
      <arxiv:announce_type>replace</arxiv:announce_type>
      <dc:creator>Someone</dc:creator>
    </item>
    <item>
      <title>A cross-list</title>
      <link>https://arxiv.org/abs/2609.13999</link>
      <description>arXiv:2609.13999v1 Announce Type: cross
Abstract: Listed twice.</description>
      <guid isPermaLink="false">oai:arXiv.org:2609.13999v1</guid>
      <arxiv:announce_type>cross</arxiv:announce_type>
    </item>
  </channel>
</rss>"""

ATOM_ARXIV = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>q-bio.NC updates on arXiv.org</title>
  <link href="http://rss.arxiv.org/atom/q-bio.NC" rel="self"/>
  <link href="https://arxiv.org/list/q-bio.NC/new" rel="alternate"/>
  <entry>
    <id>oai:arXiv.org:2609.13219v1</id>
    <title>Planning as Dynamics Relaxation</title>
    <updated>2026-09-15T04:02:32+00:00</updated>
    <link href="https://arxiv.org/abs/2609.13219" rel="alternate" type="text/html"/>
    <link href="https://arxiv.org/pdf/2609.13219" rel="related" type="application/pdf"/>
    <summary>arXiv:2609.13219v1 Announce Type: new
Abstract: Hippocampal networks relax.</summary>
    <author><name>Yuhang He</name></author>
    <author><name>Si Wu</name></author>
    <arxiv:announce_type>new</arxiv:announce_type>
  </entry>
</feed>"""

RDF_NATURE = b"""<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns="http://purl.org/rss/1.0/">
  <channel rdf:about="http://feeds.nature.com/nathumbehav/rss/current">
    <title>Nature Human Behaviour</title>
    <link>https://www.nature.com/nathumbehav</link>
  </channel>
  <item rdf:about="https://www.nature.com/articles/s41562-026-02594-2">
    <title><![CDATA[Staying in academia]]></title>
    <link>https://www.nature.com/articles/s41562-026-02594-2</link>
    <content:encoded><![CDATA[<p>Nature Human Behaviour, Published online: 15 September 2026; <a href="https://www.nature.com/articles/s41562-026-02594-2">doi:10.1038/s41562-026-02594-2</a></p>Returning after leave.]]></content:encoded>
    <dc:creator>Theresa Mercer</dc:creator>
    <dc:creator>Ada Bell</dc:creator>
    <dc:identifier>doi:10.1038/s41562-026-02594-2</dc:identifier>
    <dc:date>2026-09-15</dc:date>
    <prism:doi>10.1038/S41562-026-02594-2</prism:doi>
  </item>
</rdf:RDF>"""

RDF_CELL = b"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:prism="http://prismstandard.org/namespaces/1.2/basic/">
  <channel rdf:about="https://www.cell.com/tics"><title>Trends in Cognitive Sciences</title></channel>
  <item rdf:about="https://www.cell.com/trends/cognitive-sciences/fulltext/S1364-6613(26)00205-6?rss=yes">
    <title>Language structure as training</title>
    <description>Language plays a central role.</description>
    <dc:creator>Velia Cardin</dc:creator>
    <dc:identifier>10.1016/j.tics.2026.08.006</dc:identifier>
    <prism:publicationDate>2026-09-14</prism:publicationDate>
  </item>
</rdf:RDF>"""

HTML_PAGE = b"""<!doctype html><html><head><title>Journal</title>
<link rel="stylesheet" href="/a.css"><link rel="alternate" type="application/rss+xml" title="RSS" href="/feed.rss">
</head><body>Welcome</body></html>"""


def server(routes: dict, log=None, status=200):
    """A mock web: `routes` {url: body-bytes | (status, headers, body)}."""

    def handler(request):
        if log is not None:
            log.append(request)
        hit = routes.get(str(request.url))
        if hit is None:
            return httpx.Response(404, content=b"nope")
        if isinstance(hit, tuple):
            code, headers, body = hit
            return httpx.Response(code, headers=headers, content=body)
        if status != 200:
            return httpx.Response(status, content=b"")
        return httpx.Response(
            200, headers={"Content-Type": "application/rss+xml", "ETag": '"e1"'}, content=hit
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def public_hosts(monkeypatch):
    """The sandbox resolves no names: treat every non-loopback host as public."""
    import notes.links

    monkeypatch.setattr(
        notes.links,
        "_host_is_private",
        lambda host: host in ("localhost", "127.0.0.1") or host.startswith("127."),
    )


def down():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestParse:
    def test_rss_arxiv(self):
        out = feeds.parse_feed(RSS_ARXIV)
        assert out["kind"] == "rss" and out["title"] == "cs.CL updates on arXiv.org"
        assert out["site_url"] == "http://rss.arxiv.org/rss/cs.CL"
        titles = [e["title"] for e in out["entries"]]
        assert titles == ["Token Merging for Multilingual Speech Recognition", "A cross-list"]
        e = out["entries"][0]
        assert e["guid"] == "oai:arXiv.org:2609.13151v1" and e["arxiv_id"] == "2609.13151"
        assert e["doi"] == "" and e["link"] == "https://arxiv.org/abs/2609.13151"
        assert e["authors"] == ["Dylan Holyoak", "Mei Chen"]
        assert e["summary"] == "Leading multilingual & low-resource models are expensive."
        assert e["published_on"] == datetime.date(2026, 9, 15)

    def test_atom_arxiv(self):
        out = feeds.parse_feed(ATOM_ARXIV)
        assert out["kind"] == "atom" and out["site_url"] == "https://arxiv.org/list/q-bio.NC/new"
        (e,) = out["entries"]
        assert e["link"] == "https://arxiv.org/abs/2609.13219" and e["arxiv_id"] == "2609.13219"
        assert (
            e["authors"] == ["Yuhang He", "Si Wu"] and e["summary"] == "Hippocampal networks relax."
        )
        assert e["published_on"] == datetime.date(2026, 9, 15)

    def test_rdf_nature_and_cell(self):
        out = feeds.parse_feed(RDF_NATURE)
        assert out["kind"] == "rdf" and out["title"] == "Nature Human Behaviour"
        (e,) = out["entries"]
        assert e["doi"] == "10.1038/s41562-026-02594-2"  # prism:doi first, lower-cased
        assert (
            e["authors"] == ["Theresa Mercer", "Ada Bell"] and e["title"] == "Staying in academia"
        )
        assert e["summary"].startswith("Nature Human Behaviour, Published online") and (
            "<" not in e["summary"]
        )
        assert e["published_on"] == datetime.date(2026, 9, 15)
        (c,) = feeds.parse_feed(RDF_CELL)["entries"]
        assert c["doi"] == "10.1016/j.tics.2026.08.006" and c["guid"].startswith(
            "https://www.cell.com/"
        )
        assert c["published_on"] == datetime.date(2026, 9, 14) and c["arxiv_id"] == ""

    def test_refusals(self):
        with pytest.raises(feeds.FeedError):
            feeds.parse_feed(b'<!DOCTYPE rss [<!ENTITY a "b">]><rss><channel/></rss>')
        with pytest.raises(feeds.FeedError):
            feeds.parse_feed(HTML_PAGE)
        with pytest.raises(feeds.FeedError):
            feeds.parse_feed(b"<html><body>not xml at all")
        with pytest.raises(feeds.FeedError):
            feeds.parse_feed(b"<root><item><title>x</title></item></root>")

    def test_discover_feed_url(self):
        assert (
            feeds.discover_feed_url(HTML_PAGE, "https://journal.example/home")
            == "https://journal.example/feed.rss"
        )
        assert feeds.discover_feed_url(b"<html><head></head></html>", "https://x.example") == ""
        assert (
            feeds.discover_feed_url(
                b'<link rel="alternate" type="text/html" href="/x">', "https://x.example"
            )
            == ""
        )


@pytest.mark.django_db
class TestFetch:
    def test_fetch_stores_links_and_a_second_fetch_is_conditional(self):
        own = ReferenceFactory(arxiv_id="2609.13219", doi=None)
        feed = Feed.objects.create(url="https://rss.arxiv.org/atom/q-bio.NC")
        log = []
        routes = {
            feed.url: (
                200,
                {"ETag": '"abc"', "Last-Modified": "Tue, 15 Sep 2026 04:00:00 GMT"},
                ATOM_ARXIV,
            )
        }
        out = feeds.fetch_feed(feed, server(routes, log))
        assert out == {"new": 1, "seen": 0, "unchanged": False, "error": "", "muted": 0}
        feed.refresh_from_db()
        assert feed.title == "q-bio.NC updates on arXiv.org" and feed.etag == '"abc"'
        assert feed.site_url == "https://arxiv.org/list/q-bio.NC/new"
        assert feed.last_ok_at and feed.last_fetched_at and feed.last_error == ""
        item = feed.items.get()
        assert item.reference_id == own.pk  # already in the library: not news
        first_seen = item.created_at
        # second fetch: conditional headers, 304 → unchanged, stamps move, nothing else
        routes[feed.url] = (304, {}, b"")
        out = feeds.fetch_feed(feed, server(routes, log))
        assert out["unchanged"] is True and out["new"] == 0
        assert log[-1].headers["If-None-Match"] == '"abc"'
        assert log[-1].headers["If-Modified-Since"] == "Tue, 15 Sep 2026 04:00:00 GMT"
        assert feed.items.get().created_at == first_seen
        # a changed title is taken, the first-seen stamp stays
        routes[feed.url] = (200, {}, ATOM_ARXIV.replace(b"Planning as", b"Planning As"))
        out = feeds.fetch_feed(feed, server(routes, log))
        assert out["seen"] == 1 and out["new"] == 0
        item.refresh_from_db()
        assert item.title == "Planning As Dynamics Relaxation" and item.created_at == first_seen

    def test_failures_store_the_reason_and_keep_the_entries(self, monkeypatch):
        feed = Feed.objects.create(url="https://rss.arxiv.org/rss/cs.CL")
        assert feeds.fetch_feed(feed, server({feed.url: RSS_ARXIV}))["new"] == 2
        feed.refresh_from_db()
        ok_at = feed.last_ok_at
        out = feeds.fetch_feed(feed, server({feed.url: (503, {}, b"")}))
        assert out["error"] == "the feed answered 503"
        feed.refresh_from_db()
        assert feed.last_error == "the feed answered 503" and feed.last_ok_at == ok_at
        assert feed.last_fetched_at > ok_at and feed.items.count() == 2
        out = feeds.fetch_feed(feed, down())
        assert "did not answer" in out["error"]
        out = feeds.fetch_feed(feed, server({feed.url: HTML_PAGE}))
        assert out["error"] == "that address did not answer with a feed"
        monkeypatch.setattr(feeds, "MAX_BYTES", 100)
        out = feeds.fetch_feed(feed, server({feed.url: RSS_ARXIV}))
        assert out["error"] == "the feed is larger than 2 MB"
        feed.refresh_from_db()
        assert feed.items.count() == 2 and feed.last_error.startswith("the feed is larger")
        # a good fetch clears the error
        monkeypatch.setattr(feeds, "MAX_BYTES", 2_000_000)
        assert feeds.fetch_feed(feed, server({feed.url: RSS_ARXIV}))["error"] == ""
        feed.refresh_from_db()
        assert feed.last_error == "" and feed.last_ok_at > ok_at

    def test_redirects_are_followed_only_to_public_hosts(self, public_hosts):
        feed = Feed.objects.create(url="https://a.example/rss")
        assert feeds.fetch_feed(feed, server({feed.url: RSS_ARXIV}))["new"] == 2
        # a hop to a public host answering the feed: followed, entries stored
        routes = {
            feed.url: (301, {"Location": "https://b.example/feed.xml"}, b""),
            "https://b.example/feed.xml": RSS_ARXIV.replace(b"2609.13999", b"2609.14000"),
        }
        out = feeds.fetch_feed(feed, server(routes))
        assert out["error"] == "" and out["new"] == 1 and out["seen"] == 1
        # a hop to a private address: refused, the reason stored, the entries kept
        routes[feed.url] = (302, {"Location": "http://127.0.0.1:8000/x"}, b"")
        out = feeds.fetch_feed(feed, server(routes))
        assert out["error"].startswith("the feed redirects to an address not fetched")
        feed.refresh_from_db()
        assert feed.items.count() == 3 and feed.last_error.startswith("the feed redirects")
        # a relative Location resolves against the feed's address; a loop stops at the cap
        routes[feed.url] = (302, {"Location": "/feed.xml"}, b"")
        routes["https://a.example/feed.xml"] = (302, {"Location": "https://a.example/rss"}, b"")
        assert feeds.fetch_feed(feed, server(routes))["error"] == (
            "the feed redirects too many times"
        )
        routes["https://a.example/feed.xml"] = RSS_ARXIV
        assert feeds.fetch_feed(feed, server(routes))["error"] == ""

    def test_prune_keeps_the_newest_and_the_library_own(self, monkeypatch):
        monkeypatch.setattr(feeds, "KEEP_ITEMS", 2)
        feed = Feed.objects.create(url="https://f.example/rss")
        own = ReferenceFactory(doi="10.1/own")
        for i, day in enumerate((1, 2, 3, 4)):
            FeedItem.objects.create(
                feed=feed,
                guid=f"g{i}",
                title=f"t{i}",
                published_on=datetime.date(2026, 1, day),
                doi="10.1/own" if i == 0 else "",
                reference=own if i == 0 else None,
            )
        assert feeds._prune(feed) == 1  # g1 goes; g0 is the library's own and stays
        assert set(feed.items.values_list("guid", flat=True)) == {"g0", "g2", "g3"}

    def test_refresh_breaker_and_stale_order(self, monkeypatch):
        now = timezone.now()
        a = Feed.objects.create(url="https://a.example/rss", last_fetched_at=now)
        b = Feed.objects.create(url="https://b.example/rss")
        c = Feed.objects.create(
            url="https://c.example/rss", last_fetched_at=now - datetime.timedelta(days=2)
        )
        assert [f.pk for f in feeds.stale_feeds()] == [b.pk, c.pk]
        assert [f.pk for f in feeds.stale_feeds(hours=1, limit=1)] == [b.pk]
        out = feeds.refresh([a, b, c, a], down())
        assert out["errors"] == 3 and out["stopped"] is True and out["feeds"] == 3
        out = feeds.refresh([a, b], server({a.url: RSS_ARXIV, b.url: (500, {}, b"")}))
        assert out == {
            "feeds": 2,
            "new": 2,
            "seen": 0,
            "unchanged": 0,
            "errors": 1,
            "stopped": False,
            "muted": 0,
        }
        monkeypatch.setattr(feeds, "_client", lambda: server({}))
        Feed.objects.filter(pk__in=[b.pk, c.pk]).delete()
        assert feeds.refresh_stale()["feeds"] == 0  # a is fresh: nothing asked

    def test_add_feed(self, public_hosts):
        project = ProjectFactory()
        with pytest.raises(feeds.FeedError):
            feeds.add_feed("http://127.0.0.1:8000/x", client=server({}))
        with pytest.raises(feeds.FeedError):
            feeds.add_feed("ftp://journal.example/feed", client=server({}))
        with pytest.raises(feeds.FeedError, match="did not answer with a feed"):
            feeds.add_feed(
                "https://journal.example/plain",
                client=server(
                    {"https://journal.example/plain": (200, {"Content-Type": "text/plain"}, b"hi")}
                ),
            )
        assert Feed.objects.count() == 0  # a refused address is not persisted
        routes = {
            "https://journal.example/home": (200, {"Content-Type": "text/html"}, HTML_PAGE),
            "https://journal.example/feed.rss": RDF_NATURE,
        }
        feed, created = feeds.add_feed(
            "https://journal.example/home", project=project, title="NHB", client=server(routes)
        )
        assert created and feed.url == "https://journal.example/feed.rss"  # discovered
        assert feed.title == "NHB" and feed.project == project and feed.position == 1
        assert feed.items.count() == 1
        again, created = feeds.add_feed("https://journal.example/feed.rss", client=server(routes))
        assert not created and again.pk == feed.pk
        with pytest.raises(feeds.FeedError, match="answered 404"):
            feeds.add_feed("https://journal.example/missing", client=server(routes))


@pytest.mark.django_db
class TestList:
    def _seed(self):
        project = ProjectFactory()
        a = Feed.objects.create(url="https://a.example/rss", title="A", project=project)
        b = Feed.objects.create(url="https://b.example/rss", title="B")
        rows = [
            FeedItem.objects.create(
                feed=a,
                guid="1",
                title="Alpha load",
                arxiv_id="2609.00001",
                published_on=datetime.date(2026, 9, 3),
                summary="about attention",
            ),
            FeedItem.objects.create(
                feed=b,
                guid="1",
                title="Alpha load (cross-list)",
                arxiv_id="2609.00001",
                published_on=datetime.date(2026, 9, 3),
            ),
            FeedItem.objects.create(
                feed=b,
                guid="2",
                title="Beta",
                doi="10.1/beta",
                published_on=datetime.date(2026, 9, 2),
            ),
            FeedItem.objects.create(
                feed=b, guid="3", title="Gamma no id", published_on=datetime.date(2026, 9, 1)
            ),
        ]
        return project, a, b, rows

    def test_items_filters_dedupe_and_status(self):
        project, a, b, rows = self._seed()
        out = feeds.items()
        assert [r["title"] for r in out["results"]] == ["Alpha load", "Beta", "Gamma no id"]
        assert out["count"] == 3  # the cross-list is the same paper
        assert out["results"][0]["feed"] == {"id": a.pk, "title": "A"}
        assert out["results"][0]["addable"] and not out["results"][2]["addable"]
        assert out["results"][0]["url"] == "https://arxiv.org/abs/2609.00001"
        assert out["results"][1]["url"] == "https://doi.org/10.1/beta"
        assert [r["title"] for r in feeds.items(feed_id=b.pk)["results"]] == [
            "Alpha load (cross-list)",
            "Beta",
            "Gamma no id",
        ]
        assert [r["title"] for r in feeds.items(project=project.slug)["results"]] == ["Alpha load"]
        assert [r["title"] for r in feeds.items(q="attention")["results"]] == ["Alpha load"]
        assert feeds.items(limit=1)["results"][0]["title"] == "Alpha load"
        assert feeds.dismiss([rows[2].pk]) == 1 and feeds.dismiss([rows[2].pk]) == 0
        assert [r["title"] for r in feeds.items(dismissed=True)["results"]] == ["Beta"]
        assert feeds.status() == {
            "feeds": 2,
            "new": 3,
            "dismissed": 1,
            "muted": 0,
            "errors": 0,
            "last_fetched_at": None,
        }
        assert feeds.dismiss([rows[2].pk], undo=True) == 1
        counts = {f.title: (f.new_count, f.item_count) for f in feeds.feeds_with_counts()}
        assert counts == {"A": (1, 1), "B": (3, 3)}
        row = feeds.feed_row(feeds.feeds_with_counts().get(pk=a.pk))
        assert row["new"] == 1 and row["project"] == project.slug and row["title"] == "A"

    def test_add_item_and_the_save_hook(self, monkeypatch):
        project, a, b, rows = self._seed()
        other = ProjectFactory()

        def fake_add(identifier):
            ref, created = Reference.objects.get_or_create(
                arxiv_id=identifier if "/" not in identifier else "",
                doi=identifier if "/" in identifier else None,
                defaults={"bibtex_key": f"k{identifier[-4:]}", "title": identifier},
            )
            return ref, created

        monkeypatch.setattr(feeds, "add_reference_by_identifier", fake_add)
        with pytest.raises(feeds.FeedError):
            feeds.add_item(rows[3])
        ref, created = feeds.add_item(rows[0])  # the feed's project by default
        assert created and ref.arxiv_id == "2609.00001"
        assert ProjectReference.objects.filter(project=project, reference=ref).exists()
        rows[0].refresh_from_db()
        rows[1].refresh_from_db()
        assert rows[0].reference_id == ref.pk and rows[1].reference_id == ref.pk  # the hook
        assert [r["title"] for r in feeds.items()["results"]] == ["Beta", "Gamma no id"]
        ref2, _ = feeds.add_item(rows[2], project=other)
        assert ProjectReference.objects.filter(project=other, reference=ref2).exists()
        # a paper joining the library by any route clears its entries
        FeedItem.objects.create(feed=b, guid="9", title="Delta", doi="10.1/DELTA")
        delta = ReferenceFactory(doi="10.1/delta")
        assert FeedItem.objects.get(guid="9").reference_id == delta.pk
        # a save naming other fields does not look at the feeds
        with CaptureQueriesContext(connection) as ctx:
            delta.title = "x"
            delta.save(update_fields=["title", "updated_at"])
        assert not any("literature_feeditem" in q["sql"] for q in ctx.captured_queries)


@pytest.mark.django_db
class TestApi:
    def test_endpoints(self, client, settings, owner, monkeypatch, public_hosts):
        settings.ATLAS_API_KEY = "k"
        headers = {"HTTP_X_API_KEY": "k", "HTTP_HOST": "127.0.0.1"}
        project = ProjectFactory()
        routes = {
            "https://rss.arxiv.org/rss/cs.CL": RSS_ARXIV,
            "https://journal.example/home": (200, {"Content-Type": "text/html"}, HTML_PAGE),
            "https://journal.example/feed.rss": RDF_NATURE,
        }
        monkeypatch.setattr(feeds, "_client", lambda: server(routes))
        base = "/api/v1/feeds/"
        assert client.get(base).status_code == 401
        assert client.post(base + "items/dismiss/").status_code == 401

        def post(path, payload):
            return client.post(
                path, data=json.dumps(payload), content_type="application/json", **headers
            )

        for payload in (
            {},
            {"url": "http://localhost/feed"},
            {"url": "https://journal.example/missing"},
        ):
            r = post(base, payload)
            assert r.status_code == 400 and "url" in r.json(), payload
        r = post(base, {"url": "https://rss.arxiv.org/rss/cs.CL", "project": project.slug})
        assert r.status_code == 201, r.content
        feed = r.json()
        assert feed["title"] == "cs.CL updates on arXiv.org" and feed["new"] == 2
        assert feed["project"] == project.slug and feed["items"] == 2
        assert post(base, {"url": "https://rss.arxiv.org/rss/cs.CL"}).status_code == 200
        r = post(base, {"url": "https://journal.example/home", "title": "NHB"})
        assert r.status_code == 201 and r.json()["url"] == "https://journal.example/feed.rss"
        nhb = r.json()
        r = client.get(base, **headers)
        assert [f["title"] for f in r.json()["results"]] == ["cs.CL updates on arXiv.org", "NHB"]
        r = client.patch(
            f"{base}{nhb['id']}/",
            data=json.dumps({"title": "Nature HB", "project": project.slug}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200 and r.json()["project"] == project.slug
        # items
        r = client.get(base + "items/", **headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 3 and body["status"]["feeds"] == 2
        assert [x["title"] for x in body["results"]] == [  # undated entries last
            "Token Merging for Multilingual Speech Recognition",
            "Staying in academia",
            "A cross-list",
        ]
        r = client.get(base + f"items/?feed={feed['id']}&q=token", **headers)
        assert [x["title"] for x in r.json()["results"]] == [
            "Token Merging for Multilingual Speech Recognition"
        ]
        assert client.get(base + "items/?project=" + project.slug, **headers).json()["count"] == 3
        assert client.get(base + "items/?limit=x", **headers).status_code == 400
        assert client.get(base + "items/?feed=99999999999", **headers).status_code == 400
        # add one (the identifier resolver is mocked), dismiss the rest
        item = body["results"][1]
        monkeypatch.setattr(
            feeds,
            "add_reference_by_identifier",
            lambda ident: (ReferenceFactory(doi=ident, bibtex_key="mercer2026staying"), True),
        )
        r = post(base + "items/add/", {"id": item["id"]})
        assert r.status_code == 201 and r.json()["bibtex_key"] == "mercer2026staying"
        assert ProjectReference.objects.filter(project=project).count() == 1  # the feed's project
        assert post(base + "items/add/", {"id": "x"}).status_code == 400
        assert post(base + "items/add/", {"id": 99999999}).status_code == 404
        ids = [body["results"][0]["id"], body["results"][2]["id"]]
        r = post(base + "items/dismiss/", {"ids": ids})
        assert r.status_code == 200 and r.json()["changed"] == 2
        assert client.get(base + "items/", **headers).json()["count"] == 0
        assert client.get(base + "items/?dismissed=1", **headers).json()["count"] == 2
        assert post(base + "items/dismiss/", {"ids": ids, "undo": True}).json()["changed"] == 2
        for payload in ({"ids": []}, {"ids": ["x"]}, {"ids": list(range(501))}):
            assert post(base + "items/dismiss/", payload).status_code == 400, payload
        # refresh: status, chosen ids, stale (all fresh → nothing), junk, one feed
        r = client.get(base + "refresh/", **headers)
        assert r.status_code == 200 and r.json()["status"]["feeds"] == 2
        r = post(base + "refresh/", {"ids": [feed["id"]]})
        assert r.status_code == 200 and r.json()["feeds"] == 1 and r.json()["seen"] == 2
        assert post(base + "refresh/", {}).json()["feeds"] == 0
        assert post(base + "refresh/", {"hours": 0}).json()["feeds"] == 0
        for payload in ({"ids": list(range(21))}, {"ids": ["x"]}, {"hours": "abc"}):
            assert post(base + "refresh/", payload).status_code == 400, payload
        r = client.post(f"{base}{feed['id']}/refresh/", **headers)
        assert r.status_code == 200 and r.json()["seen"] == 2 and r.json()["feed"]["new"] == 2
        # stop following: entries go, the added paper stays
        r = client.delete(f"{base}{nhb['id']}/", **headers)
        assert r.status_code == 204
        assert FeedItem.objects.filter(feed_id=nhb["id"]).count() == 0
        assert Reference.objects.filter(bibtex_key="mercer2026staying").exists()

    def test_management_command_and_sweep_hooks(self, monkeypatch, capsys):
        from django.core.management import call_command

        a = Feed.objects.create(url="https://rss.arxiv.org/rss/cs.CL")
        Feed.objects.create(url="https://b.example/rss")
        monkeypatch.setattr(
            feeds,
            "_client",
            lambda: server({a.url: RSS_ARXIV, "https://b.example/rss": (500, {}, b"")}),
        )
        call_command("refresh_feeds")
        out = capsys.readouterr().out
        assert "feeds 2 · new 2 · seen again 0 · unchanged 0 · errors 1" in out
        assert "ERR  https://b.example/rss: the feed answered 500" in out
        call_command("refresh_feeds", "--all")
        assert "seen again 2" in capsys.readouterr().out
        src = Path(__file__).resolve().parents[2]
        assert "refresh_stale_feeds" in (src / "core" / "snapshots.py").read_text()
        assert "refresh_feeds_task" in (src / "literature" / "tasks.py").read_text()


def test_ui_is_wired():
    root = Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "pages"
    lib = (root / "Library.tsx").read_text()
    for needle in (
        'data-testid="feeds-rail"',
        'data-testid="rail-feeds-all"',
        'data-testid="rail-feed"',
        'data-testid="add-feed"',
        'data-testid="feed-url"',
        'data-testid="refresh-feeds"',
        'data-testid="feeds-panel"',
        'data-testid="feed-row"',
        'data-testid="feed-add"',
        'data-testid="feed-dismiss"',
        'data-testid="feed-filter"',
        'data-testid="unfollow-feed"',
        'data-testid="feed-mute"',
        'data-testid="feed-mute-input"',
        'data-testid="feed-toggle-muted"',
        "&muted=1",
        "/feeds/items/",
        "/feeds/items/add/",
        "/feeds/items/dismiss/",
        "/feeds/refresh/",
    ):
        assert needle in lib, needle


@pytest.mark.django_db
class TestMute:
    """#543: a feed's mute list hides entries — at fetch time and, when the list changes, over
    the stored ones — without deleting them, so a term can be taken back."""

    def test_clean_mute_and_matcher(self):
        assert feeds.clean_mute(["  LLM ", "llm", "", "a", "author:", "large  language model"]) == [
            "LLM",
            "large language model",
        ]
        assert len(feeds.clean_mute([f"t{i}" for i in range(80)])) == feeds.MUTE_TERMS_MAX
        assert len(feeds.clean_mute(["x" * 200])[0]) == feeds.MUTE_TERM_MAX
        assert feeds.clean_mute("benchmark") == []  # not a list
        assert feeds.mute_matcher([]) is None
        match = feeds.mute_matcher(["LLM", "large language model", "author:Doe", "c++"])
        assert match("A film about attention", "", []) == ""  # word boundary: film ≠ LLM
        assert match("An llm study", "", []) == "LLM"
        assert match("Scaling", "we train a Large Language Model", []) == "large language model"
        assert match("Plain", "", ["Jane Doe", "A. Smith"]) == "author:Doe"
        assert match("Fast C++ kernels", "", []) == "c++"
        assert match("Nothing here", "nothing", ["Nobody"]) == ""

    def test_fetch_stores_matching_entries_muted(self, public_hosts):
        feed = Feed.objects.create(url="https://a.example/rss", mute=["benchmark"])
        body = RSS_ARXIV.replace(
            b"<item>",
            b"<item><title>A benchmark for load</title><guid>mute-1</guid></item><item>",
            1,
        )
        out = feeds.fetch_feed(feed, server({feed.url: body}))
        assert out["muted"] == 1 and out["new"] == 3
        feed.refresh_from_db()
        assert feed.muted_total == 1
        hidden = feed.items.get(guid="mute-1")
        assert hidden.muted_at is not None and hidden.muted_by == "benchmark"
        assert feed.items.filter(muted_at__isnull=True).count() == 2
        # the feed's counts and the list leave muted entries out; ?muted=1 lists them
        row = feeds.feed_row(feeds.feeds_with_counts().get(pk=feed.pk))
        assert (row["new"], row["muted"], row["mute"], row["muted_total"]) == (
            2,
            1,
            ["benchmark"],
            1,
        )
        assert [r["title"] for r in feeds.items(muted=True)["results"]] == ["A benchmark for load"]
        assert feeds.items(muted=True)["results"][0]["muted_by"] == "benchmark"
        assert all(r["muted_at"] is None for r in feeds.items()["results"])
        assert feeds.status()["muted"] == 1 and feeds.status()["new"] == 2
        assert feeds.open_items().count() == 2
        # a second fetch re-stamps nothing and counts nothing
        out = feeds.fetch_feed(feed, server({feed.url: body}))
        assert out["muted"] == 0 and out["seen"] == 3
        assert Feed.objects.get(pk=feed.pk).muted_total == 1

    def test_apply_mute_both_ways_and_precedence(self):
        feed = Feed.objects.create(url="https://b.example/rss")
        rows = [
            FeedItem.objects.create(feed=feed, guid=f"g{i}", title=t, authors=a)
            for i, (t, a) in enumerate(
                [
                    ("A benchmark paper", []),
                    ("Attention and load", ["Jane Doe"]),
                    ("Plain paper", []),
                    ("Dismissed benchmark", []),
                ]
            )
        ]
        rows[3].dismissed_at = timezone.now()
        rows[3].save(update_fields=["dismissed_at"])
        own = ReferenceFactory()
        rows[2].reference = own
        rows[2].save(update_fields=["reference"])
        feed.mute = ["benchmark", "author:doe"]
        feed.save(update_fields=["mute"])
        assert feeds.apply_mute(feed) == {"muted": 2, "unmuted": 0}
        by = {r.guid: FeedItem.objects.get(pk=r.pk) for r in rows}
        assert by["g0"].muted_by == "benchmark" and by["g1"].muted_by == "author:doe"
        assert by["g2"].muted_at is None and by["g3"].muted_at is None  # library / dismissed
        assert Feed.objects.get(pk=feed.pk).muted_total == 2
        # take one term back: only the entries no other term matches come back
        feed.mute = ["author:doe"]
        feed.save(update_fields=["mute"])
        assert feeds.apply_mute(feed) == {"muted": 0, "unmuted": 1}
        assert FeedItem.objects.get(pk=rows[0].pk).muted_at is None
        assert FeedItem.objects.get(pk=rows[1].pk).muted_by == "author:doe"
        feed.mute = []
        feed.save(update_fields=["mute"])
        assert feeds.apply_mute(feed) == {"muted": 0, "unmuted": 1}

    def test_api_patch_mute_applies_and_validates(self, client, owner, settings):
        settings.ATLAS_API_KEY = "k"
        headers = {"HTTP_X_API_KEY": "k"}
        feed = Feed.objects.create(url="https://c.example/rss", title="C")
        FeedItem.objects.create(feed=feed, guid="x1", title="A benchmark study")
        FeedItem.objects.create(feed=feed, guid="x2", title="Something else")
        out = client.patch(
            f"/api/v1/feeds/{feed.pk}/",
            {"mute": [" Benchmark ", "benchmark", "author:"]},
            content_type="application/json",
            **headers,
        )
        assert out.status_code == 200, out.content
        body = out.json()
        assert body["mute"] == ["Benchmark"] and body["muted"] == 1 and body["new"] == 1
        assert body["muted_total"] == 1
        listed = client.get("/api/v1/feeds/items/?muted=1", **headers).json()
        assert [r["title"] for r in listed["results"]] == ["A benchmark study"]
        assert listed["results"][0]["muted_by"] == "Benchmark"
        assert listed["status"]["muted"] == 1
        assert client.get("/api/v1/feeds/items/", **headers).json()["count"] == 1
        # too many terms, a too-short or blank term, not a list → 400; a rename alone touches no entry
        assert (
            client.patch(
                f"/api/v1/feeds/{feed.pk}/",
                {"mute": [f"t{i}" for i in range(60)]},
                content_type="application/json",
                **headers,
            ).status_code
            == 400
        )
        assert (
            client.patch(
                f"/api/v1/feeds/{feed.pk}/",
                {"mute": ["a"]},
                content_type="application/json",
                **headers,
            ).status_code
            == 400
        )
        assert (
            client.patch(
                f"/api/v1/feeds/{feed.pk}/",
                {"mute": ["benchmark", ""]},
                content_type="application/json",
                **headers,
            ).status_code
            == 400
        )
        assert (
            client.patch(
                f"/api/v1/feeds/{feed.pk}/",
                {"mute": "benchmark"},
                content_type="application/json",
                **headers,
            ).status_code
            == 400
        )
        out = client.patch(
            f"/api/v1/feeds/{feed.pk}/",
            {"title": "C renamed"},
            content_type="application/json",
            **headers,
        )
        assert out.status_code == 200 and out.json()["muted"] == 1
        out = client.patch(
            f"/api/v1/feeds/{feed.pk}/", {"mute": []}, content_type="application/json", **headers
        )
        assert out.json()["muted"] == 0 and out.json()["new"] == 2
        assert client.get("/api/v1/feeds/", **headers).json()["results"][0]["mute"] == []
