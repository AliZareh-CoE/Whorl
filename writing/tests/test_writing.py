import datetime
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from literature.tests.factories import ReferenceFactory
from writing import services
from writing.models import Manuscript, ManuscriptReference, SubmissionEvent

from .factories import ManuscriptFactory

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures"


class TestCiteParser:
    def test_parses_cite_variants_and_multiple_keys(self):
        tex = (
            r"\cite{a} \citep{b,c} \citet[p.~3]{d} \parencite{e} "
            r"\textcite{f} \autocite[see][p.2]{g} \cite*{h}"
        )
        assert services.parse_cite_keys(tex) == {"a", "b", "c", "d", "e", "f", "g", "h"}

    def test_ignores_non_cite_commands(self):
        assert services.parse_cite_keys(r"\ref{fig:one} \label{sec:two}") == set()


class TestCiteChecker:
    def make_manuscript_with_bib(self):
        manuscript = ManuscriptFactory()
        for key in ("lavie2010attention", "baddeley2003working", "neverused2001"):
            ManuscriptReference.objects.create(
                manuscript=manuscript, reference=ReferenceFactory(bibtex_key=key)
            )
        return manuscript

    def test_broken_tex_fixture_flagged_correctly(self):
        manuscript = self.make_manuscript_with_bib()
        tex = (FIXTURES / "broken.tex").read_text()
        result = services.check_citations(manuscript, tex)
        assert result["missing_from_bib"] == [
            "anotherghost2021",
            "ghostpaper1999",
            "missingkey2020",
        ]
        assert result["uncited_in_bib"] == ["neverused2001"]
        assert result["matched"] == ["baddeley2003working", "lavie2010attention"]

    def test_cite_key_override_used(self):
        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript,
            reference=ReferenceFactory(bibtex_key="original2000key"),
            cite_key_override="customkey",
        )
        result = services.check_citations(manuscript, r"\cite{customkey}")
        assert result["matched"] == ["customkey"]
        assert result["missing_from_bib"] == []

    def test_export_manuscript_bib_uses_override(self):
        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript,
            reference=ReferenceFactory(bibtex_key="original2000key"),
            cite_key_override="customkey",
        )
        bib = services.export_manuscript_bib(manuscript)
        assert "@article{customkey," in bib


class TestManuscriptViews:
    def test_pipeline_board_groups_by_status(self, client_logged_in):
        project = ManuscriptFactory(status=Manuscript.Status.DRAFTING, title="Draft One").project
        ManuscriptFactory(project=project, status=Manuscript.Status.SUBMITTED, title="Sub One")
        response = client_logged_in.get(reverse("writing:project", args=[project.slug]))
        content = response.content.decode()
        assert "Drafting" in content and "Submitted" in content
        assert content.index("Draft One") < content.index("Sub One")

    def test_full_lifecycle_idea_to_published(self, client_logged_in):
        project = ManuscriptFactory(status=Manuscript.Status.IDEA).project
        manuscript = project.manuscripts.get()
        for kind, date in [
            ("submitted", "2026-01-10"),
            ("reviews_received", "2026-03-01"),
            ("revision_submitted", "2026-04-01"),
            ("accepted", "2026-05-01"),
            ("published", "2026-06-01"),
        ]:
            response = client_logged_in.post(
                reverse("writing:add_event", args=[project.slug, manuscript.pk]),
                {"kind": kind, "date": date, "notes": ""},
            )
            assert response.status_code == 302
        client_logged_in.post(
            reverse("writing:edit", args=[project.slug, manuscript.pk]),
            {
                "title": manuscript.title,
                "status": "published",
                "target_venue": "",
                "abstract": "",
                "repo_url": "",
            },
        )
        manuscript.refresh_from_db()
        assert manuscript.status == Manuscript.Status.PUBLISHED
        assert manuscript.events.count() == 5
        detail = client_logged_in.get(manuscript.get_absolute_url())
        assert b"Published" in detail.content
        assert b"Reviews received" in detail.content

    def test_cite_checker_via_view_with_fixture_upload(self, client_logged_in):
        from django.core.files.uploadedfile import SimpleUploadedFile

        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript, reference=ReferenceFactory(bibtex_key="lavie2010attention")
        )
        tex = (FIXTURES / "broken.tex").read_bytes()
        response = client_logged_in.post(
            manuscript.get_absolute_url(),
            {"tex_file": SimpleUploadedFile("paper.tex", tex, "text/x-tex")},
        )
        content = response.content.decode()
        assert "ghostpaper1999" in content
        assert "missingkey2020" in content

    def test_bib_export_download(self, client_logged_in):
        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript, reference=ReferenceFactory(bibtex_key="export2020me")
        )
        response = client_logged_in.get(
            reverse("writing:export_bib", args=[manuscript.project.slug, manuscript.pk])
        )
        assert response.status_code == 200
        assert b"export2020me" in response.content

    def test_deadline_countdown_on_overview(self, client_logged_in):
        manuscript = ManuscriptFactory(
            deadline=timezone.localdate() + datetime.timedelta(days=12),
            status=Manuscript.Status.DRAFTING,
        )
        response = client_logged_in.get(manuscript.project.get_absolute_url())
        assert b"12 days to deadline" in response.content

    def test_event_delete(self, client_logged_in):
        manuscript = ManuscriptFactory()
        event = SubmissionEvent.objects.create(
            manuscript=manuscript, kind="note", date="2026-01-01"
        )
        client_logged_in.post(
            reverse("writing:delete_event", args=[manuscript.project.slug, manuscript.pk, event.pk])
        )
        assert manuscript.events.count() == 0
