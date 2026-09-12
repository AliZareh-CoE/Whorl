"""Atlas skills for Claude Code (Owner ask 2026-09-06: "claude might need some skills").

Skills are Markdown playbooks Claude Code loads on demand (`~/.claude/skills/<name>/SKILL.md`).
Atlas ships four in `mcp_server/skills/` — daily loop, literature, writing, plans — each a
tool-by-tool recipe over the MCP server. `install_skills` copies them into the user's
personal skills directory so the terminal dock's "Claude" tab has them from the first prompt.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent / "mcp_server" / "skills"
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def personal_skills_dir() -> Path:
    return Path.home() / ".claude" / "skills"


def _meta(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    meta = {"name": skill_md.parent.name, "description": ""}
    if match:
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            if key.strip() in ("name", "description"):
                meta[key.strip()] = value.strip()
    return meta


def list_skills(source: Path = SKILLS_DIR) -> list[dict]:
    """Every shipped skill with its name, description, source folder and install state."""
    rows = []
    for skill_md in sorted(source.glob("*/SKILL.md")):
        meta = _meta(skill_md)
        target = personal_skills_dir() / skill_md.parent.name / "SKILL.md"
        rows.append(
            {
                **meta,
                "folder": skill_md.parent.name,
                "path": str(skill_md.parent),
                "installed": target.exists(),
                "up_to_date": target.exists()
                and target.read_text(encoding="utf-8") == skill_md.read_text(encoding="utf-8"),
            }
        )
    return rows


def install_skills(source: Path = SKILLS_DIR, dest: Path | None = None) -> list[str]:
    """Copy every shipped skill folder into ``dest`` (default: ~/.claude/skills). Returns the
    installed folder names. Existing copies are replaced so upgrades ship new playbooks."""
    dest = dest or personal_skills_dir()
    dest.mkdir(parents=True, exist_ok=True)
    installed = []
    for folder in sorted(p for p in source.iterdir() if (p / "SKILL.md").exists()):
        target = dest / folder.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(folder, target)
        installed.append(folder.name)
    return installed
