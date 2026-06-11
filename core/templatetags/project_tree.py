"""The project tree (Owner ideas #13 + #17): a polished SVG that grows with real progress.

Eight stages from seed to bloom. Everything interpolates with percent — trunk height
and taper, branch count, canopy spread and density — so growth feels continuous, and
every tree is deterministic per `seed` so a project always looks like itself.
"""

import math
import random

from django import template

register = template.Library()

STAGES = [  # (min percent, name)
    (0, "seed"),
    (5, "sprout"),
    (15, "seedling"),
    (30, "sapling"),
    (45, "young"),
    (60, "established"),
    (75, "mature"),
    (100, "bloom"),
]

GROUND_Y = 92


def _stage(percent: int) -> str:
    name = STAGES[0][1]
    for threshold, stage_name in STAGES:
        if percent >= threshold:
            name = stage_name
    return name


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _trunk_path(lean: float, height: float, base_w: float, top_w: float) -> str:
    """A filled, gently curved, tapered trunk — not a stroked line."""
    top_x, top_y = 50 + lean, GROUND_Y - height
    mid_x = 50 + lean * 0.45
    mid_y = GROUND_Y - height * 0.55
    points = [
        f"M {50 - base_w:.1f} {GROUND_Y}",
        f"C {50 - base_w * 0.6:.1f} {GROUND_Y - height * 0.3:.1f},"
        f" {mid_x - top_w * 1.4:.1f} {mid_y:.1f},"
        f" {top_x - top_w:.1f} {top_y:.1f}",
        f"L {top_x + top_w:.1f} {top_y:.1f}",
        f"C {mid_x + top_w * 1.4:.1f} {mid_y:.1f},"
        f" {50 + base_w * 0.6:.1f} {GROUND_Y - height * 0.3:.1f},"
        f" {50 + base_w:.1f} {GROUND_Y}",
        "Z",
    ]
    return " ".join(points)


def _branches(rng: random.Random, lean: float, height: float, t: float) -> list[dict]:
    """Tapered limbs leaving the trunk at staggered heights, alternating sides."""
    count = int(_lerp(0, 5, max(0.0, (t - 0.3) / 0.7)))
    branches = []
    for i in range(count):
        frac = 0.45 + 0.42 * (i / max(count - 1, 1))  # attach between 45% and 87% up
        ax = 50 + lean * frac
        ay = GROUND_Y - height * frac
        side = -1 if i % 2 == 0 else 1
        length = _lerp(7, 13, t) * (1 - 0.35 * frac) * rng.uniform(0.85, 1.15)
        ex = ax + side * length
        ey = ay - length * rng.uniform(0.45, 0.7)
        branches.append(
            {
                "d": f"M {ax:.1f} {ay:.1f} Q {ax + side * length * 0.55:.1f} "
                f"{ay - length * 0.15:.1f} {ex:.1f} {ey:.1f}",
                "w": round(_lerp(1.0, 2.2, t) * (1 - 0.4 * frac), 2),
                "tip_x": ex,
                "tip_y": ey,
            }
        )
    return branches


def _canopy(rng, cx, cy, t, tips) -> list[dict]:
    """Three depth layers of clusters: big light backdrop, mid body, small dark front."""
    spread_x = _lerp(7, 21, t)
    spread_y = spread_x * 0.62
    circles = []
    layers = [  # (count base, count growth, radius lo-hi, opacity, y-shift)
        (3, 5, (0.42, 0.58), 0.16, -1.5),
        (4, 6, (0.30, 0.44), 0.32, 0.0),
        (3, 6, (0.18, 0.30), 0.52, 1.0),
    ]
    for base, growth, (r_lo, r_hi), opacity, dy in layers:
        for _ in range(base + int(growth * t)):
            angle = rng.uniform(0, 2 * math.pi)
            reach = math.sqrt(rng.random())  # denser toward the middle
            circles.append(
                {
                    "cx": round(cx + spread_x * reach * math.cos(angle), 1),
                    "cy": round(cy + dy - abs(spread_y * reach * math.sin(angle)), 1),
                    "r": round(spread_x * rng.uniform(r_lo, r_hi), 1),
                    "o": opacity,
                }
            )
    # small tufts where branches end, so limbs read as part of the tree
    for tip in tips:
        circles.append(
            {
                "cx": round(tip["tip_x"], 1),
                "cy": round(tip["tip_y"] - 1, 1),
                "r": round(spread_x * rng.uniform(0.22, 0.34), 1),
                "o": 0.4,
            }
        )
    return circles


@register.inclusion_tag("core/_tree.html")
def project_tree(percent, color="#4f46e5", size=120, seed=0):
    """Render the growth-stage tree. Deterministic per project via `seed`."""
    percent = max(0, min(100, int(percent or 0)))
    stage = _stage(percent)
    rng = random.Random(seed)
    t = percent / 100

    lean = rng.uniform(-3.5, 3.5)  # each project's tree has its own posture
    height = _lerp(10, 56, t)
    canopy_x, canopy_y = 50 + lean, GROUND_Y - height - 1

    context = {
        "percent": percent,
        "stage": stage,
        "color": color,
        "size": size,
        "ground_y": GROUND_Y,
        "canopy_y": round(canopy_y, 1),
    }

    if stage in ("seed", "sprout", "seedling"):
        stem_h = {"seed": 0, "sprout": 7, "seedling": 13}[stage]
        context.update(
            {
                "stem_top": GROUND_Y - stem_h,
                "leaf_l": GROUND_Y - stem_h + 2,
                "leaf_r": GROUND_Y - stem_h + 4,
                "puff": (
                    [
                        {
                            "cx": round(50 + rng.uniform(-2.5, 2.5), 1),
                            "cy": round(GROUND_Y - stem_h - rng.uniform(0, 3), 1),
                            "r": round(rng.uniform(2.2, 3.6), 1),
                            "o": 0.4,
                        }
                        for _ in range(4)
                    ]
                    if stage == "seedling"
                    else []
                ),
            }
        )
        return context

    branches = _branches(rng, lean, height, t)
    foliage = _canopy(rng, canopy_x, canopy_y, t, branches)
    blossoms = []
    if stage == "bloom":
        front = [c for c in foliage if c["o"] >= 0.4]
        for circle in rng.sample(front, min(7, len(front))):
            blossoms.append(
                {
                    "cx": round(circle["cx"] + rng.uniform(-2, 2), 1),
                    "cy": round(circle["cy"] + rng.uniform(-2, 2), 1),
                }
            )

    context.update(
        {
            "trunk_path": _trunk_path(lean, height, _lerp(1.6, 3.4, t), _lerp(0.7, 1.1, t)),
            "branches": branches,
            "foliage": foliage,
            "blossoms": blossoms,
            "roots": [
                f"M {50 - 2:.1f} {GROUND_Y} Q {50 - 6:.1f} {GROUND_Y + 0.5} {50 - 9:.1f} {GROUND_Y + 1.5}",
                f"M {50 + 2:.1f} {GROUND_Y} Q {50 + 6:.1f} {GROUND_Y + 0.5} {50 + 9:.1f} {GROUND_Y + 1.5}",
            ]
            if t >= 0.45
            else [],
        }
    )
    return context
