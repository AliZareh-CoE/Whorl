"""The diagnostics report (2026-09-06)."""

import pytest

from core import diagnostics

pytestmark = pytest.mark.django_db


def test_report_and_text(client_logged_in, monkeypatch, tmp_path, settings):
    from writing import compile as compile_mod
    from writing.models import Manuscript

    monkeypatch.setattr(compile_mod, "tectonic_path", lambda: tmp_path / "tectonic")
    settings.DATA_DIR = tmp_path
    (tmp_path / "atlas-server.log").write_text("line one\nAtlas is running\n")
    from projects.tests.factories import ProjectFactory

    Manuscript.objects.create(
        project=ProjectFactory(),
        title="Broken",
        compile_status="failed",
        compile_log="! Undefined control sequence.",
    )
    data = client_logged_in.get("/api/v1/diagnostics/").json()
    assert data["engine"].endswith("tectonic") and data["jobs"].startswith("in-process")
    assert data["last_failed_compile"]["title"] == "Broken"
    assert "Atlas is running" in data["server_log"]
    assert [r["status"] for r in data["update_feed"]] == [
        None
    ] * 3  # three endpoints; no network by default
    text = data["text"]
    assert (
        "LaTeX engine:" in text
        and "Undefined control sequence" in text
        and "server log (tail)" in text
    )
    assert diagnostics.as_text(diagnostics.collect())  # standalone call works too
