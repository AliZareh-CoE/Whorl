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

    def test_session_auth_accepted_for_spa(self, client_logged_in):
        # Owner idea #20: the same-origin SPA reads the API with the session cookie
        assert client_logged_in.get("/api/v1/projects/").status_code == 200

    def test_session_writes_require_csrf(self, owner):
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(owner)
        response = csrf_client.post(
            "/api/v1/projects/", {"name": "No token"}, content_type="application/json"
        )
        assert response.status_code == 403  # CSRF enforced for session writes

    def test_valid_key_accepted(self, client, owner):
        assert client.get("/api/v1/projects/", **HEADERS).status_code == 200

    def test_schema_requires_session_or_api_key(self, client_logged_in, owner):
        from django.test import Client

        anon = Client()
        assert anon.get("/api/schema/").status_code == 401  # anonymous: rejected
        assert anon.get("/api/schema/", **HEADERS).status_code == 200  # API key ok
        assert client_logged_in.get("/api/schema/").status_code == 200  # session ok

    def test_docs_page_requires_login(self, client_logged_in, owner):
        from django.test import Client

        assert Client().get("/api/docs/").status_code == 302  # to login
        assert client_logged_in.get("/api/docs/").status_code == 200


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


class TestDashboardAPI:
    def test_dashboard_shape_and_session_access(self, client_logged_in):
        import datetime

        from django.utils import timezone

        from plans.tests.factories import MilestoneFactory, PhaseFactory

        phase = PhaseFactory(project__status="active", status="in_progress")
        MilestoneFactory(
            phase=phase,
            title="API dash milestone",
            due_date=timezone.localdate() + datetime.timedelta(days=3),
        )
        data = client_logged_in.get("/api/v1/dashboard/").json()
        assert {"stats", "inbox_count", "active", "milestones", "deadlines"} <= set(data)
        assert data["active"][0]["slug"] == phase.project.slug
        assert data["active"][0]["total"] == 1
        assert any("API dash milestone" == m["title"] for m in data["milestones"])


class TestOverviewSpaExtras:
    def test_overview_includes_recents(self, client_logged_in):
        from documents.tests.factories import DocumentFactory
        from projects.models import DecisionRecord

        doc = DocumentFactory(title="Overview doc")
        DecisionRecord.objects.create(
            project=doc.project, title="Overview decision", decision="Yes."
        )
        data = client_logged_in.get(f"/api/v1/projects/{doc.project.slug}/overview/").json()
        assert data["recent_documents"][0]["title"] == "Overview doc"
        assert data["recent_documents"][0]["url"].endswith("/download/")
        assert data["recent_decisions"][0]["title"] == "Overview decision"


class TestDocumentsTableAPI:
    def test_table_props_shape(self, client_logged_in):
        from documents.tests.factories import DocumentFactory

        doc = DocumentFactory(title="SPA doc")
        data = client_logged_in.get(f"/api/v1/projects/{doc.project.slug}/documents-table/").json()
        assert {"documents", "folders", "tags", "bulkUrl"} <= set(data)
        assert data["documents"][0]["title"] == "SPA doc"
        assert data["bulkUrl"].endswith("/documents/bulk/")

    def test_spa_bulk_returns_json_without_flash(self, client_logged_in):
        from documents.models import Document
        from documents.tests.factories import DocumentFactory

        doc = DocumentFactory()
        response = client_logged_in.post(
            f"/projects/{doc.project.slug}/documents/bulk/",
            {"action": "delete", "ids": [doc.pk]},
            headers={"X-SPA": "1"},
        )
        assert response.status_code == 200
        assert "Deleted 1" in response.json()["detail"]
        assert not Document.objects.filter(pk=doc.pk).exists()
        # the flash queue was consumed — the next page render shows no stale message
        follow = client_logged_in.get("/projects/")
        assert b"Deleted 1" not in follow.content


class TestLiteratureSpaSupport:
    def test_project_references_include_summary(self, client_logged_in):
        from literature.tests.factories import ProjectReferenceFactory

        link = ProjectReferenceFactory()
        data = client_logged_in.get(
            f"/api/v1/project-references/?project={link.project.slug}"
        ).json()
        summary = data["results"][0]["reference_summary"]
        assert {"id", "bibtex_key", "title", "authors", "year", "venue"} <= set(summary)

    def test_bulk_status_spa_mode_returns_json(self, client_logged_in):
        from literature.models import ProjectReference
        from literature.tests.factories import ProjectReferenceFactory

        link = ProjectReferenceFactory()
        response = client_logged_in.post(
            f"/projects/{link.project.slug}/literature/bulk-status/",
            {"reading_status": "read", "ids": [link.pk]},
            headers={"X-SPA": "1"},
        )
        assert response.status_code == 200
        assert "Marked 1" in response.json()["detail"]
        assert ProjectReference.objects.get(pk=link.pk).reading_status == "read"


