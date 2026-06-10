import pytest
from django.urls import reverse

from core.search import search_all
from literature.tests.factories import ReferenceFactory
from notes.tests.factories import NoteFactory
from projects.tests.factories import DecisionRecordFactory, ProjectFactory

pytestmark = pytest.mark.django_db


class TestSearch:
    def test_mixed_type_results(self):
        ReferenceFactory(title="Zebrafish locomotion dynamics")
        NoteFactory(title="Zebrafish ideas", body="swimming patterns")
        DecisionRecordFactory(title="Use zebrafish model", decision="Cheaper than mice.")
        results = search_all("zebrafish")
        types = {r["type"] for r in results}
        assert {"reference", "note", "decision"} <= types

    def test_empty_query_returns_nothing(self):
        assert search_all("") == []

    def test_search_page_renders_grouped(self, client_logged_in):
        project = ProjectFactory(name="Coral Reef Mapping")
        NoteFactory(project=project, title="Coral bleaching notes")
        response = client_logged_in.get(reverse("core:search"), {"q": "coral"})
        assert response.status_code == 200
        assert b"Coral Reef Mapping" in response.content
        assert b"Coral bleaching notes" in response.content

    def test_no_results_message(self, client_logged_in):
        response = client_logged_in.get(reverse("core:search"), {"q": "xyzzyplugh"})
        assert b"No results" in response.content
