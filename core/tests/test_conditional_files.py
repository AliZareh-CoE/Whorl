"""#434 (backlog #54): served files carry validators and answer conditional GETs with 304."""

import pytest
from django.core.files.base import ContentFile

from documents.tests.factories import DocumentFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
PNG = (
    b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 13 + b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(client, django_user_model):
    user = django_user_model.objects.create_superuser("owner", password="pw")
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_download_preview_and_raw_revalidate(client, owner):
    doc = DocumentFactory(
        file=ContentFile(PNG, name="fig.png"), content_type="image/png", title="Figure"
    )
    slug = doc.project.slug
    urls = [
        f"/projects/{slug}/documents/{doc.pk}/download/",
        f"/projects/{slug}/documents/{doc.pk}/preview/",
        f"/api/v1/documents/{doc.pk}/raw/",
    ]
    for url in urls:
        first = client.get(url, **HEADERS)
        assert first.status_code == 200, url
        assert first["Cache-Control"] == "private, max-age=86400"
        assert first["ETag"].startswith('"') and first["Last-Modified"]
        assert first["X-Content-Type-Options"] == "nosniff"
        by_etag = client.get(url, HTTP_IF_NONE_MATCH=first["ETag"], **HEADERS)
        assert by_etag.status_code == 304 and by_etag["ETag"] == first["ETag"], url
        assert not by_etag.content
        by_date = client.get(url, HTTP_IF_MODIFIED_SINCE=first["Last-Modified"], **HEADERS)
        assert by_date.status_code == 304, url
        stale = client.get(url, HTTP_IF_NONE_MATCH='"0-0"', **HEADERS)
        assert stale.status_code == 200, url
        old = client.get(url, HTTP_IF_MODIFIED_SINCE="Sat, 01 Jan 2000 00:00:00 GMT", **HEADERS)
        assert old.status_code == 200, url


@pytest.mark.django_db
def test_raw_still_refuses_mislabeled_files(client, owner):
    """The 304 path must never bypass the magic-byte check (#250)."""
    doc = DocumentFactory(
        file=ContentFile(b"<html>boo</html>", name="fake.png"), content_type="image/png"
    )
    r = client.get(f"/api/v1/documents/{doc.pk}/raw/", HTTP_IF_NONE_MATCH="*", **HEADERS)
    assert r.status_code == 404
