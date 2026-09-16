"""Owner idea #4: open-access PDF auto-download."""

import httpx
import pytest
from django.urls import reverse

from literature import oa

from .factories import ReferenceFactory

pytestmark = pytest.mark.django_db

FAKE_PDF = b"%PDF-1.4 tiny"


@pytest.fixture
def patch_http(monkeypatch):
    state = {"handler": None}
    real_client = httpx.Client

    def client_factory(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(state["handler"]))

    monkeypatch.setattr(oa.httpx, "Client", client_factory)
    # the fixtures' hosts do not resolve; a test that wants the real gate stubs it again
    monkeypatch.setattr(oa, "check_url", lambda url: url)
    return state


class TestResolveAndFetch:
    def test_arxiv_reference_uses_arxiv_pdf(self, patch_http):
        ref = ReferenceFactory(arxiv_id="1706.03762", doi=None)

        def handler(request):
            assert request.url.host == "arxiv.org"
            assert "/pdf/1706.03762" in str(request.url)
            return httpx.Response(200, content=FAKE_PDF)

        patch_http["handler"] = handler
        outcome = oa.fetch_and_attach_pdf(ref)
        ref.refresh_from_db()
        assert "attached" in outcome
        assert ref.pdf and ref.pdf.read().startswith(b"%PDF")
        assert ref.extra["oa_pdf"] == outcome

    def test_doi_reference_uses_unpaywall(self, patch_http):
        ref = ReferenceFactory(doi="10.1371/demo.1")

        def handler(request):
            if request.url.host == "api.unpaywall.org":
                assert "email=" in str(request.url)
                return httpx.Response(
                    200,
                    json={"best_oa_location": {"url_for_pdf": "https://repo.example/x.pdf"}},
                )
            assert request.url.host == "repo.example"
            return httpx.Response(200, content=FAKE_PDF)

        patch_http["handler"] = handler
        assert "attached" in oa.fetch_and_attach_pdf(ref)

    def test_no_oa_location_reports_not_found(self, patch_http):
        ref = ReferenceFactory(doi="10.1/closed")
        patch_http["handler"] = lambda request: httpx.Response(200, json={"best_oa_location": None})
        outcome = oa.fetch_and_attach_pdf(ref)
        ref.refresh_from_db()
        assert outcome == "No open-access PDF found."
        assert not ref.pdf

    def test_non_pdf_content_rejected(self, patch_http):
        ref = ReferenceFactory(arxiv_id="2000.00001", doi=None)
        patch_http["handler"] = lambda request: httpx.Response(
            200, content=b"<html>captcha wall</html>"
        )
        outcome = oa.fetch_and_attach_pdf(ref)
        assert "did not serve a PDF" in outcome
        assert not ref.pdf

    def test_existing_pdf_untouched(self):
        from django.core.files.base import ContentFile

        ref = ReferenceFactory()
        ref.pdf.save("have.pdf", ContentFile(FAKE_PDF), save=True)
        assert oa.fetch_and_attach_pdf(ref) == "PDF already attached."

    def test_unpaywall_error_degrades_gracefully(self, patch_http):
        ref = ReferenceFactory(doi="10.1/flaky")

        def handler(request):
            raise httpx.ConnectError("down")

        patch_http["handler"] = handler
        assert oa.fetch_and_attach_pdf(ref) == "No open-access PDF found."


class TestSurfaces:
    def test_manual_fetch_button_flow(self, client_logged_in, monkeypatch):
        ref = ReferenceFactory(doi="10.1/x")
        monkeypatch.setattr(
            "literature.oa.fetch_and_attach_pdf", lambda reference: "PDF attached (12 KB)."
        )
        response = client_logged_in.post(reverse("literature:fetch_pdf", args=[ref.pk]))
        assert response.status_code == 302

    def test_by_doi_api_triggers_background_fetch_when_enabled(
        self, client, owner, settings, monkeypatch
    ):
        settings.ATLAS_API_KEY = "k"
        settings.ATLAS_AUTO_FETCH_PDF = True
        ref = ReferenceFactory(doi="10.1/new")
        monkeypatch.setattr(
            "api.views.literature_services.add_reference_by_identifier",
            lambda identifier: (ref, True),
        )
        called = {}
        monkeypatch.setattr(
            "literature.tasks.fetch_oa_pdf_task", lambda pk: called.setdefault("pk", pk)
        )
        response = client.post(
            "/api/v1/references/by-doi/",
            {"doi": "10.1/new"},
            content_type="application/json",
            HTTP_X_API_KEY="k",
        )
        assert response.status_code == 201
        assert called["pk"] == ref.pk

    def test_no_fetch_for_existing_reference(self, client, owner, settings, monkeypatch):
        settings.ATLAS_API_KEY = "k"
        settings.ATLAS_AUTO_FETCH_PDF = True
        ref = ReferenceFactory(doi="10.1/old")
        monkeypatch.setattr(
            "api.views.literature_services.add_reference_by_identifier",
            lambda identifier: (ref, False),
        )
        called = {}
        monkeypatch.setattr(
            "literature.tasks.fetch_oa_pdf_task", lambda pk: called.setdefault("pk", pk)
        )
        client.post(
            "/api/v1/references/by-doi/",
            {"doi": "10.1/old"},
            content_type="application/json",
            HTTP_X_API_KEY="k",
        )
        assert called == {}


