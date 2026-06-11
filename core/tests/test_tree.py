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
        assert 'data-stage="seed"' in render_tree(0)
        assert 'data-stage="sprout"' in render_tree(5)
        assert 'data-stage="seedling"' in render_tree(20)
        assert 'data-stage="sapling"' in render_tree(35)
        assert 'data-stage="young"' in render_tree(50)
        assert 'data-stage="established"' in render_tree(65)
        assert 'data-stage="mature"' in render_tree(85)
        assert 'data-stage="bloom"' in render_tree(100)

    def test_bloom_has_blossoms_seed_does_not(self):
        assert render_tree(100).count('fill="#fff"') >= 4
        assert 'fill="#fff"' not in render_tree(0)

    def test_trunk_is_a_filled_path_with_branches_when_grown(self):
        grown = render_tree(80)
        assert 'fill="#78716c"' in grown  # tapered filled trunk, not a stroked line
        assert grown.count("stroke-linecap") >= 4  # branches + roots + ground

    def test_deterministic_per_seed(self):
        assert render_tree(60, seed=7) == render_tree(60, seed=7)
        assert render_tree(60, seed=7) != render_tree(60, seed=8)

    def test_clamps_out_of_range(self):
        assert 'data-stage="bloom"' in render_tree(150)
        assert 'data-stage="seed"' in render_tree(-5)
        assert 'data-stage="seed"' in render_tree(None)


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


class TestGrove:
    def test_dashboard_grove_one_tree_per_active_project(self, client_logged_in):
        from plans.tests.factories import MilestoneFactory, PhaseFactory
        from projects.tests.factories import ProjectFactory

        small = ProjectFactory(name="Small Study", status="active")
        big = ProjectFactory(name="Big Study", status="active")
        ProjectFactory(name="Done Study", status="complete")
        for _ in range(6):
            MilestoneFactory(phase=PhaseFactory(project=big))
        MilestoneFactory(phase=PhaseFactory(project=small))

        response = client_logged_in.get(reverse("core:dashboard"))
        content = response.content.decode()
        assert "The grove" in content
        assert content.count("Project tree —") == 2  # active projects only

    def test_tree_size_scales_with_scope(self):
        from core.dashboard import active_projects
        from plans.tests.factories import MilestoneFactory, PhaseFactory
        from projects.tests.factories import ProjectFactory

        small = ProjectFactory(status="active")
        big = ProjectFactory(status="active")
        MilestoneFactory(phase=PhaseFactory(project=small))
        for _ in range(20):
            MilestoneFactory(phase=PhaseFactory(project=big))

        sizes = {row["project"].pk: row["tree_size"] for row in active_projects()}
        assert sizes[small.pk] == 69  # 64 + 5*1
        assert sizes[big.pk] == 112  # capped
