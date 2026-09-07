"""The access log (#399): logins, failed logins, lockouts and rejected API keys."""

import pytest

from core import access
from core.models import AccessEvent

pytestmark = pytest.mark.django_db


def test_record_prunes_and_summarises(rf):
    request = rf.get("/", HTTP_USER_AGENT="Atlas-Test/1.0", REMOTE_ADDR="10.0.0.7")
    for _ in range(3):
        access.record("login_failed", request, detail="atlas")
    access.record("login_ok", request, detail="atlas")
    assert AccessEvent.objects.count() == 4
    top = access.recent(2)
    assert top[0]["kind"] == "login_ok" and top[0]["address"] == "10.0.0.7"
    s = access.summary()
    assert s["counts"]["login_failed"] == 3 and s["counts"]["login_ok"] == 1
    assert s["last_problem"]["kind"] == "login_failed"
    old = access.KEEP
    access.KEEP = 3
    try:
        access.record("login_ok", request)
        assert AccessEvent.objects.count() == 3
    finally:
        access.KEEP = old


def test_login_success_and_failure_are_recorded(client, django_user_model):
    django_user_model.objects.create_superuser("atlas", password="pw")
    client.post("/login/", {"username": "atlas", "password": "wrong"})
    assert AccessEvent.objects.filter(kind="login_failed", detail="atlas").exists()
    client.post("/login/", {"username": "atlas", "password": "pw"})
    assert AccessEvent.objects.filter(kind="login_ok", detail="atlas").exists()


def test_rejected_api_key_is_recorded_and_endpoint_lists_events(
    client, settings, django_user_model
):
    settings.ATLAS_API_KEY = "right"
    django_user_model.objects.create_superuser("atlas", password="pw")
    assert client.get("/api/v1/projects/", HTTP_X_API_KEY="wrong").status_code in (401, 403)
    bad = AccessEvent.objects.filter(kind="api_key_rejected").first()
    assert bad and bad.detail.startswith("/api/v1/projects/")
    data = client.get("/api/v1/access-events/?limit=5", HTTP_X_API_KEY="right").json()
    assert (
        data["events"][0]["kind"] == "api_key_rejected"
        and data["summary"]["counts"]["api_key_rejected"] == 1
    )
    # the access log is bookkeeping: it must not move the data version (ETags stay warm)
    from core import versioning

    before = versioning.data_version()
    access.record("login_ok", None)
    assert versioning.data_version() == before


def test_diagnostics_carry_the_access_summary(client, django_user_model):
    from core.diagnostics import as_text, collect

    access.record("api_key_rejected", None, detail="/api/v1/x/")
    report = collect()
    assert report["access"]["summary"]["counts"]["api_key_rejected"] == 1
    assert "rejected API keys" in as_text(report)
    src = open("frontend/src/app/pages/Diagnostics.tsx").read()
    assert 'data-testid="access-log"' in src
