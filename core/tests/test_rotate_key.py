"""Owner idea #2 remainder: API-key rotation command."""

import pytest
from django.core.management import CommandError, call_command

pytestmark = pytest.mark.django_db


def test_rotates_existing_key_preserving_other_lines(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("DEBUG=true\nATLAS_API_KEY=old-key-value\nDATABASE_URL=postgres://x\n")
    call_command("rotate_api_key", env_file=str(env))
    content = env.read_text()
    assert "old-key-value" not in content
    assert "DEBUG=true" in content
    assert "DATABASE_URL=postgres://x" in content
    key_line = next(line for line in content.splitlines() if line.startswith("ATLAS_API_KEY="))
    new_key = key_line.split("=", 1)[1]
    assert len(new_key) >= 40


def test_appends_when_key_missing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DEBUG=true\n")
    call_command("rotate_api_key", env_file=str(env))
    assert "ATLAS_API_KEY=" in env.read_text()


def test_two_rotations_differ(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ATLAS_API_KEY=seed\n")
    call_command("rotate_api_key", env_file=str(env))
    first = env.read_text()
    call_command("rotate_api_key", env_file=str(env))
    assert env.read_text() != first


def test_missing_env_file_errors(tmp_path):
    with pytest.raises(CommandError, match="does not exist"):
        call_command("rotate_api_key", env_file=str(tmp_path / "nope.env"))
