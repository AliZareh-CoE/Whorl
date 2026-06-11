"""Backlog #16: the doctor health-check command."""

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def run_doctor(**kwargs):
    import io

    out = io.StringIO()
    try:
        call_command("doctor", stdout=out, **kwargs)
        code = 0
    except SystemExit as exc:
        code = exc.code
    return out.getvalue(), code


def test_doctor_green_in_test_env(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.ATLAS_API_KEY = "a-real-key"
    output, code = run_doctor()
    assert "database reachable" in output
    assert "migrations up to date" in output
    assert "immediate mode" in output  # worker checks skipped under test settings
    assert code == 0


def test_doctor_warns_on_default_api_key(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.ATLAS_API_KEY = "change-me-api-key"
    output, code = run_doctor()
    assert "rotate_api_key" in output
    assert code == 0  # warnings don't fail the check


def test_doctor_fails_on_unwritable_media(settings):
    settings.MEDIA_ROOT = "/proc/definitely-not-writable"
    settings.ATLAS_API_KEY = "k"
    output, code = run_doctor()
    assert "not writable" in output
    assert code == 1
