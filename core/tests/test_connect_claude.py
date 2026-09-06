"""The "Connect Claude Code" page hands the user a working `claude mcp add` line."""

import json
import sys

import pytest
from django.urls import reverse


@pytest.fixture
def owner(client, django_user_model):
    user = django_user_model.objects.create_superuser("owner", password="pw")
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_page_requires_login(client):
    response = client.get(reverse("core:connect_claude"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_dev_install_passes_url_and_key_explicitly(owner, settings, monkeypatch):
    monkeypatch.delenv("ATLAS_MCP_BIN", raising=False)
    settings.ATLAS_API_KEY = "sekret-key"
    response = owner.get(reverse("core:connect_claude"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Connect Claude Code" in html
    assert "Development / server install" in html
    assert "claude mcp add atlas" in html
    assert "--env ATLAS_API_URL=http://testserver" in html
    assert "--env ATLAS_API_KEY=sekret-key" in html
    assert "-m mcp_server.server" in html
    assert sys.executable in html


@pytest.mark.django_db
def test_desktop_install_needs_no_secrets_in_the_command(owner, settings, monkeypatch, tmp_path):
    # the Tauri shell hands the server the bundled atlas-mcp path; it discovers URL + key itself
    monkeypatch.setenv("ATLAS_MCP_BIN", "/opt/Atlas/atlas-mcp/atlas-mcp")
    monkeypatch.delenv("ATLAS_DATA_DIR", raising=False)
    settings.ATLAS_API_KEY = "desktop-key"
    response = owner.get(reverse("core:connect_claude"))
    html = response.content.decode()
    assert "Desktop build detected" in html
    assert "claude mcp add atlas -- /opt/Atlas/atlas-mcp/atlas-mcp" in html
    assert "--env" not in html.split("Other MCP clients")[0]  # the one-liner carries no env
    assert "desktop-key" in html  # …but the key is still shown for other clients


@pytest.mark.django_db
def test_desktop_install_with_custom_data_dir_passes_it_along(
    owner, settings, monkeypatch, tmp_path
):
    monkeypatch.setenv("ATLAS_MCP_BIN", "/opt/Atlas/atlas-mcp/atlas-mcp")
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path))
    settings.ATLAS_API_KEY = "k"
    html = owner.get(reverse("core:connect_claude")).content.decode()
    assert f"--env ATLAS_DATA_DIR={tmp_path}" in html


@pytest.mark.django_db
def test_paths_with_spaces_are_quoted(owner, settings, monkeypatch):
    monkeypatch.setenv("ATLAS_MCP_BIN", "/Applications/Atlas Research/atlas-mcp")
    monkeypatch.delenv("ATLAS_DATA_DIR", raising=False)
    settings.ATLAS_API_KEY = "k"
    html = owner.get(reverse("core:connect_claude")).content.decode()
    assert "-- &#x27;/Applications/Atlas Research/atlas-mcp&#x27;" in html or (
        "-- '/Applications/Atlas Research/atlas-mcp'" in html
    )


@pytest.mark.django_db
def test_mcp_json_snippet_is_valid(owner, settings, monkeypatch):
    from core.mcp_connect import connection_info

    monkeypatch.setenv("ATLAS_MCP_BIN", "/opt/Atlas/atlas-mcp/atlas-mcp")
    monkeypatch.delenv("ATLAS_DATA_DIR", raising=False)
    settings.ATLAS_API_KEY = "k"

    class Req:
        scheme = "http"

        def get_host(self):
            return "127.0.0.1:8123"

    info = connection_info(Req())
    snippet = json.loads(info["mcp_json"])
    assert snippet["mcpServers"]["atlas"]["command"] == "/opt/Atlas/atlas-mcp/atlas-mcp"
    assert snippet["mcpServers"]["atlas"]["args"] == []
    assert info["api_url"] == "http://127.0.0.1:8123"


@pytest.mark.django_db
def test_missing_api_key_is_explained(owner, settings, monkeypatch):
    monkeypatch.delenv("ATLAS_MCP_BIN", raising=False)
    settings.ATLAS_API_KEY = ""
    html = owner.get(reverse("core:connect_claude")).content.decode()
    assert "No API key is configured" in html


@pytest.mark.django_db
def test_sidebars_link_to_the_page(owner):
    html = owner.get(reverse("core:dashboard")).content.decode()
    assert reverse("core:connect_claude") in html
    from pathlib import Path

    layout = Path("frontend/src/app/Layout.tsx").read_text()
    assert 'href="/connect/claude/"' in layout
