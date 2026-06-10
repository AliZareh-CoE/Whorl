import json

import httpx
import pytest

from literature import sync
from literature.models import CitationEdge, CitationSyncState

from .factories import ProjectReferenceFactory, ReferenceFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def patch_http(monkeypatch):
    state = {"handler": None}
    real_client = httpx.Client

    def client_factory(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(state["handler"]))

    monkeypatch.setattr(sync.httpx, "Client", client_factory)
    return state


class TestCitationSync:
    def test_sync_creates_edges_and_updates_counts(self, patch_http):
        link_a = ProjectReferenceFactory(reference__openalex_id="W1", reference__doi="10.1/a")
        project = link_a.project
        ref_a = link_a.reference
        ref_b = ProjectReferenceFactory(
            project=project, reference__openalex_id="W2", reference__doi="10.1/b"
        ).reference

        def handler(request):
            url = str(request.url)
            if url.startswith("https://api.openalex.org/works/W1"):
                return httpx.Response(
                    200,
                    content=json.dumps(
                        {
                            "id": "https://openalex.org/W1",
                            "referenced_works": ["https://openalex.org/W2"],
                            "cited_by_count": 11,
                        }
                    ),
                )
            if url.startswith("https://api.openalex.org/works/W2"):
                return httpx.Response(
                    200,
                    content=json.dumps(
                        {
                            "id": "https://openalex.org/W2",
                            "referenced_works": [],
                            "cited_by_count": 5,
                        }
                    ),
                )
            return httpx.Response(404)

        patch_http["handler"] = handler
        state = sync.sync_project_citations(project)
        assert state.status == CitationSyncState.Status.DONE
        assert CitationEdge.objects.filter(citing=ref_a, cited=ref_b).exists()
        ref_a.refresh_from_db()
        assert ref_a.citation_count == 11
        assert "1 new edge" in state.message

    def test_sync_resolves_missing_openalex_ids_by_doi(self, patch_http):
        link = ProjectReferenceFactory(reference__doi="10.1/needs-id")
        project = link.project

        def handler(request):
            url = str(request.url)
            if "filter=doi" in url or "filter" in dict(request.url.params):
                return httpx.Response(
                    200,
                    content=json.dumps(
                        {
                            "results": [
                                {
                                    "id": "https://openalex.org/W9",
                                    "doi": "https://doi.org/10.1/needs-id",
                                }
                            ]
                        }
                    ),
                )
            if url.startswith("https://api.openalex.org/works/W9"):
                return httpx.Response(
                    200,
                    content=json.dumps(
                        {
                            "id": "https://openalex.org/W9",
                            "referenced_works": [],
                            "cited_by_count": 3,
                        }
                    ),
                )
            return httpx.Response(404)

        patch_http["handler"] = handler
        state = sync.sync_project_citations(project)
        link.reference.refresh_from_db()
        assert link.reference.openalex_id == "W9"
        assert state.status == CitationSyncState.Status.DONE

    def test_sync_failure_recorded(self, patch_http):
        link = ProjectReferenceFactory(reference__openalex_id="W1")

        def handler(request):
            raise httpx.ConnectError("nope")

        patch_http["handler"] = handler
        state = sync.sync_project_citations(link.project)
        assert state.status == CitationSyncState.Status.FAILED
        assert "unreachable" in state.message

    def test_sync_idempotent_edges(self, patch_http):
        link_a = ProjectReferenceFactory(reference__openalex_id="W1")
        ref_b = ProjectReferenceFactory(
            project=link_a.project, reference__openalex_id="W2"
        ).reference

        def handler(request):
            url = str(request.url)
            which = "W2" if "/works/W2" in url else "W1"
            refs = ["https://openalex.org/W2"] if which == "W1" else []
            return httpx.Response(
                200,
                content=json.dumps(
                    {"id": f"https://openalex.org/{which}", "referenced_works": refs}
                ),
            )

        patch_http["handler"] = handler
        sync.sync_project_citations(link_a.project)
        sync.sync_project_citations(link_a.project)
        assert CitationEdge.objects.filter(cited=ref_b).count() == 1


class TestGraphBuilder:
    def test_graph_nodes_and_links(self):
        from core.graph import project_graph
        from notes import services as note_services
        from notes.tests.factories import NoteFactory

        link_a = ProjectReferenceFactory(reading_status="read")
        project = link_a.project
        ref_a = link_a.reference
        ref_b = ProjectReferenceFactory(project=project).reference
        CitationEdge.objects.create(citing=ref_a, cited=ref_b)

        target = NoteFactory(project=project, title="Theory")
        source = NoteFactory(project=project, title="Idea", body="[[Theory]]")
        note_services.sync_note_links(source)
        source.references.add(ref_a)

        graph = project_graph(project)
        ids = {n["id"] for n in graph["nodes"]}
        assert {
            f"ref-{ref_a.pk}",
            f"ref-{ref_b.pk}",
            f"note-{target.pk}",
            f"note-{source.pk}",
        } <= ids
        kinds = sorted(link["kind"] for link in graph["links"])
        assert kinds == ["citation", "note-citation", "note-link"]
        ref_node = next(n for n in graph["nodes"] if n["id"] == f"ref-{ref_a.pk}")
        assert ref_node["group"] == "read"

    def test_unlinked_reference_not_in_graph(self):
        from core.graph import project_graph

        link = ProjectReferenceFactory()
        ReferenceFactory()  # global, not linked to this project
        graph = project_graph(link.project)
        assert len([n for n in graph["nodes"] if n["type"] == "reference"]) == 1
