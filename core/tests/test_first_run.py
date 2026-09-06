"""First-run experience (2026-09-06): the desktop login hint and the demo loader."""

import pytest
from django.contrib.auth import get_user_model

from projects.models import Project

pytestmark = pytest.mark.django_db


def test_login_hint_only_on_desktop_with_the_default_password(client, settings):
    get_user_model().objects.create_superuser("atlas", "", "atlas")
    settings.ATLAS_DESKTOP = False
    assert b"default-login-hint" not in client.get("/login/").content
    settings.ATLAS_DESKTOP = True
    assert b"default-login-hint" in client.get("/login/").content
    user = get_user_model().objects.get(username="atlas")
    user.set_password("something-else")
    user.save()
    assert b"default-login-hint" not in client.get("/login/").content


def test_demo_loader_seeds_once(client_logged_in):
    assert client_logged_in.get("/api/v1/demo/").json() == {"projects": 0}
    out = client_logged_in.post("/api/v1/demo/").json()
    assert out["project"] and out["projects"] == 1
    client_logged_in.post("/api/v1/demo/")
    assert Project.objects.count() == 1  # idempotent


def test_doctor_reports_engine_and_feed(monkeypatch, capsys):
    from django.core.management import call_command

    from core.management.commands import doctor
    from writing import compile as compile_mod

    monkeypatch.setattr(compile_mod, "tectonic_path", lambda: None)
    monkeypatch.setattr(
        doctor.Command,
        "_check_update_feed",
        lambda self, base: self.warn("update feed unreachable (stub)"),
    )
    call_command("doctor")
    out = capsys.readouterr().out
    assert "Tectonic missing" in out and "update feed unreachable" in out


def test_deleting_a_project_with_a_manuscript_leaves_no_orphan_folders():
    """Regression: the manuscript-file mirror re-created its folder during the cascade."""
    from django.db import connection

    from documents.models import Folder
    from projects.tests.factories import ProjectFactory
    from writing.models import Manuscript

    project = ProjectFactory()
    m = Manuscript.objects.create(project=project, title="M", latex_source="x")
    m.ensure_main_file()
    assert Folder.objects.filter(project=project).exists()
    pid = project.pk
    project.delete()
    assert not Folder.objects.filter(project_id=pid).exists()
    connection.check_constraints()  # deferred FK checks run now, not at teardown
