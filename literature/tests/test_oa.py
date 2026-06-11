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

    def handler(request):
        assert request.url.host == "api.unpaywall.org", "must not follow the http URL"
        return httpx.Response(
            200, json={"best_oa_location": {"url_for_pdf": "http://evil.example/x.pdf"}}
        )

    patch_http["handler"] = handler
    assert oa.fetch_and_attach_pdf(ref) == "No open-access PDF found."
