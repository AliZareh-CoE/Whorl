"""#530: the citation watch."""

import datetime
import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from django.utils import timezone

from literature import citing
from literature.library import facets
from literature.models import CitingWork, Reference
from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory


def work(oa, doi="", title="Citing paper", refs=(), date="2026-09-01", authors=3, venue="J"):
    return {
        "id": f"https://openalex.org/{oa}",
        "doi": f"https://doi.org/{doi}" if doi else None,
        "title": title,
        "publication_year": int(date[:4]),
        "publication_date": date,
        "cited_by_count": 2,
        "authorships": [{"author": {"display_name": f"Author {i}"}} for i in range(authors)],
        "primary_location": {"source": {"display_name": venue}},
        "referenced_works": [f"https://openalex.org/{r}" for r in refs],
    }


def openalex(works=(), status=200, log=None, resolve=None, pages=None):
    """A mock OpenAlex: `cites:` list queries answer `works` (or `pages`, one list per page);
    `doi:` queries answer `resolve` {doi: W-id}."""

    def handler(request):
        if log is not None:
            log.append(request)
        q = parse_qs(str(request.url.query.decode()))
        flt = q.get("filter", [""])[0]
        if flt.startswith("doi:"):
            rows = [
                {"id": f"https://openalex.org/{wid}", "doi": f"https://doi.org/{doi}"}
                for doi, wid in (resolve or {}).items()
                if doi in flt
            ]
            return httpx.Response(200, json={"results": rows})
        if status != 200:
            return httpx.Response(status, json={"error": "Rate limit exceeded"})
        if pages is not None:
            page = int(q.get("page", ["1"])[0])
            return httpx.Response(
                200, json={"results": pages[page - 1] if page <= len(pages) else []}
            )
        return httpx.Response(200, json={"results": list(works)})

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.django_db
class TestLookup:
    def test_watched_and_open_alerts(self):
        a = ReferenceFactory(openalex_id="W1", doi=None)
        b = ReferenceFactory(doi="10.1/b")
        ReferenceFactory(doi=None)
        assert set(citing.watched().values_list("pk", flat=True)) == {a.pk, b.pk}
        w = CitingWork.objects.create(openalex_id="W9", title="t")
        w.cites.add(a)
        assert list(citing.open_alerts()) == [w]
        w.dismissed_at = timezone.now()
        w.save()
        assert not citing.open_alerts().exists()

    def test_lookup_batches_ids_with_a_pipe_and_pages_until_a_short_page(self):
        log = []
        page1 = [work(f"W{i}") for i in range(citing.PER_PAGE)]
        page2 = [work("Wlast")]
        client = openalex(log=log, pages=[page1, page2])
        works = citing.lookup_citing(["W1", "W2"], datetime.date(2026, 1, 2), client)
        assert len(works) == citing.PER_PAGE + 1 and len(log) == 2
        q = parse_qs(str(log[0].url.query.decode()))
        assert q["filter"] == ["cites:W1|W2,from_publication_date:2026-01-02"]
        assert q["per-page"] == ["50"] and q["sort"] == ["publication_date:desc"]
        assert "referenced_works" in q["select"][0] and q["mailto"]
        assert parse_qs(str(log[1].url.query.decode()))["page"] == ["2"]
        assert citing.lookup_citing([], datetime.date.today(), openalex(status=500)) == []
        with pytest.raises(RuntimeError):
            citing.lookup_citing(["W1"], datetime.date.today(), openalex(status=429))

    def test_lookup_stops_at_max_pages(self):
        full = [work(f"W{i}") for i in range(citing.PER_PAGE)]
        client = openalex(pages=[full] * 10)
        assert len(citing.lookup_citing(["W1"], datetime.date.today(), client, max_pages=2)) == 100

    def test_ensure_openalex_ids_resolves_dois_in_one_request(self):
        a = ReferenceFactory(doi="10.1/a")
        b = ReferenceFactory(doi="10.1/b")
        c = ReferenceFactory(openalex_id="W3", doi=None)
        log = []
        out = citing.ensure_openalex_ids([a, b, c], openalex(log=log, resolve={"10.1/a": "W1"}))
        assert [r.pk for r in out] == [a.pk, c.pk]
        a.refresh_from_db()
        assert a.openalex_id == "W1" and len(log) == 1
        with pytest.raises(RuntimeError):
            citing.ensure_openalex_ids(
                [b], httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
            )


