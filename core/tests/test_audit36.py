"""Audit #36 (#578, since #35: #568–#577 — Today's Trash, ?page_size= honoured, the Diagnostics
verdict, the Files Trash, the pane editor). Findings pinned here; the report is in AUDITS.md."""

import inspect

import pytest
from django.contrib.auth.decorators import login_not_required  # noqa: F401 — the intent below
from django.core.files.base import ContentFile

from core.models import TodoItem
from documents.models import Document, Tag
from projects.tests.factories import ProjectFactory
from writing.models import ManuscriptFile, SubmissionEvent
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


class TestTextBodies:
    """Finding 1: a non-string `content` / `note` in a JSON body was a 500 (len / encode /
    slice on a list, a number, an object or null) at the pane save, write-file, replace and
    the upload; a list note was stored as its repr. Every reader answers 400 naming the field."""

    def _doc(self, project):
        return Document.objects.create(
            project=project, title="n.md", rel_path="n.md", kind="other", content="old"
        )

    @pytest.mark.parametrize("bad", [["a"], 123, {"a": 1}, 1.5, True])
    def test_content_must_be_text_on_save_and_write(self, client, bad):
        project = ProjectFactory()
        doc = self._doc(project)
        resp = client.put(f"/api/v1/documents/{doc.pk}/content/", {"content": bad}, **JSON)
        assert resp.status_code == 400 and "content" in resp.json()
        resp = client.post(
            f"/api/v1/projects/{project.slug}/write-file/",
            {"path": "audit/x.txt", "content": bad},
            **JSON,
        )
        assert resp.status_code == 400 and "content" in resp.json()
        assert not project.documents.filter(rel_path="audit/x.txt").exists()

    def test_null_content_is_an_empty_save(self, client):
        project = ProjectFactory()
        doc = self._doc(project)
        resp = client.put(f"/api/v1/documents/{doc.pk}/content/", {"content": None}, **JSON)
        assert resp.status_code == 200
        doc.refresh_from_db()
        assert doc.content == ""

    @pytest.mark.parametrize("bad", [["x"], 5, {"a": 1}])
    def test_note_must_be_text_everywhere(self, client, bad):
        project = ProjectFactory()
        doc = self._doc(project)
        resp = client.put(
            f"/api/v1/documents/{doc.pk}/content/", {"content": "new", "note": bad}, **JSON
        )
        assert resp.status_code == 400 and "note" in resp.json()
        resp = client.post(
            f"/api/v1/projects/{project.slug}/write-file/",
            {"path": "n.md", "content": "new", "note": bad},
            **JSON,
        )
        assert resp.status_code == 400 and "note" in resp.json()
        assert not doc.versions.exists()  # nothing was filed on the way to the 400

    def test_a_long_note_is_trimmed_not_refused(self, client):
        project = ProjectFactory()
        doc = self._doc(project)
        resp = client.put(
            f"/api/v1/documents/{doc.pk}/content/", {"content": "new", "note": "n" * 300}, **JSON
        )
        assert resp.status_code == 200
        assert len(doc.versions.first().note) == 200


class TestQueryBudgetsAtRealPageSizes:
    """#571 made ?page_size= real: the SPA asks for 200 manuscripts, 500 todos and 200
    documents at once. Each list stays constant in queries across row counts."""

    def _count(self, client, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            assert client.get(url, **HEADERS).status_code == 200
        return len(ctx.captured_queries)

    def test_manuscripts_with_clock_events_and_files(self, client):
        project = ProjectFactory()

        def rows(n):
            for _ in range(n):
                m = ManuscriptFactory(project=project, status="submitted", target_venue="NeurIPS")
                SubmissionEvent.objects.create(manuscript=m, kind="submitted", date="2026-01-01")
                ManuscriptFile.objects.create(
                    manuscript=m, path="main.tex", kind="tex", is_main=True
                )

        rows(3)
        url = "/api/v1/manuscripts/?page_size=200"
        small = self._count(client, url)
        rows(27)
        assert self._count(client, url) == small
        assert small <= 12, small

    def test_todos_at_five_hundred(self, client):
        for i in range(5):
            TodoItem.objects.create(text=f"t{i}")
        url = "/api/v1/todos/?when=current&page_size=500"
        small = self._count(client, url)
        for i in range(200):
            TodoItem.objects.create(text=f"u{i}", done=i % 2 == 0)
        assert self._count(client, url) == small

    def test_documents_with_tags_at_two_hundred(self, client):
        project = ProjectFactory()
        tag = Tag.objects.create(project=project, name="t")

        def rows(n):
            for i in range(n):
                d = Document.objects.create(
                    project=project,
                    title=f"d{i}.txt",
                    rel_path=f"d{i}.txt",
                    kind="other",
                    file=ContentFile(b"x", name=f"d{i}.txt"),
                )
                d.tags.add(tag)

        rows(3)
        url = f"/api/v1/documents/?project={project.slug}&page_size=200"
        small = self._count(client, url)
        rows(40)
        assert self._count(client, url) == small


def test_the_login_exemption_sits_on_the_viewset_base_not_on_a_helper():
    """Finding 3: `@method_decorator(login_not_required, name="dispatch")` had drifted onto
    the `_pk` helper (a no-op on a function that only worked by accident) after two helpers
    were inserted between it and `AtlasViewSet`. It is back on the class; `_pk` is plain."""
    from api import views

    assert inspect.unwrap(views._pk) is views._pk
    assert views._pk(" 7 ") == 7
    assert views.AtlasViewSet.dispatch.login_required is False
    assert views.SearchAPIView.dispatch.login_required is False
