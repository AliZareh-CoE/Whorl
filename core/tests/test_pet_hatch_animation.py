"""#461 (backlog #132): a stage change plays a one-time hatch transition."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_creature_animates_a_stage_change_once():
    src = (BASE / "frontend" / "src" / "app" / "pet" / "Creature.tsx").read_text()
    for needle in ("atlas-pet-stage", "mochi-egg-crack", "mochi-born", "STAGE_ORDER", "hatching"):
        assert needle in src, needle
    css = (BASE / "assets" / "css" / "app.css").read_text()
    for needle in (
        "@keyframes mochi-crack",
        "@keyframes mochi-pop",
        ".mochi-egg-crack",
        ".mochi-born",
    ):
        assert needle in css, needle
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "mochi-egg-crack" in chunks