@pytest.mark.django_db
class TestCheck:
    def test_first_sweep_stores_links_stamps_and_a_second_sweep_sees_not_news(self):
        lavie = ReferenceFactory(openalex_id="W1", doi=None, bibtex_key="lavie2010attention")
        other = ReferenceFactory(openalex_id="W2", doi=None)
        own = ReferenceFactory(openalex_id="W7", doi="10.1/own")  # a library paper citing lavie
        log = []
        works = [
            work("W100", doi="10.5/new", title="New one", refs=["W1"], date="2026-09-01"),
            work("W101", title="Cites both", refs=["W1", "W2", "W555"], date="2026-08-01"),
            work("W102", title="No referenced works listed", refs=[], date="2026-07-01"),
            work("W7", doi="10.1/own", title="Own paper", refs=["W1"]),
        ]
        before = timezone.now()
        out = citing.check_references(
            [lavie, other, ReferenceFactory(doi=None)], openalex(works, log=log)
        )
        assert out["checked"] == 2 and out["skipped"] == 1 and out["errors"] == 0
        assert [r["title"] for r in out["new"]] == [
            "New one",
            "Cites both",
            "No referenced works listed",
        ]
        assert out["seen"] == 0 and not out["stopped"]
        q = parse_qs(str(log[0].url.query.decode()))
        since = datetime.date.fromisoformat(q["filter"][0].split("from_publication_date:")[1])
        assert (before.date() - since).days in (
            citing.FIRST_WINDOW_DAYS,
            citing.FIRST_WINDOW_DAYS + 1,
        )
        rows = {w.openalex_id: w for w in CitingWork.objects.all()}
        assert set(rows) == {"W100", "W101", "W102", "W7"}
        assert set(rows["W100"].cites.values_list("pk", flat=True)) == {lavie.pk}
        assert set(rows["W101"].cites.values_list("pk", flat=True)) == {lavie.pk, other.pk}
        # nothing of the batch listed → linked to the whole batch, not dropped
        assert set(rows["W102"].cites.values_list("pk", flat=True)) == {lavie.pk, other.pk}
        assert rows["W7"].reference_id == own.pk  # already in the library: not news
        assert rows["W100"].doi == "10.5/new" and rows["W100"].authors == [
            "Author 0",
            "Author 1",
            "Author 2",
        ]
        assert rows["W100"].published_on == datetime.date(2026, 9, 1) and rows["W100"].venue == "J"
        for r in (lavie, other):
            r.refresh_from_db()
            assert r.cited_by_checked_at is not None
        assert citing.open_alerts().count() == 3
        # second sweep: same works → seen, first-seen stamp unmoved, window = stamp - overlap
        first_seen = rows["W100"].created_at
        log.clear()
        out = citing.check_references([lavie, other], openalex(works, log=log))
        assert out["new"] == [] and out["seen"] == 4 and out["checked"] == 2
        assert CitingWork.objects.get(openalex_id="W100").created_at == first_seen
        q = parse_qs(str(log[0].url.query.decode()))
        since = datetime.date.fromisoformat(q["filter"][0].split("from_publication_date:")[1])
        assert (timezone.now().date() - since).days in (
            citing.OVERLAP_DAYS,
            citing.OVERLAP_DAYS + 1,
        )
        # a changed title on a re-sight is taken
        works[0]["title"] = "New one (corrected)"
        citing.check_references([lavie], openalex(works))
        assert CitingWork.objects.get(openalex_id="W100").title == "New one (corrected)"

    def test_a_failed_request_stamps_nothing_and_trips_the_breaker(self):
        refs = [ReferenceFactory(openalex_id=f"W{i}", doi=None) for i in range(3)]
        for r in refs:
            r.cited_by_checked_at = timezone.now() - datetime.timedelta(days=40)
            r.save()
        CitingWork.objects.create(openalex_id="Wold", title="kept").cites.add(refs[0])
        out = citing.check_references(refs, openalex(status=429))
        assert out["errors"] == 3 and out["checked"] == 0 and out["new"] == []
        assert not out["stopped"]  # one batch, one failure — the breaker needs three
        for r in refs:
            r.refresh_from_db()
            assert (timezone.now() - r.cited_by_checked_at).days >= 39
        assert CitingWork.objects.filter(openalex_id="Wold").exists()
        many = [
            ReferenceFactory(openalex_id=f"W{100 + i}", doi=None) for i in range(citing.CHUNK * 4)
        ]
        out = citing.check_references(many, openalex(status=500))
        assert out["stopped"] and out["errors"] == citing.CHUNK * 3

    def test_doi_only_papers_are_resolved_first_and_unknown_ones_skipped(self):
        a = ReferenceFactory(doi="10.1/a")
        b = ReferenceFactory(doi="10.1/unknown")
        log = []
        out = citing.check_references(
            [a, b], openalex([work("W200", refs=["W1"])], log=log, resolve={"10.1/a": "W1"})
        )
        assert out["checked"] == 1 and out["skipped"] == 1 and len(out["new"]) == 1
        a.refresh_from_db()
        b.refresh_from_db()
        assert a.openalex_id == "W1" and a.cited_by_checked_at and b.cited_by_checked_at
        assert citing.check_stale()["checked"] == 0  # the unknown DOI is not re-asked hourly
        filters = [parse_qs(str(r.url.query.decode()))["filter"][0] for r in log]
        assert filters[0] == "doi:10.1/a|10.1/unknown" and filters[1].startswith("cites:W1,")

    def test_stale_selection_and_status(self, monkeypatch):
        old = ReferenceFactory(openalex_id="W1", doi=None)
        old.cited_by_checked_at = timezone.now() - datetime.timedelta(days=10)
        old.save()
        fresh = ReferenceFactory(openalex_id="W2", doi=None)
        fresh.cited_by_checked_at = timezone.now()
        fresh.save()
        never = ReferenceFactory(doi="10.1/n")
        ReferenceFactory(doi=None)  # not watched
        assert [r.pk for r in citing.stale_references(7, 10)] == [never.pk, old.pk]
        assert [r.pk for r in citing.stale_references(10**9, 1)] == [never.pk]
        status = citing.watch_status()
        assert status == {
            "new": 0,
            "dismissed": 0,
            "watched": 3,
            "unchecked": 1,
            "last_checked_at": fresh.cited_by_checked_at,
        }
        asked = []
        monkeypatch.setattr(
            citing, "check_references", lambda refs, client=None: asked.append(refs) or {}
        )
        citing.check_stale(days=1, limit=50)
        assert [r.pk for r in asked[0]] == [never.pk, old.pk]
        for r in (old, never):
            r.cited_by_checked_at = timezone.now()
            r.save()
        assert citing.check_stale()["checked"] == 0 and len(asked) == 1


