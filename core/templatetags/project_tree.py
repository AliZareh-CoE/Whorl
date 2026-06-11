"""The project tree (Owner idea #13): an SVG that grows with real progress."""

import math
import random

from django import template

register = template.Library()


def _stage(percent: int) -> str:
    if percent >= 100:
        return "bloom"
    if percent >= 70:
        return "mature"
    if percent >= 40:
        return "young"
    if percent >= 10:
        return "sapling"
    return "sprout"


@register.inclusion_tag("core/_tree.html")
def project_tree(percent, color="#4f46e5", size=120, seed=0):
    """Render the growth-stage tree. Deterministic per project via `seed`."""
    percent = max(0, min(100, int(percent or 0)))
    stage = _stage(percent)
    rng = random.Random(seed)

    # trunk grows 18→52 px with progress
    trunk_height = 18 + 34 * percent / 100
    canopy_y = 92 - trunk_height

    foliage = []
    if stage != "sprout":
        count = {"sapling": 3, "young": 6, "mature": 9, "bloom": 9}[stage]
        spread = {"sapling": 9, "young": 14, "mature": 18, "bloom": 18}[stage]
        for i in range(count):
            angle = (i / count) * 2 * math.pi + rng.random() * 0.8
            radius = spread * (0.35 + 0.65 * rng.random())
            foliage.append(
                {
                    "cx": round(50 + radius * math.cos(angle), 1),
                    "cy": round(canopy_y - abs(radius * math.sin(angle)) * 0.9, 1),
                    "r": round(
                        6 + 6 * rng.random() + (2 if stage in ("mature", "bloom") else 0), 1
                    ),
                    "opacity": round(0.25 + 0.5 * rng.random(), 2),
                }
            )

    blossoms = []
    if stage == "bloom":
        for circle in foliage[:6]:
            blossoms.append(
                {
                    "cx": round(circle["cx"] + rng.uniform(-3, 3), 1),
                    "cy": round(circle["cy"] + rng.uniform(-3, 3), 1),
                }
            )

    return {
        "percent": percent,
        "stage": stage,
        "color": color,
        "size": size,
        "trunk_height": round(trunk_height, 1),
        "canopy_y": round(canopy_y, 1),
        "foliage": foliage,
        "blossoms": blossoms,
        "branch": stage in ("young", "mature", "bloom"),
    }
