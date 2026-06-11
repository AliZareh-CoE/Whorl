"""Backlog #10: OpenAlex discover-similar."""

import json

import httpx
import pytest
from django.urls import reverse

from literature import discover

from .factories import ReferenceFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def patch_http(monkeypatch):
    state = {"handler": None}
    real_client = httpx.Client

    def client_factory(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(state["handler"]))

    monkeypatch.setattr(discover.httpx, "Client", client_factory)
    return state


def openalex_handler(request):
    url = str(request.url)
    if url.startswith("https://api.openalex.org/works/W1?"):
        return httpx.Response(
            200,
            content=json.dumps(
                {"related_works": ["https://openalex.org/W2", "https://openalex.org/W3"]}
            ),
        )
    if "filter=openalex_id" in url or "openalex_id%3A" in url:
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "results": [
                        {
                            "id": "https://openalex.org/W2",
                            "title": "A neighbor paper",
                            "doi": "https://doi.org/10.1/neighbor",
                            "publication_year": 2021,
                            "cited_by_count": 7,
                            "authorships": [{"author": {"display_name": "Nina Neighbor"}}],
                        },
                        {
                            "id": "https://openalex.org/W3",
                            "title": "Already owned",
                            "doi": "https://doi.org/10.1/owned",
                            "publication_year": 2020,
                            "cited_by_count": 3,
                            "authorships": [],
                        },
                    ]
                }
            ),
        )
    return httpx.Response(404)


class TestDiscoverService:
    def test_returns_neighbors_excluding_library(self, patch_http):
        anchor = ReferenceFactory(openalex_id="W1")
        ReferenceFactory(doi="10.1/owned")  # already in library
        patch_http["handler"] = openalex_handler
        results = discover.discover_similar(anchor)
        assert len(results) == 1
        assert results[0]["doi"] == "10.1/neighbor"
        assert results[0]["first_author"] == "Nina Neighbor"

    def test_no_identifiers_returns_empty(self, patch_http):
        anchor = ReferenceFactory(doi=None, openalex_id="")
        patch_http["handler"] = lambda request: httpx.Response(404)
        assert discover.discover_similar(anchor) == []

    def test_resolves_work_id_from_doi(self, patch_http):
        anchor = ReferenceFactory(doi="10.1/anchor", openalex_id="")

        def handler(request):
            url = str(request.url)
            if "doi:10.1/anchor" in url:
                return httpx.Response(200, content=json.dumps({"id": "https://openalex.org/W1"}))
            return openalex_handler(request)

        patch_http["handler"] = handler
        results = discover.discover_similar(anchor)
        assert results and results[0]["doi"] == "10.1/neighbor"


class TestDiscoverViews:
    def test_panel_renders_results(self, client_logged_in, monkeypatch):
        anchor = ReferenceFactory(openalex_id="W1")
        monkeypatch.setattr(
            "literature.discover.discover_similar",
            lambda ref: [
                {
                    "doi": "10.1/n",
                    "title": "Neighbor",
                    "year": 2021,
                    "citations": 7,
                    "first_author": "N",
                }
            ],
        )
        response = client_logged_in.get(reverse("literature:discover", args=[anchor.pk]))
        content = response.content.decode()
        assert "Neighbor" in content
        assert "discover-add" in content

    def test_panel_handles_network_failure(self, client_logged_in, monkeypatch):
        anchor = ReferenceFactory()

        def boom(ref):
            raise RuntimeError("net down")

        monkeypatch.setattr("literature.discover.discover_similar", boom)
        response = client_logged_in.get(reverse("literature:discover", args=[anchor.pk]))
        assert b"unreachable" in response.content

    def test_add_endpoint(self, client_logged_in, monkeypatch):
        anchor = ReferenceFactory()
        new_ref = ReferenceFactory(bibtex_key="found2021paper")
        monkeypatch.setattr(
            "literature.views.services.add_reference_by_identifier",
            lambda identifier: (new_ref, True),
        )
        response = client_logged_in.post(
            reverse("literature:discover_add", args=[anchor.pk]), {"doi": "10.1/n"}
        )
        data = response.json()
        assert response.status_code == 200
        assert data["bibtex_key"] == "found2021paper"