def test_non_https_oa_url_rejected(patch_http):
    ref = ReferenceFactory(doi="10.1/sketchy")
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        if request.url.host == "api.unpaywall.org":
            return httpx.Response(
                200, json={"best_oa_location": {"url_for_pdf": "http://evil.example/x.pdf"}}
            )
        return httpx.Response(200, json={})  # Semantic Scholar / OpenAlex: nothing

    patch_http["handler"] = handler
    assert oa.fetch_and_attach_pdf(ref) == "No open-access PDF found."
    assert "evil.example" not in hosts, "must not follow the http URL"


def _fake_pdf(request):
    return httpx.Response(200, content=FAKE_PDF)


class TestFourSources:
    """The finder asks arXiv, Unpaywall, Semantic Scholar and OpenAlex in turn, and stops at
    the first source whose link serves a real PDF."""

    def test_unpaywall_second_location_is_tried_and_s2_never_asked(self, patch_http):
        ref = ReferenceFactory(doi="10.1/two-locations")
        hosts = []

        def handler(request):
            hosts.append(request.url.host)
            if request.url.host == "api.unpaywall.org":
                return httpx.Response(
                    200,
                    json={
                        "best_oa_location": {"url_for_pdf": "https://wall.example/a.pdf"},
                        "oa_locations": [
                            {"url_for_pdf": "https://wall.example/a.pdf"},
                            {"url_for_pdf": None},
                            {"url_for_pdf": "https://repo.example/b.pdf"},
                        ],
                    },
                )
            if request.url.host == "wall.example":
                return httpx.Response(200, content=b"<html>login</html>")
            return _fake_pdf(request)

        patch_http["handler"] = handler
        outcome = oa.fetch_and_attach_pdf(ref)
        ref.refresh_from_db()
        assert outcome.endswith("via Unpaywall.") and ref.pdf
        assert ref.extra["oa_source"] == "unpaywall"
        assert ref.extra["oa_tried"] == ["Unpaywall"]
        assert "api.semanticscholar.org" not in hosts and "api.openalex.org" not in hosts

    def test_s2_fills_the_arxiv_id_and_the_arxiv_pdf_wins(self, patch_http, settings):
        settings.ATLAS_S2_API_KEY = "s2-key"
        ref = ReferenceFactory(doi="10.1109/CVPR.2016.90", arxiv_id="")
        seen = {}

        def handler(request):
            if request.url.host == "api.unpaywall.org":
                return httpx.Response(200, json={"best_oa_location": None, "oa_locations": []})
            if request.url.host == "api.semanticscholar.org":
                seen["s2_key"] = request.headers.get("x-api-key")
                assert "DOI:10.1109/CVPR.2016.90" in str(request.url)
                return httpx.Response(
                    200,
                    json={
                        "externalIds": {"ArXiv": "1512.03385", "DOI": "10.1109/CVPR.2016.90"},
                        "openAccessPdf": {"url": "https://s2.example/resnet.pdf"},
                    },
                )
            if request.url.host == "arxiv.org":
                assert "/pdf/1512.03385" in str(request.url)
                return _fake_pdf(request)
            raise AssertionError(f"unexpected host {request.url.host}")

        patch_http["handler"] = handler
        outcome = oa.fetch_and_attach_pdf(ref)
        ref.refresh_from_db()
        assert outcome.endswith("via arXiv.") and ref.pdf
        assert ref.arxiv_id == "1512.03385"
        assert ref.extra["oa_source"] == "arxiv"
        assert seen["s2_key"] == "s2-key"

    def test_s2_open_access_pdf_when_it_has_no_arxiv_id(self, patch_http):
        ref = ReferenceFactory(doi="10.1/s2-only")

        def handler(request):
            if request.url.host == "api.unpaywall.org":
                return httpx.Response(404, json={"error": True})
            if request.url.host == "api.semanticscholar.org":
                return httpx.Response(
                    200, json={"externalIds": {}, "openAccessPdf": {"url": "https://s2.example/x"}}
                )
            assert request.url.host == "s2.example"
            return _fake_pdf(request)

        patch_http["handler"] = handler
        outcome = oa.fetch_and_attach_pdf(ref)
        ref.refresh_from_db()
        assert outcome.endswith("via Semantic Scholar.")
        assert ref.arxiv_id == "" and ref.extra["oa_source"] == "s2"

    def test_openalex_is_the_last_resort_and_reads_the_arxiv_landing_page(self, patch_http):
        ref = ReferenceFactory(doi="10.1/openalex-only")

        def handler(request):
            host = request.url.host
            if host == "api.unpaywall.org":
                return httpx.Response(200, json={"best_oa_location": None})
            if host == "api.semanticscholar.org":
                return httpx.Response(429, text="slow down")
            if host == "api.openalex.org":
                assert "doi:10.1/openalex-only" in str(request.url)
                return httpx.Response(
                    200,
                    json={
                        "best_oa_location": {
                            "pdf_url": None,
                            "landing_page_url": "https://arxiv.org/abs/2101.00001v3",
                        },
                        "primary_location": {"pdf_url": "https://pub.example/paywalled.pdf"},
                        "locations": [{"pdf_url": "https://oa.example/free.pdf"}],
                    },
                )
            if host == "arxiv.org":
                return httpx.Response(404)
            if host == "pub.example":
                return httpx.Response(403)
            assert host == "oa.example"
            return _fake_pdf(request)

        patch_http["handler"] = handler
        outcome = oa.fetch_and_attach_pdf(ref)
        ref.refresh_from_db()
        assert outcome.endswith("via OpenAlex.") and ref.pdf
        assert ref.arxiv_id == "2101.00001"
        assert ref.extra["oa_tried"] == ["arXiv", "OpenAlex"]

    def test_a_known_arxiv_id_is_never_overwritten(self, patch_http):
        ref = ReferenceFactory(doi="10.1/keep", arxiv_id="2201.11111")

        def handler(request):
            host = request.url.host
            if host == "arxiv.org":
                return httpx.Response(500)
            if host == "api.unpaywall.org":
                return httpx.Response(200, json={})
            if host == "api.semanticscholar.org":
                return httpx.Response(200, json={"externalIds": {"ArXiv": "9999.99999"}})
            return httpx.Response(200, json={})

        patch_http["handler"] = handler
        assert "Download failed (HTTP 500)" in oa.fetch_and_attach_pdf(ref)
        ref.refresh_from_db()
        assert ref.arxiv_id == "2201.11111" and not ref.pdf
        assert "oa_source" not in ref.extra

    def test_at_most_four_downloads_per_paper(self, patch_http):
        ref = ReferenceFactory(doi="10.1/many")
        downloads, hosts = [], []

        def handler(request):
            hosts.append(request.url.host)
            if request.url.host == "api.unpaywall.org":
                return httpx.Response(
                    200,
                    json={
                        "best_oa_location": None,
                        "oa_locations": [
                            {"url_for_pdf": f"https://mirror{i}.example/x.pdf"} for i in range(6)
                        ],
                    },
                )
            downloads.append(request.url.host)
            return httpx.Response(200, content=b"nope")

        patch_http["handler"] = handler
        assert "did not serve a PDF" in oa.fetch_and_attach_pdf(ref)
        assert len(downloads) == oa.MAX_CANDIDATES
        assert "api.semanticscholar.org" not in hosts

    def test_api_reports_the_source_and_the_learned_arxiv_id(
        self, patch_http, client, owner, settings
    ):
        settings.ATLAS_API_KEY = "k"
        ref = ReferenceFactory(doi="10.1/api", arxiv_id="")

        def handler(request):
            host = request.url.host
            if host == "api.unpaywall.org":
                return httpx.Response(200, json={})
            if host == "api.semanticscholar.org":
                return httpx.Response(200, json={"externalIds": {"ArXiv": "arXiv:1706.03762v5"}})
            assert host == "arxiv.org"
            return _fake_pdf(request)

        patch_http["handler"] = handler
        out = client.post(f"/api/v1/references/{ref.pk}/fetch-pdf/", HTTP_X_API_KEY="k")
        assert out.status_code == 200
        body = out.json()
        assert body["attached"] and body["source"] == "arxiv"
        assert body["arxiv_id"] == "1706.03762"
        assert body["outcome"].endswith("via arXiv.")


