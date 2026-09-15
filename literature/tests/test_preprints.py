"""#529: the preprint watch."""

import json
from pathlib import Path

import httpx
import pytest
from django.utils import timezone

from literature import preprints
from literature.library import facets, filter_references
from literature.models import Reference
from literature.services import MetadataError
from literature.tests.factories import ReferenceFactory

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry><id>http://arxiv.org/abs/1512.03385v6</id><title>Deep Residual Learning</title>
    <arxiv:doi>10.1109/CVPR.2016.90</arxiv:doi><arxiv:journal_ref>CVPR 2016, pp. 770-778</arxiv:journal_ref></entry>
  <entry><id>http://arxiv.org/abs/2301.00001v1</id><title>Nothing yet</title></entry>
  <entry><id>http://arxiv.org/abs/2202.00002v2</id><title>Own DOI only</title>
    <arxiv:doi>10.48550/arXiv.2202.00002</arxiv:doi></entry>
</feed>"""


def route(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def sources(arxiv=ATOM, s2=None, arxiv_status=200, s2_status=200, log=None):
    """A mock transport answering arXiv with Atom and Semantic Scholar with a JSON list."""

    def handler(request):
        if log is not None:
            log.append(request)
        if "arxiv.org" in request.url.host:
            return httpx.Response(arxiv_status, text=arxiv)
        body = json.loads(request.content or b"{}")
        rows = s2 or {}
        return httpx.Response(
            s2_status,
            json=[rows.get(i.removeprefix("ARXIV:")) for i in body.get("ids", [])],
        )

    return route(handler)


def preprint(arxiv_id, **kw):
    kw.setdefault("doi", None)
    kw.setdefault("venue", "arXiv")
    return ReferenceFactory(arxiv_id=arxiv_id, **kw)


@pytest.mark.django_db
class TestRules:
    def test_is_preprint_and_the_queryset_agree(self):
        a = preprint("1512.03385")
        b = preprint("2202.00002", doi="10.48550/arXiv.2202.00002")
        c = ReferenceFactory(arxiv_id="1706.03762", doi="10.5555/published")
        d = ReferenceFactory(doi="10.1/plain")
        assert [preprints.is_preprint(r) for r in (a, b, c, d)] == [True, True, False, False]
        assert set(preprints.preprints().values_list("pk", flat=True)) == {a.pk, b.pk}

    def test_lookup_arxiv_reads_the_deposited_doi_and_skips_arxiv_dois(self):
        found = preprints.lookup_arxiv(["1512.03385", "2301.00001", "2202.00002"], sources())
        assert found == {
            "1512.03385": {
                "doi": "10.1109/cvpr.2016.90",
                "venue": "CVPR 2016, pp. 770-778",
                "source": "arxiv",
            }
        }
        with pytest.raises(RuntimeError):
            preprints.lookup_arxiv(["1512.03385"], sources(arxiv_status=429))
        with pytest.raises(ValueError):
            preprints.lookup_arxiv(["1512.03385"], sources(arxiv="Rate exceeded."))
        assert preprints.lookup_arxiv([], sources(arxiv_status=500)) == {}

    def test_lookup_s2_reads_external_ids_and_the_best_venue_name(self):
        rows = {
            "2301.00001": {
                "externalIds": {"ArXiv": "2301.00001", "DOI": "10.1000/xyz"},
                "venue": "NeurIPS",
                "publicationVenue": {"name": "Neural Information Processing Systems"},
            },
            "1111.11111": {"externalIds": {"DOI": "10.48550/arXiv.1111.11111"}},
            "2222.22222": None,
        }
        found = preprints.lookup_s2(["2301.00001", "1111.11111", "2222.22222"], sources(s2=rows))
        assert found == {
            "2301.00001": {
                "doi": "10.1000/xyz",
                "venue": "Neural Information Processing Systems",
                "source": "s2",
            }
        }
        with pytest.raises(RuntimeError):
            preprints.lookup_s2(["2301.00001"], sources(s2_status=429))


@pytest.mark.django_db
class TestCheck:
    def test_arxiv_first_then_s2_for_the_rest_stamps_and_stores(self):
        resnet = preprint("1512.03385")
        later = preprint("2301.00001")
        plain = ReferenceFactory(doi="10.1/plain")
        log = []
        s2 = {"2301.00001": {"externalIds": {"DOI": "10.1000/xyz"}, "venue": "NeurIPS"}}
        out = preprints.check_references([resnet, later, plain], sources(s2=s2, log=log), pause=0)
        assert (out["checked"], out["errors"], out["skipped"], out["stopped"]) == (2, 0, 1, False)
        assert sorted(r["bibtex_key"] for r in out["published"]) == sorted(
            [resnet.bibtex_key, later.bibtex_key]
        )
        resnet.refresh_from_db()
        later.refresh_from_db()
        assert (resnet.published_doi, resnet.published_venue) == (
            "10.1109/cvpr.2016.90",
            "CVPR 2016, pp. 770-778",
        )
        assert (later.published_doi, later.published_venue) == ("10.1000/xyz", "NeurIPS")
        assert resnet.published_checked_at and later.published_checked_at
        # one arXiv request for the batch, one Semantic Scholar request for the leftover id
        hosts = [r.url.host for r in log]
        assert hosts == ["export.arxiv.org", "api.semanticscholar.org"]
        s2_body = json.loads(log[1].content)
        assert s2_body["ids"] == ["ARXIV:2301.00001"]

    def test_a_miss_moves_the_stamp_but_never_clears_a_found_doi(self):
        ref = preprint("1512.03385", published_doi="10.1109/cvpr.2016.90", published_venue="CVPR")
        before = ref.published_checked_at
        # arXiv now answers without the DOI, Semantic Scholar knows nothing
        atom = ATOM.replace("<arxiv:doi>10.1109/CVPR.2016.90</arxiv:doi>", "")
        out = preprints.check_references([ref], sources(arxiv=atom), pause=0)
        ref.refresh_from_db()
        assert out["checked"] == 1 and ref.published_doi == "10.1109/cvpr.2016.90"
        assert ref.published_checked_at and ref.published_checked_at != before
        assert out["published"][0]["published_doi"] == "10.1109/cvpr.2016.90"

    def test_no_source_answering_leaves_everything_alone_and_trips_the_breaker(self):
        refs = [preprint(f"23{i:02d}.00001") for i in range(1, 5)]
        refs[0].published_doi = "10.1/kept"
        refs[0].save(update_fields=["published_doi"])

        def down(request):
            raise httpx.ConnectError("offline")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(preprints, "CHUNK", 1)
            out = preprints.check_references(refs, route(down), pause=0)
        assert out["stopped"] is True
        assert out["errors"] == preprints.MAX_CONSECUTIVE_ERRORS and out["checked"] == 0
        for ref in refs:
            ref.refresh_from_db()
            assert ref.published_checked_at is None
        refs[0].refresh_from_db()
        assert refs[0].published_doi == "10.1/kept"

    def test_stale_selection_skips_known_publications_and_orders_never_first(self):
        now = timezone.now()
        known = preprint("1512.03385", published_doi="10.1/x", published_checked_at=now)
        never = preprint("2301.00001")
        old = preprint("2301.00002", published_checked_at=now - timezone.timedelta(days=40))
        fresh = preprint("2301.00003", published_checked_at=now - timezone.timedelta(days=2))
        got = [r.pk for r in preprints.stale_references(days=30, limit=10)]
        assert got == [never.pk, old.pk]
        assert known.pk not in got and fresh.pk not in got
        assert [r.pk for r in preprints.stale_references(days=10**20, limit=1)] == [never.pk]
        assert preprints.watch_status() == {
            "preprints": 4,
            "published_available": 1,
            "unchecked": 1,
            "last_checked_at": now,
        }

    def test_check_stale_asks_nothing_when_nothing_is_stale(self, monkeypatch):
        preprint("1512.03385", published_checked_at=timezone.now())
        monkeypatch.setattr(preprints, "_client", lambda: (_ for _ in ()).throw(AssertionError))
        assert preprints.check_stale()["checked"] == 0

    def test_filters_and_facets(self):
        a = preprint("1512.03385", published_doi="10.1/x")
        b = preprint("2301.00001")
        ReferenceFactory(doi="10.1/plain")
        qs = Reference.objects.all()
        assert set(filter_references(qs, {"preprints": "1"}).values_list("pk", flat=True)) == {
            a.pk,
            b.pk,
        }
        assert list(
            filter_references(qs, {"published_available": "true"}).values_list("pk", flat=True)
        ) == [a.pk]
        f = facets(qs)
        assert (f["preprints"], f["published_available"]) == (2, 1)


@pytest.mark.django_db
class TestUpgrade:
    def test_upgrade_applies_the_published_metadata_and_keeps_the_key(self, monkeypatch):
        ref = preprint(
            "1512.03385",
            title="Deep Residual Learning (preprint)",
            year=2015,
            published_doi="10.1109/cvpr.2016.90",
            published_venue="CVPR",
            raw_bibtex="@misc{x, title={old}}",
        )
        key = ref.bibtex_key
        monkeypatch.setattr(
            preprints,
            "fetch_metadata_by_doi",
            lambda doi: {
                "doi": doi,
                "entry_type": "inproceedings",
                "title": "Deep Residual Learning for Image Recognition",
                "year": 2016,
                "venue": "2016 IEEE Conference on Computer Vision and Pattern Recognition",
                "url": "https://doi.org/10.1109/cvpr.2016.90",
                "citation_count": 1000,
                "extra": {"source": "crossref"},
            },
        )
        out = preprints.upgrade(ref)
        ref.refresh_from_db()
        assert out == {
            "id": ref.pk,
            "bibtex_key": key,
            "doi": "10.1109/cvpr.2016.90",
            "metadata": "full",
        }
        assert ref.bibtex_key == key and ref.arxiv_id == "1512.03385"
        assert (ref.doi, ref.entry_type, ref.year) == (
            "10.1109/cvpr.2016.90",
            "inproceedings",
            2016,
        )
        assert ref.venue.startswith("2016 IEEE") and ref.raw_bibtex == ""
        assert ref.published_doi == "" and ref.published_venue == ""
        assert ref.extra["preprint"]["venue"] == "arXiv" and ref.extra["preprint"]["year"] == 2015
        assert ref.extra["source"] == "crossref"
        assert not preprints.is_preprint(ref)

    def test_upgrade_offline_applies_the_stored_doi_and_venue(self, monkeypatch):
        ref = preprint("2301.00001", published_doi="10.1000/xyz", published_venue="NeurIPS")

        def offline(doi):
            raise MetadataError("no network")

        monkeypatch.setattr(preprints, "fetch_metadata_by_doi", offline)
        out = preprints.upgrade(ref)
        ref.refresh_from_db()
        assert out["metadata"] == "partial"
        assert (ref.doi, ref.venue, ref.entry_type) == ("10.1000/xyz", "NeurIPS", "article")
        assert ref.url == "https://doi.org/10.1000/xyz"

    def test_upgrade_refuses_without_a_doi_and_on_a_collision(self):
        ref = preprint("2301.00001")
        with pytest.raises(ValueError):
            preprints.upgrade(ref)
        other = ReferenceFactory(doi="10.1000/XYZ")  # a hand-typed DOI keeps its case
        ref.published_doi = "10.1000/xyz"
        ref.save(update_fields=["published_doi"])
        with pytest.raises(preprints.UpgradeConflict) as exc:
            preprints.upgrade(ref)
        assert exc.value.other.pk == other.pk
        ref.refresh_from_db()
        assert ref.doi is None and ref.published_doi == "10.1000/xyz"


@pytest.mark.django_db
class TestApi:
    def test_endpoints(self, client, settings, owner, monkeypatch):
        settings.ATLAS_API_KEY = "k"
        headers = {"HTTP_X_API_KEY": "k", "HTTP_HOST": "127.0.0.1"}
        a = preprint("1512.03385")
        b = preprint("2301.00001")
        monkeypatch.setattr(preprints, "_client", lambda: sources())
        assert client.post("/api/v1/references/check-published/").status_code == 401
        assert client.post(f"/api/v1/references/{a.pk}/upgrade/").status_code == 401
        r = client.post(
            "/api/v1/references/check-published/",
            data=json.dumps({"ids": [a.pk, b.pk]}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["checked"] == 2 and [x["bibtex_key"] for x in body["published"]] == [
            a.bibtex_key
        ]
        assert body["status"]["published_available"] == 1 and "rows" not in body
        row = client.get(f"/api/v1/references/{a.pk}/", **headers).json()
        assert row["preprint"] is True and row["published_doi"] == "10.1109/cvpr.2016.90"
        assert row["published_venue"].startswith("CVPR") and row["published_checked_at"]
        # junk
        for payload in ({"ids": list(range(51))}, {"ids": ["x"]}, {"stale": True, "days": "abc"}):
            r = client.post(
                "/api/v1/references/check-published/",
                data=json.dumps(payload),
                content_type="application/json",
                **headers,
            )
            assert r.status_code == 400, payload
        # stale: b has just been checked, a knows its publication → nothing to ask
        r = client.post(
            "/api/v1/references/check-published/",
            data=json.dumps({"stale": True}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200 and r.json()["checked"] == 0
        # list filter + facet + GET status
        listed = client.get("/api/v1/references/?published_available=1", **headers).json()
        assert [x["id"] for x in listed["results"]] == [a.pk]
        assert client.get("/api/v1/references/?preprints=1", **headers).json()["count"] == 2
        assert client.get("/api/v1/references/facets/", **headers).json()["preprints"] == 2
        assert (
            client.get("/api/v1/references/check-published/", **headers).json()["status"][
                "preprints"
            ]
            == 2
        )
        # upgrade: 400 without a known version, 200 with one (offline → partial), 409 on a clash
        r = client.post(f"/api/v1/references/{b.pk}/upgrade/", **headers)
        assert r.status_code == 400

        def offline(doi):
            raise MetadataError("no network")

        monkeypatch.setattr(preprints, "fetch_metadata_by_doi", offline)
        r = client.post(f"/api/v1/references/{a.pk}/upgrade/", **headers)
        assert r.status_code == 200, r.content
        assert (
            r.json()["doi"] == "10.1109/cvpr.2016.90"
            and r.json()["upgrade"]["metadata"] == "partial"
        )
        assert r.json()["preprint"] is False and r.json()["published_doi"] == ""
        ReferenceFactory(doi="10.1000/xyz")
        b.published_doi = "10.1000/xyz"
        b.save(update_fields=["published_doi"])
        r = client.post(f"/api/v1/references/{b.pk}/upgrade/", **headers)
        assert r.status_code == 409 and r.json()["other"]["bibtex_key"]

    def test_preflight_warns_about_cited_preprints_with_a_published_version(self, owner):
        from projects.models import Project
        from writing.models import Manuscript, ManuscriptReference
        from writing.preflight import check_bibliography

        project = Project.objects.create(name="P", slug="p")
        manuscript = Manuscript.objects.create(project=project, title="M")
        dated = preprint("1512.03385", published_doi="10.1/x")
        fresh = preprint("2301.00001")
        for ref in (dated, fresh):
            ManuscriptReference.objects.create(manuscript=manuscript, reference=ref)
        rows = {r["key"]: r for r in check_bibliography(manuscript, network=False)}
        assert rows["preprints"]["state"] == "warn"
        assert dated.bibtex_key in rows["preprints"]["detail"]
        assert fresh.bibtex_key not in rows["preprints"]["detail"]
        dated.published_doi = ""
        dated.save(update_fields=["published_doi"])
        rows = {r["key"]: r for r in check_bibliography(manuscript, network=False)}
        assert rows["preprints"]["state"] == "ok"


def test_ui_is_wired():
    root = Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "pages"
    lib = (root / "Library.tsx").read_text()
    for needle in (
        'data-testid="published-chip"',
        'data-testid="published-banner"',
        'data-testid="upgrade-preprint"',
        'data-testid="preprint-line"',
        'data-testid="rail-preprints"',
        'data-testid="rail-published"',
        'data-testid="check-preprints"',
        "/references/check-published/",
        "/upgrade/",
        'k === "published_available"',
    ):
        assert needle in lib, needle
    assert lib.count('data-testid="published-chip"') == 2  # the list row and the card
    ref = (root / "Reference.tsx").read_text()
    assert 'data-testid="published-banner"' in ref and "/upgrade/" in ref
