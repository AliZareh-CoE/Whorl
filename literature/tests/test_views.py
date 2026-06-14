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

    def test_index_sorts_by_year_descending(self, client_logged_in):
        ReferenceFactory(title="Old Paper", year=1990)
        ReferenceFactory(title="New Paper", year=2025)
        response = client_logged_in.get(
            reverse("literature:index"), {"sort": "year", "dir": "desc"}
        )
        assert response.status_code == 200
        body = response.content.decode()
        assert body.index("New Paper") < body.index("Old Paper")

    def test_index_remembers_sort_across_visits(self, client_logged_in):
        # #176: choosing a sort sticks; a later visit with no sort param restores it.
        ReferenceFactory(title="Old Paper", year=1990)
        ReferenceFactory(title="New Paper", year=2025)
        client_logged_in.get(reverse("literature:index"), {"sort": "year", "dir": "desc"})
        body = client_logged_in.get(reverse("literature:index")).content.decode()
        assert body.index("New Paper") < body.index("Old Paper")

    def test_index_sorts_by_year_ascending(self, client_logged_in):
        ReferenceFactory(title="Old Paper", year=1990)
        ReferenceFactory(title="New Paper", year=2025)
        response = client_logged_in.get(reverse("literature:index"), {"sort": "year"})
        body = response.content.decode()
        assert body.index("Old Paper") < body.index("New Paper")

    def test_index_rejects_unknown_sort_field(self, client_logged_in):
        # a hostile ?sort= must fall back to the title default, never reach the ORM raw
        ReferenceFactory(title="Anything")
        response = client_logged_in.get(
            reverse("literature:index"), {"sort": "password; DROP TABLE"}
        )
        assert response.status_code == 200
        assert b"Anything" in response.content

    def test_sort_links_preserve_search_query(self, client_logged_in):
        ReferenceFactory(title="Quantum Frogs")
        response = client_logged_in.get(reverse("literature:index"), {"q": "Quantum"})
        assert b"q=Quantum" in response.content

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

    def test_project_page_orders_by_year(self, client_logged_in):
        # #189: the order pills sort the per-project literature list server-side.
        project = ProjectFactory()
        ProjectReferenceFactory(project=project, reference__title="Old One", reference__year=1990)
        ProjectReferenceFactory(project=project, reference__title="New One", reference__year=2025)
        url = reverse("literature:project", args=[project.slug])
        body = client_logged_in.get(url, {"sort": "year"}).content.decode()
        assert body.index("New One") < body.index("Old One")  # year desc, newest first

    def test_project_page_remembers_order(self, client_logged_in):
        # #190: choosing an order sticks; a later visit with no sort param restores it.
        project = ProjectFactory()
        ProjectReferenceFactory(project=project, reference__title="Old One", reference__year=1990)
        ProjectReferenceFactory(project=project, reference__title="New One", reference__year=2025)
        url = reverse("literature:project", args=[project.slug])
        client_logged_in.get(url, {"sort": "year"})
        body = client_logged_in.get(url).content.decode()
        assert body.index("New One") < body.index("Old One")

    def test_project_page_rejects_unknown_sort(self, client_logged_in):
        project = ProjectFactory()
        ProjectReferenceFactory(project=project, reference__title="Anything Here")
        url = reverse("literature:project", args=[project.slug])
        response = client_logged_in.get(url, {"sort": "'; DROP TABLE"})
        assert response.status_code == 200
        assert b"Anything Here" in response.content

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

    def test_queue_order_persists_in_session(self, client_logged_in):
        # #193: choosing the queue order remembers it across visits.
        project = ProjectFactory()
        ProjectReferenceFactory(project=project, reference__title="QueuePaper")
        url = reverse("literature:queue", args=[project.slug])
        client_logged_in.get(url, {"order": "gaps"})
        assert client_logged_in.session["queue_order"] == "gaps"

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


class TestAuditCycle10Fixes:
    def test_highlight_length_capped(self, client_logged_in):
        from django.core.files.base import ContentFile

        link = ProjectReferenceFactory()
        link.reference.pdf.save("p.pdf", ContentFile(b"%PDF-1.4"), save=True)
        response = client_logged_in.post(
            reverse("literature:highlight", args=[link.reference.pk]),
            {"project": link.project.slug, "text": "x" * 2001},
        )
        assert response.status_code == 400
        assert "2000" in response.json()["error"]


