"""Owner idea #10: generic comments on notes, references, manuscripts."""

import pytest
from django.urls import reverse

from core.comments import comments_for
from core.models import Comment

pytestmark = pytest.mark.django_db


class TestComments:
    def test_comment_on_note_and_render(self, client_logged_in):
        from notes.tests.factories import NoteFactory

        note = NoteFactory()
        response = client_logged_in.post(
            reverse("core:comment_add", args=["note", note.pk]),
            {"body": "This connects to the **pilot** data."},
        )
        assert response.status_code == 302
        assert response.url == note.get_absolute_url()
        assert comments_for(note).count() == 1
        page = client_logged_in.get(note.get_absolute_url())
        assert b"<strong>pilot</strong>" in page.content

    def test_comment_on_reference_and_manuscript(self, client_logged_in):
        from literature.tests.factories import ReferenceFactory
        from writing.tests.factories import ManuscriptFactory

        ref = ReferenceFactory()
        manuscript = ManuscriptFactory()
        client_logged_in.post(
            reverse("core:comment_add", args=["reference", ref.pk]), {"body": "key paper"}
        )
        client_logged_in.post(
            reverse("core:comment_add", args=["manuscript", manuscript.pk]),
            {"body": "rework intro"},
        )
        assert comments_for(ref).count() == 1
        assert comments_for(manuscript).count() == 1
        # threads are independent
        assert Comment.objects.count() == 2

    def test_unknown_kind_404(self, client_logged_in):
        response = client_logged_in.post(
            reverse("core:comment_add", args=["project", 1]), {"body": "nope"}
        )
        assert response.status_code == 404

    def test_empty_body_ignored(self, client_logged_in):
        from notes.tests.factories import NoteFactory

        note = NoteFactory()
        client_logged_in.post(reverse("core:comment_add", args=["note", note.pk]), {"body": "  "})
        assert comments_for(note).count() == 0

    def test_delete_comment(self, client_logged_in):
        from notes.tests.factories import NoteFactory

        note = NoteFactory()
        client_logged_in.post(reverse("core:comment_add", args=["note", note.pk]), {"body": "bye"})
        comment = Comment.objects.get()
        response = client_logged_in.post(reverse("core:comment_delete", args=[comment.pk]))
        assert response.status_code == 302
        assert Comment.objects.count() == 0

    def test_body_capped(self, client_logged_in):
        from notes.tests.factories import NoteFactory

        note = NoteFactory()
        client_logged_in.post(
            reverse("core:comment_add", args=["note", note.pk]), {"body": "x" * 6000}
        )
        assert len(comments_for(note).get().body) == 5000


class TestPageAnchoredComments:
    def make_pdf_ref(self):
        from django.core.files.base import ContentFile

        from literature.tests.factories import ReferenceFactory

        ref = ReferenceFactory()
        ref.pdf.save("p.pdf", ContentFile(b"%PDF-1.4"), save=True)
        return ref

    def test_comment_with_page_and_next_redirect(self, client_logged_in):
        ref = self.make_pdf_ref()
        read_url = reverse("literature:read", args=[ref.pk])
        response = client_logged_in.post(
            reverse("core:comment_add", args=["reference", ref.pk]),
            {"body": "key claim here", "page": "3", "next": read_url},
        )
        assert response.status_code == 302
        assert response.url == read_url
        comment = comments_for(ref).get()
        assert comment.page == 3

    def test_open_redirect_rejected(self, client_logged_in):
        ref = self.make_pdf_ref()
        response = client_logged_in.post(
            reverse("core:comment_add", args=["reference", ref.pk]),
            {"body": "x", "next": "https://evil.example/phish"},
        )
        assert response.url == ref.get_absolute_url()
        response2 = client_logged_in.post(
            reverse("core:comment_add", args=["reference", ref.pk]),
            {"body": "y", "next": "//evil.example"},
        )
        assert response2.url == ref.get_absolute_url()

    def test_reader_shows_page_comments(self, client_logged_in):
        from core.models import Comment

        ref = self.make_pdf_ref()
        Comment.objects.create(target=ref, body="anchored thought", page=2)
        Comment.objects.create(target=ref, body="general thought")  # no page
        response = client_logged_in.get(reverse("literature:read", args=[ref.pk]))
        content = response.content.decode()
        assert "anchored thought" in content
        assert "p.2" in content
        assert "general thought" not in content  # reader panel is page-anchored only

    def test_invalid_page_stored_as_null(self, client_logged_in):
        ref = self.make_pdf_ref()
        client_logged_in.post(
            reverse("core:comment_add", args=["reference", ref.pk]),
            {"body": "no page", "page": "abc"},
        )
        assert comments_for(ref).get().page is None
