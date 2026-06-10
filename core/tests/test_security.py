"""Owner idea #2: login throttling, upload validation, hardened settings."""

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core import security
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


class TestLoginThrottle:
    def test_lockout_after_max_failures(self, client, owner):
        url = reverse("login")
        for _ in range(security.LOGIN_MAX_FAILURES):
            response = client.post(url, {"username": "owner", "password": "wrong"})
            assert response.status_code == 200
        locked = client.post(url, {"username": "owner", "password": "wrong"})
        assert locked.status_code == 429
        assert b"Too many failed attempts" in locked.content
        # even the correct password is refused while locked
        still_locked = client.post(url, {"username": "owner", "password": "pw"})
        assert still_locked.status_code == 429

    def test_successful_login_resets_counter(self, client, owner):
        url = reverse("login")
        client.post(url, {"username": "owner", "password": "wrong"})
        ok = client.post(url, {"username": "owner", "password": "pw"})
        assert ok.status_code == 302
        assert cache.get("login-failures:127.0.0.1") is None

    def test_lockout_expires_with_cache(self, client, owner):
        url = reverse("login")
        for _ in range(security.LOGIN_MAX_FAILURES):
            client.post(url, {"username": "owner", "password": "wrong"})
        cache.clear()  # simulates the lockout window passing
        response = client.post(url, {"username": "owner", "password": "pw"})
        assert response.status_code == 302


class TestUploadValidation:
    def test_oversized_document_rejected_in_form(self, client_logged_in, monkeypatch):
        monkeypatch.setattr(security, "MAX_UPLOAD_BYTES", 10)
        project = ProjectFactory()
        response = client_logged_in.post(
            reverse("documents:upload", args=[project.slug]),
            {
                "title": "Too big",
                "file": SimpleUploadedFile("big.bin", b"x" * 11),
                "description": "",
            },
        )
        assert response.status_code == 200
        assert b"limit" in response.content
        assert project.documents.count() == 0

    def test_reference_pdf_must_be_pdf(self, client_logged_in):
        from literature.tests.factories import ReferenceFactory

        ref = ReferenceFactory()
        response = client_logged_in.post(
            reverse("literature:edit", args=[ref.pk]),
            {
                "entry_type": "article",
                "title": ref.title,
                "authors_text": "",
                "doi": "",
                "arxiv_id": "",
                "url": "",
                "abstract": "",
                "pdf": SimpleUploadedFile("paper.exe", b"MZ fake"),
            },
        )
        assert response.status_code == 200
        assert b"Only .pdf files" in response.content

    def test_oversized_upload_rejected_in_api(self, client, owner, settings, monkeypatch):
        settings.ATLAS_API_KEY = "k"
        monkeypatch.setattr(security, "MAX_UPLOAD_BYTES", 10)
        project = ProjectFactory()
        response = client.post(
            "/api/v1/documents/",
            {
                "project": project.slug,
                "title": "Too big",
                "file": SimpleUploadedFile("big.bin", b"x" * 11),
            },
            HTTP_X_API_KEY="k",
        )
        assert response.status_code == 400
        assert "limit" in response.json()["file"][0]


class TestHardenedSettings:
    def test_prod_settings_flags(self):
        import importlib

        prod = importlib.import_module("config.settings.prod")
        assert prod.SECURE_HSTS_SECONDS >= 31536000
        assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
        assert prod.SECURE_SSL_REDIRECT is True
        assert prod.SESSION_COOKIE_SECURE is True
        assert prod.CSRF_COOKIE_SECURE is True
        assert prod.DEBUG is False

    def test_clickjacking_header_on_pages(self, client_logged_in):
        response = client_logged_in.get(reverse("core:dashboard"))
        assert response.headers["X-Frame-Options"] == "DENY"