class TestLitReviewIntegration:
    def make_matrix_with_mark(self):
        from literature.models import ReviewMark, ReviewTheme

        link = ProjectReferenceFactory()
        theme = ReviewTheme.objects.create(project=link.project, name="Methods", order=1)
        ReviewMark.objects.create(theme=theme, project_reference=link, note="tests it directly")
        return link, theme

    def test_queue_shows_theme_coverage(self, client_logged_in):
        link, theme = self.make_matrix_with_mark()
        ProjectReferenceFactory(project=link.project)  # uncovered paper
        response = client_logged_in.get(reverse("literature:queue", args=[link.project.slug]))
        content = response.content.decode()
        assert "1/1 themes" in content
        assert "0/1 themes" in content

    def test_matrix_markdown_export(self, client_logged_in):
        link, theme = self.make_matrix_with_mark()
        response = client_logged_in.get(
            reverse("literature:matrix_export", args=[link.project.slug])
        )
        body = response.content.decode()
        assert response["Content-Type"].startswith("text/markdown")
        assert "| Paper | Methods |" in body
        assert f"| {link.reference.bibtex_key} | tests it directly |" in body

    def test_review_matrix_api_endpoint(self, client, owner, settings):
        settings.ATLAS_API_KEY = "k"
        link, theme = self.make_matrix_with_mark()
        data = client.get(
            f"/api/v1/projects/{link.project.slug}/review-matrix/", HTTP_X_API_KEY="k"
        ).json()
        assert data["themes"] == ["Methods"]
        assert data["papers"][0]["marks"] == {"Methods": "tests it directly"}

    def test_mcp_client_review_matrix(self, monkeypatch):
        import httpx

        from mcp_server import client as mcp_client

        monkeypatch.setenv("ATLAS_API_KEY", "k")
        calls = {}

        def fake_client():
            def handler(request):
                calls["url"] = str(request.url)
                return httpx.Response(200, json={"ok": True})

            return httpx.Client(base_url="http://t/api/v1", transport=httpx.MockTransport(handler))

        monkeypatch.setattr(mcp_client, "_client", fake_client)
        mcp_client.get_review_matrix("my-project")
        assert calls["url"].endswith("/projects/my-project/review-matrix/")


def test_reader_has_listen_player(client_logged_in):
    from django.core.files.base import ContentFile

    link = ProjectReferenceFactory()
    link.reference.pdf.save("p.pdf", ContentFile(b"%PDF-1.4"), save=True)
    response = client_logged_in.get(reverse("literature:read", args=[link.reference.pk]))
    content = response.content.decode()
    assert 'id="listen-btn"' in content
    assert 'id="player-stop"' in content
    assert "listenFrom" in content


class TestKeywordCloud:
    def test_cloud_built_from_linked_refs(self, client_logged_in):
        project = ProjectFactory()
        for _i in range(3):
            ProjectReferenceFactory(
                project=project,
                reference__title="Working memory load study variant",
                reference__abstract="working memory load drives attention lapses",
            )
        response = client_logged_in.get(reverse("literature:project", args=[project.slug]))
        content = response.content.decode()
        assert "Keywords" in content
        assert "working memory load" in content

    def test_keyword_filters_literature_and_queue(self, client_logged_in):
        project = ProjectFactory()
        ProjectReferenceFactory(
            project=project, reference__title="Working memory load study", reference__abstract=""
        )
        ProjectReferenceFactory(
            project=project, reference__title="Coral reef bleaching", reference__abstract=""
        )
        lit = client_logged_in.get(
            reverse("literature:project", args=[project.slug]), {"kw": "memory"}
        )
        assert b"Working memory" in lit.content
        assert b"Coral reef" not in lit.content
        queue = client_logged_in.get(
            reverse("literature:queue", args=[project.slug]), {"kw": "memory"}
        )
        assert b"Working memory" in queue.content
        assert b"Coral reef" not in queue.content

    def test_cloud_cached(self, django_assert_num_queries, client_logged_in):
        from literature.selectors import project_keyword_cloud

        link = ProjectReferenceFactory()
        project_keyword_cloud(link.project)  # warm
        with django_assert_num_queries(0):
            project_keyword_cloud(link.project)


