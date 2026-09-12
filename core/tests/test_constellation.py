"""Observatory second pass (#387): the overview header carries the project's constellation."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_constellation_is_wired_into_the_overview():
    component = (BASE / "frontend/src/app/pages/project/Constellation.tsx").read_text()
    overview = (BASE / "frontend/src/app/pages/ProjectOverview.tsx").read_text()
    assert 'data-testid="constellation"' in component and "prefers-reduced-motion" in component
    assert "/graph/`" in component and "MAX_NODES" in component  # the graph API, capped
    assert "<Constellation slug={project.slug} accent={accent} />" in overview
    bundle = " ".join(
        p.read_text(errors="ignore")
        for p in (BASE / "static/js/islands").glob("ProjectOverview*.js")
    )
    assert "constellation" in bundle and "open the graph" in bundle


def test_orbit_is_wired_into_the_plan():
    """#392: the Plan header carries the orbit — phases as arcs, milestones as moons."""
    orbit = (BASE / "frontend/src/app/pages/plan/Orbit.tsx").read_text()
    plan = (BASE / "frontend/src/app/pages/Plan.tsx").read_text()
    assert 'data-testid="plan-orbit"' in orbit and 'data-testid="orbit-moon"' in orbit
    assert "<Orbit phases={data.phases} accent={accent}" in plan
    assert "id={`phase-${phase.id}`}" in plan  # the click target of an arc
    bundle = " ".join(
        p.read_text(errors="ignore") for p in (BASE / "static/js/islands").glob("Plan*.js")
    )
    assert "plan-orbit" in bundle