@pytest.mark.django_db
class TestFeed:
    def test_alerts_filters_dismiss_and_the_add_hook(self):
        p1 = ProjectReferenceFactory()
        p2 = ProjectReferenceFactory()
        a, b = p1.reference, p2.reference
        w1 = CitingWork.objects.create(
            openalex_id="W1", doi="10.9/w1", title="one", published_on=datetime.date(2026, 9, 1)
        )
        w1.cites.add(a)
        w2 = CitingWork.objects.create(
            openalex_id="W2", title="two", published_on=datetime.date(2026, 8, 1)
        )
        w2.cites.add(a, b)
        w3 = CitingWork.objects.create(
            openalex_id="W3", title="three", published_on=datetime.date(2026, 7, 1)
        )
        w3.cites.add(b)
        feed = citing.alerts()
        assert feed["count"] == 3 and [r["title"] for r in feed["results"]] == [
            "one",
            "two",
            "three",
        ]
        row = feed["results"][0]
        assert row["addable"] is True and row["url"] == "https://doi.org/10.9/w1"
        assert row["cites"] == [{"id": a.pk, "bibtex_key": a.bibtex_key, "title": a.title}]
        assert feed["results"][1]["addable"] is False and feed["results"][1]["url"].endswith("/W2")
        assert [r["id"] for r in citing.alerts(project=p2.project.slug)["results"]] == [
            w2.pk,
            w3.pk,
        ]
        assert [r["id"] for r in citing.alerts(reference_id=a.pk)["results"]] == [w1.pk, w2.pk]
        assert citing.alerts(limit=1)["count"] == 3 and len(citing.alerts(limit=1)["results"]) == 1
        # dismiss + undo
        assert citing.dismiss([w1.pk, w3.pk]) == 2 and citing.dismiss([w1.pk]) == 0
        assert [r["id"] for r in citing.alerts()["results"]] == [w2.pk]
        assert [r["id"] for r in citing.alerts(dismissed=True)["results"]] == [w1.pk, w3.pk]
        assert citing.dismiss([w1.pk], undo=True) == 1 and citing.alerts()["count"] == 2
        # facets count open alerts on the view's papers
        assert facets(Reference.objects.all())["new_citations"] == 2
        assert facets(Reference.objects.filter(pk=b.pk))["new_citations"] == 1
        # adding the paper to the library removes it from the feed (the post_save hook)
        added = ReferenceFactory(doi="10.9/W1")
        w1.refresh_from_db()
        assert w1.reference_id == added.pk and citing.alerts()["count"] == 1
        assert citing.watch_status()["new"] == 1
        # a save that names other fields does not look for citing works
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        added.last_page = 3
        with CaptureQueriesContext(connection) as ctx:
            added.save(update_fields=["last_page", "updated_at"])
        assert not any("literature_citingwork" in q["sql"] for q in ctx.captured_queries)


