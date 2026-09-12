"""#456 (backlog #122): the revision trim is stated in the History panel and adjustable."""

from pathlib import Path

import pytest
from django.conf import settings

from writing.models import ManuscriptFile, snapshot_manuscript
from writing.tests.factories import ManuscriptFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.fixture
def ms(db):
    m = ManuscriptFactory(title="Kept")
    ManuscriptFile.objects.create(
        manuscript=m, path="main.tex", content="x", kind="tex", is_main=True
    )
    return m


def test_trim_honours_the_per_manuscript_cap(ms):
    ms.auto_revisions_keep = 3
    ms.save(update_fields=["auto_revisions_keep"])
    snapshot_manuscript(ms, label="v1")
    for _ in range(6):
        snapshot_manuscript(ms)
    assert ms.revisions.filter(label="").count() == 3
    assert ms.revisions.exclude(label="").count() == 1  # labeled ones always stay


@pytest.mark.django_db
def test_endpoint_reports_retention_and_api_changes_it(client, owner, ms):
    client.login(username="owner", password="pw")
    snapshot_manuscript(ms, label="v1")
    snapshot_manuscript(ms)
    data = client.get(f"/projects/{ms.project.slug}/writing/{ms.pk}/revisions/").json()
    assert data["retention"] == {"keep": 50, "labeled": 1, "auto": 1}
    r = client.patch(
        f"/api/v1/manuscripts/{ms.pk}/",
        {"auto_revisions_keep": 10},
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 200 and r.json()["auto_revisions_keep"] == 10
    bad = client.patch(
        f"/api/v1/manuscripts/{ms.pk}/",
        {"auto_revisions_keep": 0},
        content_type="application/json",
        **HEADERS,
    )
    assert bad.status_code == 400
    data = client.get(f"/projects/{ms.project.slug}/writing/{ms.pk}/revisions/").json()
    assert data["retention"]["keep"] == 10


def test_history_panel_wiring():
    src = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Studio.tsx"
    ).read_text()
    for needle in (
        'data-testid="revision-retention"',
        'data-testid="retention-keep"',
        "auto_revisions_keep",
        "manuscriptId={m.id}",
    ):
        assert needle in src, needle
