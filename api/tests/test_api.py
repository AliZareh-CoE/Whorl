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


class TestLiteratureAPI:
    def test_by_doi_creates_and_links(self, client, owner, monkeypatch):
        from literature.tests.factories import ReferenceFactory

        project = ProjectFactory()
        ref = ReferenceFactory()
        monkeypatch.setattr(
            "api.views.literature_services.add_reference_by_identifier",
            lambda identifier: (ref, True),
        )
        response = client.post(
            "/api/v1/references/by-doi/",
            {"doi": "10.1/x", "project": project.slug},
            content_type="application/json",
            **HEADERS,
        )
        assert response.status_code == 201
        assert project.project_references.filter(reference=ref).exists()

    def test_by_doi_metadata_error_is_400(self, client, owner, monkeypatch):
        from literature.services import MetadataError

        def boom(identifier):
            raise MetadataError("no such DOI")

        monkeypatch.setattr("api.views.literature_services.add_reference_by_identifier", boom)
        response = client.post(
            "/api/v1/references/by-doi/",
            {"doi": "10.1/x"},
            content_type="application/json",
            **HEADERS,
        )
        assert response.status_code == 400
        assert "no such DOI" in response.json()["detail"]

    def test_quick_capture_post(self, client, owner):
        response = client.post(
            "/api/v1/quick-capture/",
            {"text": "captured via API"},
            content_type="application/json",
            **HEADERS,
        )
        assert response.status_code == 201
        from notes.models import QuickCapture

        assert QuickCapture.objects.filter(text="captured via API").exists()


class TestGraphAPI:
    def test_graph_endpoint_shape(self, client, owner):
        from literature.models import CitationEdge
        from literature.tests.factories import ProjectReferenceFactory

        link_a = ProjectReferenceFactory()
        link_b = ProjectReferenceFactory(project=link_a.project)
        CitationEdge.objects.create(citing=link_a.reference, cited=link_b.reference)
        response = client.get(f"/api/v1/projects/{link_a.project.slug}/graph/", **HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert {"nodes", "links"} == set(data)
        assert len(data["nodes"]) == 2
        assert data["links"][0]["kind"] == "citation"


class TestMCPSupportEndpoints:
    def test_overview_endpoint(self, client, owner):
        from plans.tests.factories import MilestoneFactory, PhaseFactory

        phase = PhaseFactory(status="in_progress", name="Pilot")
        MilestoneFactory(phase=phase, title="Collect")
        data = client.get(f"/api/v1/projects/{phase.project.slug}/overview/", **HEADERS).json()
        assert data["current_phase"]["name"] == "Pilot"
        assert data["progress"]["total"] == 1
        assert data["next_milestones"][0]["title"] == "Collect"
        assert data["counts"]["documents"] == 0

    def test_plan_endpoint_nests_milestones_and_tasks(self, client, owner):
        from plans.tests.factories import TaskFactory

        task = TaskFactory(title="Leaf")
        slug = task.milestone.phase.project.slug
        data = client.get(f"/api/v1/projects/{slug}/plan/", **HEADERS).json()
        assert data["phases"][0]["milestones"][0]["tasks"][0]["title"] == "Leaf"

    def test_reading_queue_endpoint_sorted(self, client, owner):
        from literature.tests.factories import ProjectReferenceFactory

        link_low = ProjectReferenceFactory(priority="low")
        ProjectReferenceFactory(project=link_low.project, priority="high")
        data = client.get(
            f"/api/v1/projects/{link_low.project.slug}/reading-queue/", **HEADERS
        ).json()
        assert [item["priority"] for item in data] == ["high", "low"]

    def test_bib_report_endpoint_offline(self, client, owner):
        from literature.tests.factories import ProjectReferenceFactory

        link = ProjectReferenceFactory(reference__venue="", reference__year=None)
        data = client.get(f"/api/v1/projects/{link.project.slug}/bib-report/", **HEADERS).json()
        assert data["network_checks_included"] is False
        assert data["findings"]["missing_fields"]

    def test_search_endpoint(self, client, owner):
        from notes.tests.factories import NoteFactory

        NoteFactory(title="Searchable narwhal facts")
        data = client.get("/api/v1/search/?q=narwhal", **HEADERS).json()
        assert any(r["type"] == "note" for r in data["results"])

    def test_search_requires_key(self, client, owner):
        assert client.get("/api/v1/search/?q=x").status_code in (401, 403)

    def test_note_create_via_api_syncs_wiki_links(self, client, owner):
        from notes.models import Note
        from notes.tests.factories import NoteFactory

        target = NoteFactory(title="API Target")
        response = client.post(
            "/api/v1/notes/",
            {
                "project": target.project.slug,
                "title": "API Source",
                "body": "links to [[API Target]]",
            },
            content_type="application/json",
            **HEADERS,
        )
        assert response.status_code == 201
        source = Note.objects.get(title="API Source")
        assert source.outgoing_links.get().target == target
