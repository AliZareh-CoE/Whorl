import pytest
from django.urls import reverse

from notes import services
from notes.models import Note
from projects.tests.factories import ProjectFactory

from .factories import NoteFactory

pytestmark = pytest.mark.django_db


class TestWikiLinks:
    def test_parse_titles_dedupes_case_insensitively(self):
        body = "See [[Alpha]] and [[beta]] plus [[ALPHA]] again."
        assert services.parse_wiki_titles(body) == ["Alpha", "beta"]

    def test_sync_creates_links_and_reports_unresolved(self):
        project = ProjectFactory()
        alpha = NoteFactory(project=project, title="Alpha")
        beta = NoteFactory(project=project, title="Beta", body="Links to [[Alpha]] and [[Gamma]].")
        unresolved = services.sync_note_links(beta)
        assert [link.target for link in beta.outgoing_links.all()] == [alpha]
        assert unresolved == ["Gamma"]

    def test_sync_replaces_old_links(self):
        project = ProjectFactory()
        alpha = NoteFactory(project=project, title="Alpha")
        NoteFactory(project=project, title="Beta")
        note = NoteFactory(project=project, title="Hub", body="[[Alpha]]")
        services.sync_note_links(note)
        note.body = "[[Beta]] only now"
        note.save()
        services.sync_note_links(note)
        targets = [link.target.title for link in note.outgoing_links.all()]
        assert targets == ["Beta"]
        assert alpha.incoming_links.count() == 0

    def test_links_scoped_to_project(self):
        NoteFactory(title="Shared Title")
        project = ProjectFactory()
        note = NoteFactory(project=project, title="Local", body="[[Shared Title]]")
        unresolved = services.sync_note_links(note)
        assert unresolved == ["Shared Title"]

    def test_body_with_resolved_links_renders_markdown_link(self):
        project = ProjectFactory()
        alpha = NoteFactory(project=project, title="Alpha")
        note = NoteFactory(project=project, title="Source", body="go to [[Alpha]] or [[Nowhere]]")
        rendered = services.body_with_resolved_links(note)
        assert f"[Alpha]({alpha.get_absolute_url()})" in rendered
        # an unresolved link now offers a one-click "create this note" (pre-filled)
        create = reverse("notes:create", kwargs={"slug": project.slug})
        assert f"[+ Nowhere]({create}?title=Nowhere)" in rendered

    def test_create_form_prefills_title_from_query(self, client_logged_in):
        project = ProjectFactory()
        url = reverse("notes:create", kwargs={"slug": project.slug}) + "?title=Fresh%20Idea"
        body = client_logged_in.get(url).content
        assert b'value="Fresh Idea"' in body


class TestUnwrittenTitles:
    def test_collects_referenced_but_missing_titles(self):
        project = ProjectFactory()
        NoteFactory(project=project, title="Alpha", body="see [[Beta]] and [[Gamma]]")
        NoteFactory(project=project, title="Beta", body="back to [[Alpha]] and [[Gamma]]")
        # Beta + Alpha exist; Gamma is referenced twice but unwritten → once, deduped.
        assert services.unwritten_note_titles(project) == ["Gamma"]

    def test_scoped_to_project(self):
        project = ProjectFactory()
        NoteFactory(project=project, title="Home", body="[[Local Stub]]")
        NoteFactory(title="Elsewhere", body="[[Foreign Stub]]")  # different project
        assert services.unwritten_note_titles(project) == ["Local Stub"]


