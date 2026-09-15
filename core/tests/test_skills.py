"""Atlas skills for Claude Code (Owner ask 2026-09-06)."""

import re
from pathlib import Path

import pytest

from core import skills

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.django_db


def _tool_names() -> set[str]:
    src = (ROOT / "mcp_server" / "server.py").read_text()
    return set(re.findall(r"@mcp\.tool\(\)\s*\ndef\s+([a-z_]+)\s*\(", src))


def test_every_skill_has_frontmatter_and_only_real_tools():
    rows = skills.list_skills()
    assert {r["name"] for r in rows} == {
        "atlas-daily",
        "atlas-literature",
        "atlas-writing",
        "atlas-plan",
        "atlas-import-projects",
    }
    tools = _tool_names()
    for row in rows:
        assert row["description"] and "Use when" in row["description"]
        text = (Path(row["path"]) / "SKILL.md").read_text()
        mentioned = set(re.findall(r"`([a-z_]+)`", text))
        fields = {"dry_run", "bibtex_key", "needs_metadata"}  # argument / field names
        unknown = {m for m in mentioned if "_" in m and m not in tools and m not in fields}
        assert not unknown, f"{row['name']} mentions tools that do not exist: {unknown}"


def test_install_copies_every_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "personal_skills_dir", lambda: tmp_path / ".claude" / "skills")
    names = skills.install_skills(dest=tmp_path / ".claude" / "skills")
    assert names == [
        "atlas-daily",
        "atlas-import-projects",
        "atlas-literature",
        "atlas-plan",
        "atlas-writing",
    ]
    assert (tmp_path / ".claude" / "skills" / "atlas-writing" / "SKILL.md").exists()
    assert all(r["installed"] and r["up_to_date"] for r in skills.list_skills())
    # re-install replaces (upgrade path)
    (tmp_path / ".claude" / "skills" / "atlas-daily" / "SKILL.md").write_text("stale")
    assert not [r for r in skills.list_skills() if r["name"] == "atlas-daily"][0]["up_to_date"]
    skills.install_skills(dest=tmp_path / ".claude" / "skills")
    assert all(r["up_to_date"] for r in skills.list_skills())


def test_connect_page_lists_skills_and_installs(client_logged_in, tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "personal_skills_dir", lambda: tmp_path / "skills")
    page = client_logged_in.get("/connect/claude/")
    assert page.status_code == 200
    body = page.content.decode()
    assert "/atlas-literature" in body and "not installed" in body
    response = client_logged_in.post("/connect/claude/skills/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200 and len(response.json()["installed"]) == 5
    assert (tmp_path / "skills" / "atlas-plan" / "SKILL.md").exists()
    assert b"installed" in client_logged_in.get("/connect/claude/").content
    assert client_logged_in.get("/connect/claude/skills/").status_code == 302  # POST only
