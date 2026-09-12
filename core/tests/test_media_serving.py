"""Uploaded files are served by Django in every settings module (desktop has no proxy)."""

import pytest
from django.test import override_settings

pytestmark = pytest.mark.django_db


@pytest.fixture
def media_file(tmp_path):
    (tmp_path / "manuscripts" / "pdf").mkdir(parents=True)
    target = tmp_path / "manuscripts" / "pdf" / "manuscript-1.pdf"
    target.write_bytes(b"%PDF-1.4 fake")
    return tmp_path


def test_media_served_with_debug_off(client_logged_in, media_file):
    with override_settings(DEBUG=False, MEDIA_ROOT=media_file):
        response = client_logged_in.get("/media/manuscripts/pdf/manuscript-1.pdf")
    assert response.status_code == 200
    assert b"".join(response.streaming_content).startswith(b"%PDF")


def test_media_requires_login(client, media_file):
    with override_settings(DEBUG=False, MEDIA_ROOT=media_file):
        response = client.get("/media/manuscripts/pdf/manuscript-1.pdf")
    assert response.status_code == 302
    assert "/login/" in response["Location"]


def test_media_missing_is_404(client_logged_in, media_file):
    with override_settings(MEDIA_ROOT=media_file):
        assert client_logged_in.get("/media/nope.pdf").status_code == 404