class TestNoteViews:
    def test_note_list_shows_unwritten_stubs(self, client_logged_in):
        project = ProjectFactory()
        NoteFactory(project=project, title="Real", body="points at [[Missing Idea]]")
        body = client_logged_in.get(reverse("notes:list", args=[project.slug])).content
        assert b"Mentioned but not yet written" in body
        assert b"+ Missing Idea" in body
        assert b"?title=Missing%20Idea" in body

    def test_note_list_backlink_count_no_n_plus_one(
        self, client_logged_in, django_assert_max_num_queries
    ):
        # the per-row backlink count is annotated, not a .count() per note (#236-fu).
        project = ProjectFactory()
        NoteFactory.create_batch(3, project=project)
        url = reverse("notes:list", args=[project.slug])
        client_logged_in.get(url)  # warm
        with django_assert_max_num_queries(15) as ctx:
            client_logged_in.get(url)
        baseline = len(ctx.captured_queries)
        NoteFactory.create_batch(5, project=project)
        with django_assert_max_num_queries(baseline):
            client_logged_in.get(url)  # 8 notes cost no more queries than 3

    def test_create_note_syncs_links(self, client_logged_in):
        project = ProjectFactory()
        NoteFactory(project=project, title="Target")
        response = client_logged_in.post(
            reverse("notes:create", args=[project.slug]),
            {"title": "Source", "body": "see [[Target]]"},
        )
        assert response.status_code == 302
        source = Note.objects.get(title="Source")
        assert source.outgoing_links.get().target.title == "Target"

    def test_detail_shows_backlinks(self, client_logged_in):
        project = ProjectFactory()
        target = NoteFactory(project=project, title="Popular")
        source = NoteFactory(project=project, title="Fan", body="[[Popular]]")
        services.sync_note_links(source)
        response = client_logged_in.get(target.get_absolute_url())
        assert response.status_code == 200
        assert b"Fan" in response.content

    def test_duplicate_title_rejected(self, client_logged_in):
        project = ProjectFactory()
        NoteFactory(project=project, title="Unique")
        response = client_logged_in.post(
            reverse("notes:create", args=[project.slug]),
            {"title": "unique", "body": ""},
        )
        assert response.status_code == 200
        assert b"already exists" in response.content

    def test_preview_endpoint(self, client_logged_in):
        project = ProjectFactory()
        response = client_logged_in.post(
            reverse("notes:preview", args=[project.slug]), {"body": "**bold**"}
        )
        assert b"<strong>bold</strong>" in response.content


class TestInboxBulk:
    def test_bulk_dismiss_and_assign(self, client_logged_in):
        from notes.models import QuickCapture
        from projects.tests.factories import ProjectFactory

        project = ProjectFactory()
        a = QuickCapture.objects.create(text="bulk a")
        b = QuickCapture.objects.create(text="bulk b")
        c = QuickCapture.objects.create(text="bulk c")

        client_logged_in.post(
            reverse("notes:inbox_bulk"), {"action": "dismiss", "ids": [a.pk, b.pk]}
        )
        a.refresh_from_db(), b.refresh_from_db(), c.refresh_from_db()
        assert a.processed and b.processed and not c.processed

        client_logged_in.post(
            reverse("notes:inbox_bulk"),
            {"action": "assign", "ids": [c.pk], "project": project.slug},
        )
        c.refresh_from_db()
        assert c.processed and c.project == project

    def test_triage_honors_safe_next_redirect(self, client_logged_in):
        from notes.models import QuickCapture
        from projects.tests.factories import ProjectFactory

        project = ProjectFactory()
        capture = QuickCapture.objects.create(text="from the dashboard")
        response = client_logged_in.post(
            reverse("notes:triage", args=[capture.pk]),
            {"action": "assign", "project": project.slug, "next": "/classic/"},
        )
        capture.refresh_from_db()
        assert capture.processed and capture.project == project
        assert response.status_code == 302 and response.url == "/classic/"

    def test_triage_rejects_offsite_next(self, client_logged_in):
        from notes.models import QuickCapture

        capture = QuickCapture.objects.create(text="x")
        response = client_logged_in.post(
            reverse("notes:triage", args=[capture.pk]),
            {"action": "dismiss", "next": "https://evil.example/phish"},
        )
        assert response.status_code == 302
        assert response.url == reverse("notes:inbox")

    def test_inbox_renders_bulk_bar(self, client_logged_in):
        from notes.models import QuickCapture

        QuickCapture.objects.create(text="something")
        content = client_logged_in.get(reverse("notes:inbox")).content.decode()
        assert 'id="inbox-bulk-form"' in content
        assert "Dismiss all" in content