class TestQueueGapOrdering:
    def _setup_matrix(self):
        from literature.models import ProjectReference, ReviewMark, ReviewTheme
        from literature.tests.factories import ProjectReferenceFactory

        # theme "Covered" has 2 read papers; theme "Gap" has none
        queued_covered = ProjectReferenceFactory()
        project = queued_covered.project
        covered = ReviewTheme.objects.create(project=project, name="Covered", order=1)
        gap = ReviewTheme.objects.create(project=project, name="Gap", order=2)
        for _ in range(2):
            done = ProjectReferenceFactory(
                project=project, reading_status=ProjectReference.ReadingStatus.READ
            )
            ReviewMark.objects.create(theme=covered, project_reference=done)
        ReviewMark.objects.create(theme=covered, project_reference=queued_covered)
        queued_gap = ProjectReferenceFactory(project=project)
        ReviewMark.objects.create(theme=gap, project_reference=queued_gap)
        queued_unmarked = ProjectReferenceFactory(project=project)
        return project, queued_gap, queued_covered, queued_unmarked

    def test_gap_scores_annotated(self):
        from literature.selectors import annotate_gap_scores

        project, queued_gap, queued_covered, queued_unmarked = self._setup_matrix()
        links = list(
            project.project_references.filter(reading_status="to_read").prefetch_related(
                "review_marks"
            )
        )
        annotate_gap_scores(project, links)
        by_pk = {link.pk: link for link in links}
        assert by_pk[queued_gap.pk].gap_score == 0
        assert by_pk[queued_gap.pk].gap_theme == "Gap"
        assert by_pk[queued_covered.pk].gap_score == 2
        assert by_pk[queued_unmarked.pk].gap_score is None

    def test_queue_orders_gap_papers_first(self, client_logged_in):
        project, queued_gap, queued_covered, queued_unmarked = self._setup_matrix()
        url = reverse("literature:queue", args=[project.slug]) + "?order=gaps"
        response = client_logged_in.get(url)
        content = response.content.decode()
        positions = [
            content.index(link.reference.title)
            for link in (queued_gap, queued_covered, queued_unmarked)
        ]
        assert positions == sorted(positions)  # gap paper first, unmarked last
        assert "fills: Gap (0 read)" in content

    def test_default_order_unchanged(self, client_logged_in):
        project, *_ = self._setup_matrix()
        response = client_logged_in.get(reverse("literature:queue", args=[project.slug]))
        assert response.status_code == 200
        assert "Fill matrix gaps" in response.content.decode()


class TestBulkStatus:
    def test_bulk_marks_selected_papers(self, client_logged_in):
        from literature.models import ProjectReference
        from literature.tests.factories import ProjectReferenceFactory

        first = ProjectReferenceFactory()
        second = ProjectReferenceFactory(project=first.project)
        other = ProjectReferenceFactory()  # different project — must be ignored
        url = reverse("literature:bulk_status", args=[first.project.slug])
        response = client_logged_in.post(
            url, {"reading_status": "read", "ids": [first.pk, second.pk, other.pk]}
        )
        assert response.status_code == 302
        assert ProjectReference.objects.get(pk=first.pk).reading_status == "read"
        assert ProjectReference.objects.get(pk=second.pk).reading_status == "read"
        assert ProjectReference.objects.get(pk=other.pk).reading_status == "to_read"

    def test_invalid_status_rejected(self, client_logged_in):
        from literature.models import ProjectReference
        from literature.tests.factories import ProjectReferenceFactory

        link = ProjectReferenceFactory()
        url = reverse("literature:bulk_status", args=[link.project.slug])
        client_logged_in.post(url, {"reading_status": "nonsense", "ids": [link.pk]})
        assert ProjectReference.objects.get(pk=link.pk).reading_status == "to_read"

    def test_pages_render_bulk_bar(self, client_logged_in):
        from literature.tests.factories import ProjectReferenceFactory

        link = ProjectReferenceFactory()
        for name in ("literature:project", "literature:queue"):
            content = client_logged_in.get(reverse(name, args=[link.project.slug])).content.decode()
            assert 'id="bulk-status-form"' in content


