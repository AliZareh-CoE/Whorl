"""Regression guards for Owner idea #1 (performance): hot pages stay within query budgets.

Budgets are deliberately generous ceilings — they exist to catch reintroduced N+1s
(which scale with row counts), not to pin exact query plans.
"""

import pytest
from django.urls import reverse

from literature.tests.factories import ProjectReferenceFactory
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def warm_pet_cache(db):
    """The sidebar pet is 5-min cached; budgets measure steady-state pages."""
    from core.pet import pet_state

    pet_state()


def build_busy_project():
    project = ProjectFactory()
    for order in range(4):
        phase = PhaseFactory(project=project, order=order)
        MilestoneFactory.create_batch(3, phase=phase)
    for _ in range(20):
        ProjectReferenceFactory(project=project)
    return project


class TestQueryBudgets:
    def test_library_index_constant_queries(self, client_logged_in, django_assert_max_num_queries):
        build_busy_project()
        with django_assert_max_num_queries(10):
            response = client_logged_in.get(reverse("literature:index"))
        assert response.status_code == 200

    def test_documents_index_constant_queries(
        self, client_logged_in, django_assert_max_num_queries
    ):
        # the per-row move-<select> used to re-query project.folders per document (#180);
        # the bulk-move <select> reused the same redundant query until #181 pointed it at the
        # cached folder list. With several folders and many documents the page must stay within
        # a flat budget that no longer leaves room for those duplicate folder reads.
        from documents.tests.factories import DocumentFactory, FolderFactory

        project = ProjectFactory()
        FolderFactory.create_batch(5, project=project)
        DocumentFactory.create_batch(15, project=project)
        url = reverse("documents:index", args=[project.slug]) + "?all=1"
        with django_assert_max_num_queries(16):
            response = client_logged_in.get(url)
        assert response.status_code == 200

    def test_project_overview_budget(self, client_logged_in, django_assert_max_num_queries):
        project = build_busy_project()
        with django_assert_max_num_queries(18):
            response = client_logged_in.get(project.get_absolute_url())
        assert response.status_code == 200

    def test_plan_page_budget(self, client_logged_in, django_assert_max_num_queries):
        project = build_busy_project()
        with django_assert_max_num_queries(12):
            response = client_logged_in.get(reverse("plans:plan", args=[project.slug]))
        assert response.status_code == 200

    def test_dashboard_budget_and_heatmap_cache(
        self, client_logged_in, django_assert_max_num_queries, settings
    ):
        settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        build_busy_project()
        client_logged_in.get(reverse("core:dashboard"))  # warm the heatmap cache
        with django_assert_max_num_queries(20):
            response = client_logged_in.get(reverse("core:dashboard"))
        assert response.status_code == 200


class TestApiQueryBudgets:
    """AUDIT #10: the project-references list ran 48 queries (N+1 via the nested
    reference serializer) before select_related; these ceilings keep the API flat."""

    def test_project_references_list_constant_queries(
        self, client_logged_in, django_assert_max_num_queries
    ):
        project = build_busy_project()
        with django_assert_max_num_queries(8):
            response = client_logged_in.get(f"/api/v1/project-references/?project={project.slug}")
        assert response.status_code == 200
        assert response.json()["count"] == 20

    def test_timeline_constant_queries(self, client_logged_in, django_assert_max_num_queries):
        project = build_busy_project()
        with django_assert_max_num_queries(14):
            response = client_logged_in.get(f"/api/v1/projects/{project.slug}/timeline/")
        assert response.status_code == 200

    def test_q_param_is_capped(self, client_logged_in):
        project = build_busy_project()
        response = client_logged_in.get(
            f"/api/v1/milestones/?project={project.slug}&q={'a' * 5000}"
        )
        assert response.status_code == 200  # capped to 200 chars, not an error
