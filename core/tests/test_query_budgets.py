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
        with django_assert_max_num_queries(15):
            response = client_logged_in.get(url)
        assert response.status_code == 200

    def test_project_overview_budget(self, client_logged_in, django_assert_max_num_queries):
        project = build_busy_project()
        with django_assert_max_num_queries(18):
            response = client_logged_in.get(project.get_absolute_url())
        assert response.status_code == 200

    def test_api_overview_budget(self, client_logged_in, django_assert_max_num_queries):
        """#484: the SPA overview payload (digest, pulse, glances, themes, manuscripts with
        their pre-flight) — the timeline, the roadmap and the current phase are computed once
        per request, and nothing in it scales with the number of papers or milestones."""
        from notes.models import Note
        from writing.models import Manuscript

        project = build_busy_project()
        for i in range(5):
            Note.objects.create(project=project, title=f"n{i}", body="[[n0]]")
        Manuscript.objects.create(project=project, title="P", status="drafting")
        with django_assert_max_num_queries(60):
            response = client_logged_in.get(f"/api/v1/projects/{project.slug}/overview/")
        assert response.status_code == 200

    def test_api_dashboard_budget(self, client_logged_in, django_assert_max_num_queries):
        """Audit #27 (#488): the dashboard's cross-project panels (reading queue, writing)
        must not grow a pre-flight per manuscript per project — only the rows shown get one."""
        from writing.models import Manuscript

        for i in range(3):
            project = build_busy_project()
            for j in range(3):
                Manuscript.objects.create(project=project, title=f"P{i}{j}", status="drafting")
        # #489 added the per-project pulses as nine grouped queries (a fixed cost, not per
        # project) → the pin moves from 100 to 110
        with django_assert_max_num_queries(110):
            response = client_logged_in.get("/api/v1/dashboard/")
        assert response.status_code == 200
        rows = response.json()["writing"]["rows"]
        assert len(rows) == 6 and sum(1 for r in rows if r["readiness"]) == 4

    def test_plan_page_budget(self, client_logged_in, django_assert_max_num_queries):
        project = build_busy_project()
        with django_assert_max_num_queries(12):
            response = client_logged_in.get(reverse("plans:plan", args=[project.slug]))
        assert response.status_code == 200

    def test_reading_queue_constant_queries(self, client_logged_in, django_assert_max_num_queries):
        # #226: the reading queue grows with the project's references — adding more must not
        # add queries (select_related/prefetch + a single review-mark count).
        project = ProjectFactory()
        ProjectReferenceFactory.create_batch(3, project=project)
        url = reverse("literature:queue", args=[project.slug])
        client_logged_in.get(url)  # warm
        with django_assert_max_num_queries(25) as ctx:
            client_logged_in.get(url)
        baseline = len(ctx.captured_queries)
        ProjectReferenceFactory.create_batch(5, project=project)
        with django_assert_max_num_queries(baseline):
            client_logged_in.get(url)  # 8 papers cost no more queries than 3

    def test_review_matrix_constant_queries(self, client_logged_in, django_assert_max_num_queries):
        # #226: the papers × themes matrix is the other per-reference grid — keep it flat.
        project = ProjectFactory()
        ProjectReferenceFactory.create_batch(3, project=project)
        url = reverse("literature:matrix", args=[project.slug])
        client_logged_in.get(url)  # warm
        with django_assert_max_num_queries(25) as ctx:
            client_logged_in.get(url)
        baseline = len(ctx.captured_queries)
        ProjectReferenceFactory.create_batch(5, project=project)
        with django_assert_max_num_queries(baseline):
            client_logged_in.get(url)

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


class TestApiBudgets:
    """#426: the SPA's list endpoints must not grow with the rows they return."""

    def test_reference_list_with_tags_is_constant(
        self, client_logged_in, django_assert_max_num_queries
    ):
        from literature.models import LibraryTag
        from literature.tests.factories import ReferenceFactory

        tags = [LibraryTag.objects.create(name=f"t{i}") for i in range(3)]
        for i in range(40):
            ref = ReferenceFactory(bibtex_key=f"ref{i}")
            ref.tags.add(tags[i % 3])
            if i % 2:
                ref.tags.add(tags[(i + 1) % 3])
        with django_assert_max_num_queries(12):
            response = client_logged_in.get("/api/v1/references/?page_size=50")
        assert response.status_code == 200 and len(response.json()["results"]) == 40
        assert all(isinstance(r["tags"], list) for r in response.json()["results"])
