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


def test_doctor_warns_when_updater_pubkey_is_placeholder(settings, tmp_path):
    # #203: surface the one-time desktop signing step without failing the check.
    settings.MEDIA_ROOT = tmp_path
    settings.ATLAS_API_KEY = "a-real-key"
    output, code = run_doctor()
    # the shipped tauri.conf has the REPLACE_ME placeholder until the owner does D3
    # #303: the repo now carries the real public key with createUpdaterArtifacts off (CI flips
    # it on when the signing secret exists) — doctor reports that state as OK, not a warning.
    assert "Desktop auto-update public key set" in output
    assert code == 0


def test_doctor_fails_on_updater_misconfig(settings, tmp_path):
    # #206: createUpdaterArtifacts on + placeholder pubkey breaks the release build → fail.
    import json

    settings.MEDIA_ROOT = tmp_path / "media"
    settings.ATLAS_API_KEY = "a-real-key"
    settings.BASE_DIR = tmp_path
    (tmp_path / "static" / "css").mkdir(parents=True)
    (tmp_path / "static" / "css" / "app.css").write_text("/* built */")
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop" / "tauri.conf.json").write_text(
        json.dumps(
            {
                "bundle": {"createUpdaterArtifacts": True},
                "plugins": {"updater": {"pubkey": "REPLACE_ME_PLACEHOLDER"}},
            }
        )
    )
    output, code = run_doctor()
    assert "misconfigured" in output.lower()
    assert code == 1


def test_doctor_reports_configured_updater(settings, tmp_path):
    # #208: the _check_desktop helper's green path — a real (non-placeholder) pubkey reports OK.
    import json

    settings.MEDIA_ROOT = tmp_path / "media"
    settings.ATLAS_API_KEY = "a-real-key"
    settings.BASE_DIR = tmp_path
    (tmp_path / "static" / "css").mkdir(parents=True)
    (tmp_path / "static" / "css" / "app.css").write_text("/* built */")
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop" / "tauri.conf.json").write_text(
        json.dumps(
            {
                "bundle": {"createUpdaterArtifacts": True},
                "plugins": {"updater": {"pubkey": "dW50cnVzdGVkAAAArealkeybytes"}},
            }
        )
    )
    output, code = run_doctor()
    assert "Desktop auto-update signing configured" in output
    assert code == 0


def test_doctor_skips_desktop_when_no_tauri_conf(settings, tmp_path):
    # #208: with no desktop/tauri.conf.json the desktop section is silently skipped (not a fail).
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.ATLAS_API_KEY = "a-real-key"
    settings.BASE_DIR = tmp_path
    (tmp_path / "static" / "css").mkdir(parents=True)
    (tmp_path / "static" / "css" / "app.css").write_text("/* built */")
    output, code = run_doctor()
    assert "Desktop auto-update" not in output
    assert code == 0


def test_doctor_fails_on_unwritable_media(settings):
    settings.MEDIA_ROOT = "/proc/definitely-not-writable"
    settings.ATLAS_API_KEY = "k"
    output, code = run_doctor()
    assert "not writable" in output
    assert code == 1
