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


class TestPdfReader:
    def make_ref_with_pdf(self):
        from django.core.files.base import ContentFile

        link = ProjectReferenceFactory()
        link.reference.pdf.save("paper.pdf", ContentFile(b"%PDF-1.4 fake"), save=True)
        return link

    def test_read_page_renders_with_pdf(self, client_logged_in):
        link = self.make_ref_with_pdf()
        response = client_logged_in.get(reverse("literature:read", args=[link.reference.pk]))
        assert response.status_code == 200
        assert b"pdfjs" in response.content
        assert link.project.name.encode() in response.content

    def test_read_redirects_without_pdf(self, client_logged_in):
        ref = ReferenceFactory()
        response = client_logged_in.get(reverse("literature:read", args=[ref.pk]))
        assert response.status_code == 302
        assert response.url == ref.get_absolute_url()

    def test_save_highlight_creates_and_appends_note(self, client_logged_in):
        from notes.models import Note

        link = self.make_ref_with_pdf()
        url = reverse("literature:highlight", args=[link.reference.pk])
        first = client_logged_in.post(
            url, {"project": link.project.slug, "text": "key passage one", "page": 3}
        )
        assert first.status_code == 200
        note = Note.objects.get(pk=first.json()["note_id"])
        assert note.title == f"Highlights — {link.reference.bibtex_key}"
        assert "> key passage one" in note.body
        assert "p.3" in note.body
        assert link.reference in note.references.all()

        client_logged_in.post(url, {"project": link.project.slug, "text": "second passage"})
        note.refresh_from_db()
        assert "second passage" in note.body
        assert Note.objects.filter(project=link.project).count() == 1

    def test_highlight_rejects_unlinked_project(self, client_logged_in):
        link = self.make_ref_with_pdf()
        other = ProjectFactory()
        response = client_logged_in.post(
            reverse("literature:highlight", args=[link.reference.pk]),
            {"project": other.slug, "text": "nope"},
        )
        assert response.status_code == 404

    def test_highlight_rejects_empty_text(self, client_logged_in):
        link = self.make_ref_with_pdf()
        response = client_logged_in.post(
            reverse("literature:highlight", args=[link.reference.pk]),
            {"project": link.project.slug, "text": "   "},
        )
        assert response.status_code == 400


class TestReviewMatrix:
    def make_matrix(self):
        from literature.models import ReviewTheme

        link = ProjectReferenceFactory()
        theme = ReviewTheme.objects.create(project=link.project, name="Methods", order=1)
        return link, theme

    def test_matrix_renders_papers_and_themes(self, client_logged_in):
        link, theme = self.make_matrix()
        response = client_logged_in.get(reverse("literature:matrix", args=[link.project.slug]))
        assert response.status_code == 200
        assert b"Methods" in response.content
        assert link.reference.bibtex_key.encode() in response.content

    def test_toggle_mark_on_and_off(self, client_logged_in):
        from literature.models import ReviewMark

        link, theme = self.make_matrix()
        url = reverse("literature:toggle_mark", args=[link.project.slug, theme.pk, link.pk])
        first = client_logged_in.post(url)
        assert first.status_code == 200
        assert ReviewMark.objects.filter(theme=theme, project_reference=link).exists()
        client_logged_in.post(url)
        assert not ReviewMark.objects.filter(theme=theme, project_reference=link).exists()

    def test_toggle_scoped_to_project(self, client_logged_in):
        link, theme = self.make_matrix()
        other = ProjectReferenceFactory()  # different project
        url = reverse("literature:toggle_mark", args=[other.project.slug, theme.pk, other.pk])
        assert client_logged_in.post(url).status_code == 404

    def test_mark_note_edit(self, client_logged_in):
        from literature.models import ReviewMark

        link, theme = self.make_matrix()
        mark = ReviewMark.objects.create(theme=theme, project_reference=link)
        response = client_logged_in.post(
            reverse("literature:mark_note", args=[link.project.slug, mark.pk]),
            {"note": "covers it in section 3"},
        )
        mark.refresh_from_db()
        assert response.status_code == 302
        assert mark.note == "covers it in section 3"

    def test_theme_crud_and_unique_per_project(self, client_logged_in):
        link, theme = self.make_matrix()
        response = client_logged_in.post(
            reverse("literature:theme_create", args=[link.project.slug]),
            {"name": "Population", "order": 2},
        )
        assert response.status_code == 302
        assert link.project.review_themes.count() == 2
        dup = client_logged_in.post(
            reverse("literature:theme_create", args=[link.project.slug]),
            {"name": "Methods", "order": 3},
        )
        assert dup.status_code == 200  # form re-renders with error
        assert link.project.review_themes.count() == 2
