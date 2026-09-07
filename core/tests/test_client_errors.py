"""Front-end crash reports + the boot watchdog (#382): a blank window must say why."""

from pathlib import Path

import pytest
from django.conf import settings

from core import client_errors
from core.diagnostics import as_text, collect

BASE = Path(settings.BASE_DIR)


@pytest.fixture(autouse=True)
def _clean_cache():
    client_errors.clear()
    yield
    client_errors.clear()


def test_record_logs_and_keeps_recent(caplog):
    with caplog.at_level("ERROR", logger="atlas.client"):
        entry = client_errors.record(
            {
                "where": "boot",
                "url": "/",
                "errors": ["error: x is not defined @ /static/js/spa.js:1"],
                "version": "0.1.106",
            },
            user_agent="WebView2",
        )
    assert entry["where"] == "boot" and entry["errors"] == [
        "error: x is not defined @ /static/js/spa.js:1"
    ]
    assert "front-end boot error at / (0.1.106): error: x is not defined" in caplog.text
    for i in range(25):
        client_errors.record({"where": "window", "errors": [f"e{i}"]})
    kept = client_errors.recent()
    assert len(kept) == client_errors.KEEP and kept[0]["errors"] == ["e24"]


def test_report_endpoint_and_diagnostics(client, django_user_model):
    user = django_user_model.objects.create_superuser("owner", password="pw")
    client.force_login(user)
    response = client.post(
        "/api/v1/client-errors/",
        {
            "where": "render:page",
            "url": "/library",
            "errors": ["TypeError: boom", "at Library"],
            "version": "dev",
        },
        content_type="application/json",
    )
    assert response.status_code == 204
    report = collect()
    assert report["client_errors"][0]["where"] == "render:page"
    text = as_text(report)
    assert "front-end errors (most recent first):" in text and "TypeError: boom" in text
    # a malformed body never 500s — the report is best effort
    assert (
        client.post("/api/v1/client-errors/", "[1,2]", content_type="application/json").status_code
        == 204
    )


def test_shell_carries_the_boot_watchdog(client, django_user_model):
    user = django_user_model.objects.create_superuser("owner", password="pw")
    client.force_login(user)
    html = client.get("/").content.decode()
    assert 'data-version="' in html and "__atlasBootErrors" in html
    assert "/api/v1/client-errors/" in html and "boot-failure" in html
    assert 'onerror="window.__atlasScriptFailed' in html


def test_error_boundary_wired_and_static_recollected_clean():
    main = (BASE / "frontend/src/app/main.tsx").read_text()
    layout = (BASE / "frontend/src/app/Layout.tsx").read_text()
    assert '<ErrorBoundary scope="app">' in main and "__atlasMounted = true" in main
    assert '<ErrorBoundary scope="page" resetKey={location.pathname}>' in layout
    bundle = (BASE / "static/js/spa.js").read_text(errors="ignore")
    assert "render-failure" in bundle and "/client-errors/" in bundle
    run_desktop = (BASE / "core/management/commands/run_desktop.py").read_text()
    assert '"collectstatic", "--no-input", "--clear"' in run_desktop
    desktop = (BASE / "config/settings/desktop.py").read_text()
    assert "WHITENOISE_MAX_AGE = 0" in desktop
