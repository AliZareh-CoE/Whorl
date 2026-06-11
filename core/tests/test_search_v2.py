"""Owner idea #15: lightning search — websearch parsing, typo tolerance, suggestions."""

import pytest
from django.urls import reverse

from core.search import search_all
from notes.tests.factories import NoteFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


class TestSearchV2:
    def test_typo_falls_back_to_trigram(self):
        NoteFactory(title="Attention allocation experiments")
        results = search_all("attentoin alocation")  # two typos — FTS finds nothing
        assert any(r["type"] == "note" for r in results)

    def test_websearch_negation(self):
        NoteFactory(title="Coral study", body="about coral reefs")
        NoteFactory(title="Coral economics", body="about coral markets")
        results = search_all("coral -markets")
        titles = [str(r["object"]) for r in results if r["type"] == "note"]
        assert "Coral study" in titles
        assert "Coral economics" not in titles

    def test_quoted_phrase(self):
        NoteFactory(title="Working memory load study", body="")
        NoteFactory(title="Memory of working in load environments", body="")
        results = search_all('"working memory load"')
        titles = [str(r["object"]) for r in results if r["type"] == "note"]
        assert "Working memory load study" in titles

    def test_no_fallback_when_fts_hits(self):
        NoteFactory(title="Unique zebrafish note")
        ProjectFactory(name="Zebra crossing")  # trigram-close to 'zebrafish' but FTS hit wins
        results = search_all("zebrafish")
        assert all(r["type"] == "note" for r in results)


class TestSuggest:
    def test_suggest_returns_links(self, client_logged_in):
        note = NoteFactory(title="Suggestion target note")
        response = client_logged_in.get(reverse("core:search_suggest"), {"q": "suggestion target"})
        content = response.content.decode()
        assert "Suggestion target note" in content
        assert note.get_absolute_url() in content
        assert "All results for" in content

    def test_suggest_requires_two_chars(self, client_logged_in):
        response = client_logged_in.get(reverse("core:search_suggest"), {"q": "a"})
        assert response.content.decode().strip() == ""

    def test_sidebar_wired_for_suggestions(self, client_logged_in):
        response = client_logged_in.get(reverse("core:dashboard"))
        assert b'hx-get="/search/suggest/"' in response.content


class TestTrigramIndexes:
    def test_all_five_trgm_indexes_exist(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT indexname FROM pg_indexes WHERE indexname LIKE '%_trgm'")
            names = {row[0] for row in cursor.fetchall()}
        assert {
            "project_name_trgm",
            "decision_title_trgm",
            "reference_title_trgm",
            "document_title_trgm",
            "note_title_trgm",
        } <= names

    def test_fallback_filters_with_index_served_operator(self):
        from literature.models import Reference

        sql = str(Reference.objects.filter(title__trigram_similar="load theory").query)
        assert " % " in sql  # the % operator is what the GIN trgm indexes serve