class TestNotesSpaSupport:
    def test_preview_renders_sanitized_html_with_wiki_links(self, client_logged_in):
        from notes.tests.factories import NoteFactory

        target = NoteFactory(title="Linked Note")
        response = client_logged_in.post(
            "/api/v1/notes/preview/",
            {
                "body": "see [[Linked Note]] and <script>alert(1)</script> **bold**",
                "project": target.project.slug,
            },
            content_type="application/json",
        )
        html = response.json()["html"]
        assert f'href="{target.get_absolute_url()}"' in html
        assert "<script>" not in html  # nh3 strips it
        assert "<strong>bold</strong>" in html

    def test_note_serializer_includes_backlinks(self, client_logged_in):
        from notes.models import NoteLink
        from notes.tests.factories import NoteFactory

        target = NoteFactory(title="Hub")
        source = NoteFactory(project=target.project, title="Spoke")
        NoteLink.objects.create(source=source, target=target)
        data = client_logged_in.get(f"/api/v1/notes/{target.pk}/").json()
        assert data["backlinks"] == [{"id": source.pk, "title": "Spoke"}]


class TestManuscriptsAPI:
    def test_list_detail_and_events(self, client_logged_in):
        from writing.models import SubmissionEvent
        from writing.tests.factories import ManuscriptFactory

        manuscript = ManuscriptFactory(title="API Manuscript", status="submitted")
        SubmissionEvent.objects.create(
            manuscript=manuscript, kind="submitted", date="2026-06-01", notes="v1 in"
        )
        listing = client_logged_in.get("/api/v1/manuscripts/").json()
        assert listing["count"] == 1
        assert listing["results"][0]["project_name"] == manuscript.project.name

        detail = client_logged_in.get(f"/api/v1/manuscripts/{manuscript.pk}/").json()
        assert detail["events"][0]["kind"] == "submitted"

    def test_status_patch(self, client_logged_in):
        from writing.models import Manuscript
        from writing.tests.factories import ManuscriptFactory

        manuscript = ManuscriptFactory(status="drafting")
        response = client_logged_in.patch(
            f"/api/v1/manuscripts/{manuscript.pk}/",
            {"status": "submitted"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert Manuscript.objects.get(pk=manuscript.pk).status == "submitted"


def test_search_accepts_session_for_spa(client_logged_in):
    # SearchAPIView pinned authentication_classes and silently dropped session auth
    response = client_logged_in.get("/api/v1/search/?q=anything")
    assert response.status_code == 200


class TestResearchAPI:
    def test_hypotheses_with_evidence_counts(self, client_logged_in):
        from projects.tests.factories import ProjectFactory
        from research.models import Evidence, Hypothesis

        project = ProjectFactory()
        hypothesis = Hypothesis.objects.create(
            project=project, statement="Load gates distraction", status="testing"
        )
        Evidence.objects.create(hypothesis=hypothesis, direction="supports", summary="s1")
        Evidence.objects.create(hypothesis=hypothesis, direction="contradicts", summary="c1")
        data = client_logged_in.get(f"/api/v1/hypotheses/?project={project.slug}").json()
        row = data["results"][0]
        assert row["supports"] == 1 and row["contradicts"] == 1

    def test_research_endpoints_are_read_only(self, client_logged_in):
        response = client_logged_in.post("/api/v1/hypotheses/", {}, content_type="application/json")
        assert response.status_code == 405

    def test_experiments_and_datasets_listed(self, client_logged_in):
        from projects.tests.factories import ProjectFactory
        from research.models import Dataset, ExperimentEntry

        project = ProjectFactory()
        ExperimentEntry.objects.create(project=project, title="Run 1", date="2026-06-01")
        Dataset.objects.create(project=project, name="pilot-v1", location="/data/x")
        assert (
            client_logged_in.get(f"/api/v1/experiments/?project={project.slug}").json()["count"]
            == 1
        )
        assert (
            client_logged_in.get(f"/api/v1/datasets/?project={project.slug}").json()["count"] == 1
        )
