"""Owner idea #1 remainder: conditional GETs — ETags + 304s on the API."""

import pytest

from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings):
    settings.ATLAS_API_KEY = KEY


class TestETags:
    def test_list_returns_etag_then_304(self, client, owner):
        ProjectFactory()
        first = client.get("/api/v1/projects/", **HEADERS)
        etag = first["ETag"]
        assert etag.startswith('W/"')
        second = client.get("/api/v1/projects/", HTTP_IF_NONE_MATCH=etag, **HEADERS)
        assert second.status_code == 304
        assert not second.content

    def test_etag_changes_when_data_changes(self, client, owner):
        project = ProjectFactory()
        etag = client.get("/api/v1/projects/", **HEADERS)["ETag"]
        project.name = "Renamed"
        project.save()
        response = client.get("/api/v1/projects/", HTTP_IF_NONE_MATCH=etag, **HEADERS)
        assert response.status_code == 200
        assert response["ETag"] != etag

    def test_etag_varies_with_query_params(self, client, owner):
        ProjectFactory()
        plain = client.get("/api/v1/projects/", **HEADERS)["ETag"]
        paged = client.get("/api/v1/projects/?page=1", **HEADERS)["ETag"]
        assert plain != paged

    def test_retrieve_304(self, client, owner):
        project = ProjectFactory()
        first = client.get(f"/api/v1/projects/{project.slug}/", **HEADERS)
        second = client.get(
            f"/api/v1/projects/{project.slug}/", HTTP_IF_NONE_MATCH=first["ETag"], **HEADERS
        )
        assert second.status_code == 304

    def test_download_has_cache_control(self, client_logged_in):
        from django.urls import reverse

        from documents.tests.factories import DocumentFactory

        doc = DocumentFactory()
        response = client_logged_in.get(
            reverse("documents:download", args=[doc.project.slug, doc.pk])
        )
        assert "max-age=86400" in response["Cache-Control"]
