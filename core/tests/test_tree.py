"""Owner idea #13: the project tree grows with real progress."""

import pytest
from django.template import Context, Template
from django.urls import reverse

from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def render_tree(percent, seed=1):
    template = Template("{% load project_tree %}{% project_tree percent '#4f46e5' 100 seed %}")
    return template.render(Context({"percent": percent, "seed": seed}))


class TestTreeStages:
    def test_stage_thresholds(self):
        assert 'data-stage="sprout"' in render_tree(0)
        assert 'data-stage="sapling"' in render_tree(15)
        assert 'data-stage="young"' in render_tree(50)
        assert 'data-stage="mature"' in render_tree(85)
        assert 'data-stage="bloom"' in render_tree(100)

    def test_bloom_has_blossoms_sprout_does_not(self):
        assert render_tree(100).count('fill="#fff"') >= 4
        assert 'fill="#fff"' not in render_tree(0)

    def test_deterministic_per_seed(self):
        assert render_tree(60, seed=7) == render_tree(60, seed=7)
        assert render_tree(60, seed=7) != render_tree(60, seed=8)

    def test_clamps_out_of_range(self):
        assert 'data-stage="bloom"' in render_tree(150)
        assert 'data-stage="sprout"' in render_tree(-5)
        assert 'data-stage="sprout"' in render_tree(None)


class TestTreeSurfaces:
    def test_overview_and_index_render_trees(self, client_logged_in):
        from django.utils import timezone

        from plans.tests.factories import MilestoneFactory, PhaseFactory

        project = ProjectFactory()
        phase = PhaseFactory(project=project)
        MilestoneFactory(phase=phase, completed_at=timezone.now())
        MilestoneFactory(phase=phase)

        overview = client_logged_in.get(project.get_absolute_url())
        assert b'data-stage="young"' in overview.content  # 50%

        index = client_logged_in.get(reverse("projects:list"))
        assert b"Project tree" in index.content