class TestHopGuard:
    """Audit #33 (backlog 341): a PDF download follows redirects by hand — every hop must stay
    on https and on a public host, at most five hops, the body streamed under the size cap —
    and (backlog 342) one slow paper cannot eat the sweep's wall clock."""

    def _ref(self):
        return ReferenceFactory(arxiv_id="2101.00001", doi=None)

    def test_redirect_to_a_private_host_is_refused(self, patch_http, monkeypatch):
        hosts = []
        monkeypatch.setattr(
            oa,
            "check_url",
            lambda url: (
                (_ for _ in ()).throw(oa.LinkError("that host is private or unresolvable"))
                if "127.0.0.1" in url
                else url
            ),
        )

        def handler(request):
            hosts.append(request.url.host)
            if request.url.host == "arxiv.org":
                return httpx.Response(302, headers={"location": "https://127.0.0.1/x.pdf"})
            return _fake_pdf(request)

        patch_http["handler"] = handler
        ref = self._ref()
        outcome = oa.fetch_and_attach_pdf(ref)
        assert "127.0.0.1" not in hosts
        assert outcome == "Download refused (redirect: that host is private or unresolvable)."
        ref.refresh_from_db()
        assert not ref.pdf

    def test_first_address_on_a_private_host_is_refused(self, patch_http, monkeypatch):
        # Audit #34, backlog 343: the first link a service hands back is gated like a hop
        hosts = []
        monkeypatch.setattr(
            oa,
            "check_url",
            lambda url: (
                (_ for _ in ()).throw(oa.LinkError("that host is private or unresolvable"))
                if "10.0.0.5" in url
                else url
            ),
        )

        def handler(request):
            hosts.append(request.url.host)
            return _fake_pdf(request)

        patch_http["handler"] = handler
        client = oa.httpx.Client()
        data, why = oa._download(client, "https://10.0.0.5/x.pdf")
        assert (
            data is None
            and why == "Download refused (address: that host is private or unresolvable)."
        )
        assert hosts == []  # never fetched

    def test_redirect_off_https_is_refused(self, patch_http, monkeypatch):
        monkeypatch.setattr(oa, "check_url", lambda url: url)
        hosts = []

        def handler(request):
            hosts.append(f"{request.url.scheme}://{request.url.host}")
            if request.url.host == "arxiv.org":
                return httpx.Response(302, headers={"location": "http://mirror.example/x.pdf"})
            return _fake_pdf(request)

        patch_http["handler"] = handler
        assert oa.fetch_and_attach_pdf(self._ref()) == "Download refused (redirect left https)."
        assert "http://mirror.example" not in hosts

    def test_a_public_https_redirect_is_followed(self, patch_http, monkeypatch):
        monkeypatch.setattr(oa, "check_url", lambda url: url)

        def handler(request):
            if request.url.host == "arxiv.org" and "v2" not in request.url.path:
                return httpx.Response(307, headers={"location": "/pdf/2101.00001v2"})
            return _fake_pdf(request)

        patch_http["handler"] = handler
        # a relative Location resolves against the hop it came from (arxiv.org, https)
        ref = self._ref()
        assert "attached" in oa.fetch_and_attach_pdf(ref)

    def test_too_many_hops(self, patch_http, monkeypatch):
        monkeypatch.setattr(oa, "check_url", lambda url: url)
        count = {"n": 0}

        def handler(request):
            count["n"] += 1
            return httpx.Response(302, headers={"location": f"https://hop.example/{count['n']}"})

        patch_http["handler"] = handler
        assert oa.fetch_and_attach_pdf(self._ref()) == "Download refused (too many redirects)."
        assert count["n"] == oa.MAX_HOPS + 1  # one candidate (arXiv), six requests, then stop

    def test_oversized_body_is_cut_off_while_streaming(self, patch_http, monkeypatch):
        monkeypatch.setattr(oa, "MAX_PDF_BYTES", 1000)
        served = {"bytes": 0}

        def body():
            for _ in range(100):
                served["bytes"] += 100
                yield b"%PDF" + b"x" * 96

        patch_http["handler"] = lambda request: httpx.Response(200, content=body())
        assert oa.fetch_and_attach_pdf(self._ref()) == "PDF larger than the 50 MB limit — skipped."
        assert served["bytes"] < 10_000, "the whole 10 KB body must not be read"

    def test_per_paper_wall_clock(self, patch_http, monkeypatch):
        monkeypatch.setattr(oa, "PAPER_BUDGET_SECONDS", -1)  # already out of time
        hosts = []

        def handler(request):
            hosts.append(request.url.host)
            return _fake_pdf(request)

        patch_http["handler"] = handler
        ref = self._ref()
        outcome = oa.find_pdf(ref)
        assert outcome["outcome"].startswith("Stopped (out of time") and not outcome["attached"]
        assert hosts == [], "no download is started once the paper's clock has run out"
        ref.refresh_from_db()
        assert ref.extra["oa_pdf"].startswith("Stopped")