@pytest.mark.django_db
class TestApi:
    def test_endpoints(self, client, settings, owner, monkeypatch):
        settings.ATLAS_API_KEY = "k"
        headers = {"HTTP_X_API_KEY": "k", "HTTP_HOST": "127.0.0.1"}
        link = ProjectReferenceFactory(reference__openalex_id="W1", reference__doi=None)
        a = link.reference
        b = ReferenceFactory(openalex_id="W2", doi=None)
        works = [
            work("W100", doi="10.5/new", title="New one", refs=["W1"]),
            work("W101", refs=["W2"], date="2026-08-01"),
        ]
        monkeypatch.setattr(citing, "_client", lambda: openalex(works))
        base = "/api/v1/references/new-citations/"
        assert client.get(base).status_code == 401
        assert client.post(base + "check/").status_code == 401
        assert client.post(base + "dismiss/").status_code == 401
        r = client.post(
            base + "check/",
            data=json.dumps({"ids": [a.pk, b.pk]}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["checked"] == 2 and [x["title"] for x in body["new"]] == [
            "New one",
            "Citing paper",
        ]
        assert body["status"]["new"] == 2 and body["status"]["watched"] == 2
        for payload in ({"ids": list(range(51))}, {"ids": ["x"]}, {"stale": True, "days": "abc"}):
            r = client.post(
                base + "check/",
                data=json.dumps(payload),
                content_type="application/json",
                **headers,
            )
            assert r.status_code == 400, payload
        # stale: both just checked → nothing asked
        r = client.post(
            base + "check/",
            data=json.dumps({"stale": True}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200 and r.json()["checked"] == 0
        assert client.get(base + "check/", **headers).json()["status"]["new"] == 2
        # the feed, filtered
        feed = client.get(base, **headers).json()
        assert feed["count"] == 2 and feed["results"][0]["cites"][0]["bibtex_key"] == a.bibtex_key
        assert feed["status"]["unchecked"] == 0
        assert client.get(base + f"?project={link.project.slug}", **headers).json()["count"] == 1
        assert client.get(base + f"?reference={b.pk}", **headers).json()["count"] == 1
        assert client.get(base + "?limit=x", **headers).status_code == 400
        assert client.get(base + f"?reference={10**19}", **headers).status_code == 400
        # dismiss, undo, junk
        w = feed["results"][0]["id"]
        r = client.post(
            base + "dismiss/",
            data=json.dumps({"ids": [w]}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200 and r.json()["changed"] == 1 and r.json()["status"]["new"] == 1
        assert client.get(base + "?dismissed=1", **headers).json()["count"] == 1
        r = client.post(
            base + "dismiss/",
            data=json.dumps({"ids": [w], "undo": True}),
            content_type="application/json",
            **headers,
        )
        assert r.json()["changed"] == 1 and client.get(base, **headers).json()["count"] == 2
        for payload in ({}, {"ids": []}, {"ids": ["x"]}, {"ids": list(range(501))}):
            r = client.post(
                base + "dismiss/",
                data=json.dumps(payload),
                content_type="application/json",
                **headers,
            )
            assert r.status_code == 400, payload
        # facet + row field
        assert client.get("/api/v1/references/facets/", **headers).json()["new_citations"] == 2
        assert client.get(f"/api/v1/references/{a.pk}/", **headers).json()["cited_by_checked_at"]
        # adding the paper by its DOI takes it out of the feed
        monkeypatch.setattr(
            "literature.services.add_reference_by_identifier",
            lambda ident: (ReferenceFactory(doi="10.5/new"), True),
        )
        r = client.post(
            "/api/v1/references/by-doi/",
            data=json.dumps({"doi": "10.5/new"}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code in (200, 201), r.content
        assert client.get(base, **headers).json()["count"] == 1

    def test_management_command_and_sweep_hooks(self, monkeypatch, capsys):
        from django.core.management import call_command

        ReferenceFactory(openalex_id="W1", doi=None)
        monkeypatch.setattr(
            citing, "_client", lambda: openalex([work("W100", refs=["W1"], title="Fresh")])
        )
        call_command("check_citations")
        out = capsys.readouterr().out
        assert "NEW  Fresh" in out and "checked 1 · new 1" in out
        call_command("check_citations", "--all")
        assert "seen again 1" in capsys.readouterr().out
        src = Path(__file__).resolve().parents[2]
        assert "check_stale_citations" in (src / "core" / "snapshots.py").read_text()
        assert "check_citations_task" in (src / "literature" / "tasks.py").read_text()


def test_ui_is_wired():
    root = Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "pages"
    lib = (root / "Library.tsx").read_text()
    for needle in (
        'data-testid="rail-new-citations"',
        'data-testid="check-citations"',
        'data-testid="citing-row"',
        'data-testid="citing-add"',
        'data-testid="citing-dismiss"',
        'data-testid="citing-cites"',
        'data-testid="citing-line"',
        "/references/new-citations/",
        "/references/new-citations/check/",
        "/references/new-citations/dismiss/",
    ):
        assert needle in lib, needle
    ref = (root / "Reference.tsx").read_text()
    assert 'data-testid="citing-section"' in ref and "/references/new-citations/" in ref


@pytest.mark.django_db
def test_alerts_put_undated_works_last_on_every_database():
    """#545 (backlog 332): the model's `-published_on` ordering puts undated works first on
    Postgres and last on SQLite; the feed orders them last explicitly."""
    a = ReferenceFactory(doi="10.9/dated")
    dated = CitingWork.objects.create(
        openalex_id="W-d", title="dated", published_on=datetime.date(2026, 9, 1)
    )
    undated = CitingWork.objects.create(openalex_id="W-u", title="undated")
    older = CitingWork.objects.create(
        openalex_id="W-o", title="older", published_on=datetime.date(2026, 1, 1)
    )
    for w in (dated, undated, older):
        w.cites.add(a)
    assert [r["id"] for r in citing.alerts()["results"]] == [dated.pk, older.pk, undated.pk]
