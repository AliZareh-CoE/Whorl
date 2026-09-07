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

    def test_finds_manuscripts(self):
        # #239: global search now covers manuscripts (added after search was first built).
        from writing.tests.factories import ManuscriptFactory

        ManuscriptFactory(title="Zebrafish swimming under load")
        results = search_all("zebrafish")
        manuscripts = [r for r in results if r["type"] == "manuscript"]
        assert manuscripts and manuscripts[0]["object"].title == "Zebrafish swimming under load"

    def test_finds_research_thinking_types(self):
        # #240: hypotheses, research questions, and experiments are searchable too.
        from plans.models import ResearchQuestion
        from research.models import ExperimentEntry, Hypothesis

        project = ProjectFactory()
        Hypothesis.objects.create(
            project=project, statement="Octopus camouflage is attention-gated"
        )
        ResearchQuestion.objects.create(
            project=project, question="How does octopus skin sense light?"
        )
        ExperimentEntry.objects.create(project=project, title="Octopus dazzle trial")
        types = {r["type"] for r in search_all("octopus")}
        assert {"hypothesis", "question", "experiment"} <= types

    def test_api_search_gives_research_types_a_url(self, client_logged_in):
        # #243: the API/MCP search returned url=None for hypotheses/questions/experiments
        # (no get_absolute_url). Now each has one (its list page + a deep-link anchor).
        from plans.models import ResearchQuestion
        from research.models import ExperimentEntry, Hypothesis

        project = ProjectFactory()
        Hypothesis.objects.create(project=project, statement="Penguins navigate by polarized light")
        ResearchQuestion.objects.create(project=project, question="Do penguins see UV?")
        ExperimentEntry.objects.create(project=project, title="Penguin maze run")
        data = client_logged_in.get("/api/v1/search/?q=penguin").json()
        urls = {r["type"]: r["url"] for r in data["results"]}
        for kind in ("hypothesis", "question", "experiment"):
            assert urls.get(kind), f"{kind} result must carry a url"
            assert f"#{kind}-" in urls[kind]  # deep-link anchor

    def test_empty_query_returns_nothing(self):
        assert search_all("") == []

    def test_icontains_fallback_finds_across_types(self):
        # #210b: the SQLite desktop build uses the non-Postgres LIKE fallback. The logic
        # works on any backend, so exercise it directly here.
        from core.search import _icontains_search

        ReferenceFactory(title="Octopus camouflage review")
        NoteFactory(title="Octopus ideas", body="chromatophores")
        DecisionRecordFactory(title="Study octopus", decision="Tractable model.")
        results = _icontains_search("octopus")
        types = {r["type"] for r in results}
        assert {"reference", "note", "decision"} <= types
        # every row keeps the same shape the FTS path returns
        assert all({"type", "object", "project"} <= r.keys() for r in results)

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


class TestCoverage428:
    """#428: protocols, datasets and captures are searchable on both paths."""

    def _seed(self):
        from notes.models import QuickCapture
        from research.models import Dataset, Protocol

        project = ProjectFactory(name="Tide pools")
        Protocol.objects.create(
            project=project, title="Anemone handling", body="gloves, ten minutes"
        )
        Dataset.objects.create(project=project, name="anemone-counts", location="/data/anemone")
        QuickCapture.objects.create(text="ask about the anemone permit")
        return project

    def test_icontains_path(self):
        from core.search import _icontains_search, describe

        self._seed()
        rows = {r["type"]: r for r in _icontains_search("anemone")}
        assert {"protocol", "dataset", "capture"} <= rows.keys()
        assert describe(rows["protocol"], "anemone")["meta"] == "v1"
        assert describe(rows["capture"], "anemone")["app_url"] == "/inbox"
        assert describe(rows["dataset"], "anemone")["app_url"].endswith("/research")

    def test_fts_path(self):
        from django.db import connection

        if connection.vendor != "postgresql":
            pytest.skip("FTS path is Postgres-only")
        self._seed()
        types = {r["type"] for r in search_all("anemone")}
        assert {"protocol", "dataset", "capture"} <= types

    def test_ui_labels(self):
        src = open("frontend/src/app/pages/Search.tsx").read()
        assert 'protocol: "Protocols"' in src and 'capture: "Captures"' in src
