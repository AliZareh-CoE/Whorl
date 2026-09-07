"""#441: the multipart contract attach_manuscript_figure relies on, exercised against the API."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from writing.models import ManuscriptFile
from writing.tests.factories import ManuscriptFactory

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


@pytest.mark.django_db
def test_api_accepts_the_multipart_the_mcp_client_sends(client, settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    ms = ManuscriptFactory()
    r = client.post(
        "/api/v1/manuscript-files/",
        {
            "manuscript": ms.pk,
            "path": "figures/pilot.png",
            "kind": "asset",
            "asset": SimpleUploadedFile("pilot.png", PNG, content_type="image/png"),
        },
        HTTP_X_API_KEY="k",
    )
    assert r.status_code == 201, r.content
    row = ManuscriptFile.objects.get(pk=r.json()["id"])
    assert row.kind == "asset" and row.path == "figures/pilot.png" and row.asset
