import pytest
from django.urls import reverse

from literature.models import ProjectReference
from projects.tests.factories import ProjectFactory

from .factories import ProjectReferenceFactory, ReferenceFactory

pytestmark = pytest.mark.django_db


class TestLibrary:
    def test_index_renders_and_searches(self, client_logged_in):
        ReferenceFactory(title="Quantum Frogs in Winter")
        ReferenceFactory(title="Classical Toads in Summer")
        response = client_logged_in.get(reverse("literature:index"), {"q": "Quantum"})
        assert response.status_code == 200
        assert b"Quantum Frogs" in response.content
        assert b"Classical Toads" not in response.content

    def test_add_by_identifier_uses_service(self, client_logged_in, monkeypatch):
        ref = ReferenceFactory()
        monkeypatch.setattr(
            "literature.services.add_reference_by_identifier", lambda identifier: (ref, True)
        )
        response = client_logged_in.post(reverse("literature:add"), {"identifier": "10.1/x"})
        assert response.status_code == 302
        assert response.url == ref.get_absolute_url()

    def test_add_by_identifier_shows_metadata_error(self, client_logged_in, monkeypatch):
        from literature.services import MetadataError

        def boom(identifier):
            raise MetadataError("Could not resolve DOI 10.1/x: Crossref returned 404")

        monkeypatch.setattr("literature.services.add_reference_by_identifier", boom)
        response = client_logged_in.post(reverse("literature:add"), {"identifier": "10.1/x"})
        assert response.status_code == 200
        assert b"Crossref returned 404" in response.content

    def test_manual_entry_generates_key(self, client_logged_in):
        response = client_logged_in.post(
            reverse("literature:create"),
            {
                "entry_type": "article",
                "title": "Handmade Entry",
                "year": 2023,
                "venue": "Manual Venue",
                "authors_text": "Doe, Jane",
                "doi": "",
                "arxiv_id": "",
                "url": "",
                "abstract": "",
            },
        )
        assert response.status_code == 302
        from literature.models import Reference

        ref = Reference.objects.get(title="Handmade Entry")
        assert ref.bibtex_key == "doe2023handmade"

    def test_detail_shows_bibtex(self, client_logged_in):
        ref = ReferenceFactory()
        response = client_logged_in.get(ref.get_absolute_url())
        assert response.status_code == 200
        assert ref.bibtex_key.encode() in response.content

    def test_import_page(self, client_logged_in):
        bibtex = "@article{k1, title={Pasted}, author={Poe, Edgar}, journal={J}, year={2020}}"
        response = client_logged_in.post(reverse("literature:import"), {"bibtex": bibtex})
        assert response.status_code == 200
        from literature.models import Reference

        assert Reference.objects.filter(title="Pasted").exists()


class TestProjectLiterature:
    def test_project_page_filters_by_status(self, client_logged_in):
        project = ProjectFactory()
        read = ProjectReferenceFactory(
            project=project, reading_status="read", reference__title="Read Paper Xyz"
        )
        ProjectReferenceFactory(
            project=project, reading_status="to_read", reference__title="Unread Paper Abc"
        )
        url = reverse("literature:project", args=[project.slug])
        response = client_logged_in.get(url, {"status": "read"})
        assert read.reference.title.encode() in response.content
        assert b"Unread Paper Abc" not in response.content

    def test_queue_sorted_by_priority(self, client_logged_in):
        project = ProjectFactory()
        ProjectReferenceFactory(project=project, priority="low", reference__title="LowPaper")
        ProjectReferenceFactory(project=project, priority="high", reference__title="HighPaper")
        ProjectReferenceFactory(
            project=project, reading_status="read", reference__title="DonePaper"
        )
        response = client_logged_in.get(reverse("literature:queue", args=[project.slug]))
        content = response.content.decode()
        assert "DonePaper" not in content
        assert content.index("HighPaper") < content.index("LowPaper")

    def test_set_status_htmx(self, client_logged_in):
        link = ProjectReferenceFactory()
        response = client_logged_in.post(
            reverse("literature:set_status", args=[link.project.slug, link.pk]),
            {"reading_status": "read"},
        )
        link.refresh_from_db()
        assert response.status_code == 200
        assert link.reading_status == "read"

    def test_link_reference_to_project(self, client_logged_in):
        project = ProjectFactory()
        ref = ReferenceFactory()
        response = client_logged_in.post(
            reverse("literature:project_link", args=[project.slug]),
            {"reference": ref.pk, "reading_status": "to_read", "priority": "high", "notes": ""},
        )
        assert response.status_code == 302
        link = ProjectReference.objects.get(project=project, reference=ref)
        assert link.priority == "high"

    def test_export_bib(self, client_logged_in):
        link = ProjectReferenceFactory()
        response = client_logged_in.get(reverse("literature:export_bib", args=[link.project.slug]))
        assert response.status_code == 200
        assert "attachment" in response["Content-Disposition"]
        assert link.reference.bibtex_key.encode() in response.content

    def test_bib_report_offline_renders_four_sections(self, client_logged_in):
        link = ProjectReferenceFactory(reference__venue="", reference__year=None)
        url = reverse("literature:report", args=[link.project.slug])
        response = client_logged_in.get(f"{url}?offline")
        content = response.content.decode()
        for section in ("Duplicates", "Missing fields", "DOI resolution", "Retractions"):
            assert section in content
        assert "missing" in content  # the seeded missing-fields finding shows up


class TestInbox:
    def test_capture_and_triage(self, client_logged_in):
        from notes.models import QuickCapture

        response = client_logged_in.post(reverse("notes:inbox"), {"text": "read the frog paper"})
        assert response.status_code == 302
        capture = QuickCapture.objects.get()
        project = ProjectFactory()
        client_logged_in.post(
            reverse("notes:triage", args=[capture.pk]),
            {"action": "assign", "project": project.slug},
        )
        capture.refresh_from_db()
        assert capture.processed and capture.project == project

    def test_dismiss(self, client_logged_in):
        from notes.models import QuickCapture

        capture = QuickCapture.objects.create(text="meh")
        client_logged_in.post(reverse("notes:triage", args=[capture.pk]), {"action": "dismiss"})
        capture.refresh_from_db()
        assert capture.processed and capture.project is None