class TestSynthesisScaffold:
    def _matrix(self):
        from literature.models import ReviewMark, ReviewTheme
        from literature.tests.factories import ProjectReferenceFactory

        link = ProjectReferenceFactory()
        project = link.project
        theme = ReviewTheme.objects.create(project=project, name="Load theory", order=1)
        ReviewTheme.objects.create(project=project, name="Empty theme", order=2)
        ReviewMark.objects.create(theme=theme, project_reference=link, note="key paper")
        unthemed = ProjectReferenceFactory(project=project)
        return project, link, unthemed

    def test_scaffold_groups_by_theme(self):
        from literature.selectors import synthesis_scaffold

        project, link, unthemed = self._matrix()
        text = synthesis_scaffold(project)
        assert "## Load theory" in text
        assert link.reference.bibtex_key in text
        assert "key paper" in text
        assert "## Empty theme" in text and "a gap to fill or drop" in text
        assert "## Not yet themed" in text
        assert unthemed.reference.bibtex_key in text
        assert "## Synthesis" in text

    def test_draft_creates_note_and_redirects(self, client_logged_in):
        from django.urls import reverse

        from notes.models import Note

        project, link, _ = self._matrix()
        response = client_logged_in.post(reverse("literature:draft_synthesis", args=[project.slug]))
        assert response.status_code == 302
        note = Note.objects.get(project=project, title=f"Synthesis — {project.name}")
        assert link.reference.bibtex_key in note.body
        assert response.url == note.get_absolute_url()

    def test_draft_is_idempotent(self, client_logged_in):
        from django.urls import reverse

        from notes.models import Note

        project, *_ = self._matrix()
        url = reverse("literature:draft_synthesis", args=[project.slug])
        client_logged_in.post(url)
        client_logged_in.post(url)
        assert Note.objects.filter(title=f"Synthesis — {project.name}").count() == 1


class TestThemeCandidates:
    """Backlog #82: the coverage-gap nudge deep-links the queue to a theme's candidates."""

    def _setup(self):
        from literature.models import ReviewMark, ReviewTheme

        hit = ProjectReferenceFactory(reference__title="Attention mechanisms in working memory")
        project = hit.project
        theme = ReviewTheme.objects.create(project=project, name="Attention", order=1)
        miss = ProjectReferenceFactory(
            project=project, reference__title="Bayesian models of perception"
        )
        marked = ProjectReferenceFactory(
            project=project, reference__title="Attention as a resource"
        )
        ReviewMark.objects.create(theme=theme, project_reference=marked)
        return project, hit, miss, marked

    def _candidates(self, project, theme_name):
        from literature.selectors import theme_candidates

        return list(theme_candidates(project.project_references.all(), theme_name))

    def test_matches_title_excludes_marked_and_misses(self):
        project, hit, miss, marked = self._setup()
        assert self._candidates(project, "Attention") == [hit]

    def test_matches_abstract_words_individually(self):
        project, *_ = self._setup()
        extra = ProjectReferenceFactory(
            project=project,
            reference__title="An unrelated title",
            reference__abstract="We study selective attention under load.",
        )
        assert extra in self._candidates(project, "Selective Attention")

    def test_excludes_read_papers(self):
        project, hit, *_ = self._setup()
        hit.reading_status = ProjectReference.ReadingStatus.READ
        hit.save()
        assert self._candidates(project, "Attention") == []

    def test_stopword_only_theme_matches_nothing(self):
        project, *_ = self._setup()
        assert self._candidates(project, "the of") == []
        assert self._candidates(project, "") == []

    def test_api_theme_param_filters_queue(self, client, owner, settings):
        settings.ATLAS_API_KEY = "k"
        project, hit, miss, marked = self._setup()
        data = client.get(
            f"/api/v1/project-references/?project={project.slug}&theme=Attention",
            HTTP_X_API_KEY="k",
        ).json()
        assert [row["id"] for row in data["results"]] == [hit.pk]
