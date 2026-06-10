import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings):
    settings.ATLAS_API_KEY = KEY


class TestAuth:
    def test_missing_key_rejected(self, client, owner):
        assert client.get("/api/v1/projects/").status_code == 401

    def test_wrong_key_rejected(self, client, owner):
        response = client.get("/api/v1/projects/", HTTP_X_API_KEY="nope")
        assert response.status_code == 401

    def test_session_auth_not_accepted(self, client_logged_in):
        assert client_logged_in.get("/api/v1/projects/").status_code == 401

    def test_valid_key_accepted(self, client, owner):
        assert client.get("/api/v1/projects/", **HEADERS).status_code == 200

    def test_schema_and_docs_render_without_login(self, client, owner):
        assert client.get("/api/schema/").status_code == 200
        assert client.get("/api/docs/").status_code == 200


class TestProjects:
    def test_create_and_retrieve_by_slug(self, client, owner):
        response = client.post(
            "/api/v1/projects/",
            {"name": "API Project", "description": "from the API", "status": "active"},
            content_type="application/json",
            **HEADERS,
        )
        assert response.status_code == 201
        slug = response.json()["slug"]
        assert slug == "api-project"
        detail = client.get(f"/api/v1/projects/{slug}/", **HEADERS)
        assert detail.status_code == 200
        assert detail.json()["name"] == "API Project"

    def test_pagination_shape(self, client, owner):
        ProjectFactory.create_batch(3)
        data = client.get("/api/v1/projects/", **HEADERS).json()
        assert {"count", "next", "previous", "results"} <= set(data)
        assert data["count"] == 3


class TestPlanResources:
    def test_phase_filter_by_project(self, client, owner):
        phase = PhaseFactory()
        PhaseFactory()  # other project
        data = client.get(f"/api/v1/phases/?project={phase.project.slug}", **HEADERS).json()
        assert data["count"] == 1
        assert data["results"][0]["id"] == phase.pk

    def test_complete_milestone_via_patch(self, client, owner):
        milestone = MilestoneFactory()
        response = client.patch(
            f"/api/v1/milestones/{milestone.pk}/",
            {"completed_at": timezone.now().isoformat()},
            content_type="application/json",
            **HEADERS,
        )
        assert response.status_code == 200
        milestone.refresh_from_db()
        assert milestone.completed_at is not None


class TestDocuments:
    def test_upload_via_api(self, client, owner):
        project = ProjectFactory()
        response = client.post(
            "/api/v1/documents/",
            {
                "project": project.slug,
                "title": "API upload",
                "file": SimpleUploadedFile("api.txt", b"hello", "text/plain"),
            },
            **HEADERS,
        )
        assert response.status_code == 201
        doc = project.documents.get()
        assert doc.title == "API upload"
        assert doc.file_size == 5


class TestDecisions:
    def test_create_decision_with_project_slug(self, client, owner):
        project = ProjectFactory()
        response = client.post(
            "/api/v1/decisions/",
            {
                "project": project.slug,
                "title": "API decision",
                "decision": "Yes.",
                "decided_on": "2026-06-10",
            },
            content_type="application/json",
            **HEADERS,
        )
        assert response.status_code == 201
        assert project.decisions.count() == 1


class TestUIUnaffected:
    def test_ui_still_requires_login(self, client, owner):
        project = ProjectFactory()
        assert client.get(f"/projects/{project.slug}/").status_code == 302

    def test_api_key_setting_empty_rejects_all(self, client, owner, settings):
        settings.ATLAS_API_KEY = ""
        assert client.get("/api/v1/projects/", **HEADERS).status_code == 401


def test_project_delete_via_api(client, owner):
    project = ProjectFactory()
    response = client.delete(f"/api/v1/projects/{project.slug}/", **HEADERS)
    assert response.status_code == 204
    assert not Project.objects.filter(pk=project.pk).exists()
