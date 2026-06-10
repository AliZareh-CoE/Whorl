import json

import httpx
import pytest

from literature import services
from literature.models import Reference

from .factories import ReferenceFactory

pytestmark = pytest.mark.django_db


class TestNormalizers:
    def test_normalize_doi_strips_url_and_lowercases(self):
        assert (
            services.normalize_doi("https://doi.org/10.1038/NATURE12373") == "10.1038/nature12373"
        )

    def test_normalize_arxiv_strips_url_prefix_and_version(self):
        assert services.normalize_arxiv_id("https://arxiv.org/abs/2106.01234v2") == "2106.01234"
        assert services.normalize_arxiv_id("arXiv:2106.01234") == "2106.01234"


class TestBibtexKey:
    def test_key_shape(self):
        key = services.generate_bibtex_key(
            [{"family": "Smith", "given": "Jo"}], 2020, "The Attention Economy of Science"
        )
        assert key == "smith2020attention"

    def test_collision_gets_letter_suffix(self):
        ReferenceFactory(bibtex_key="smith2020attention")
        key = services.generate_bibtex_key([{"family": "Smith"}], 2020, "Attention Everywhere")
        assert key == "smith2020attentionb"

    def test_handles_missing_author_and_year(self):
        assert services.generate_bibtex_key([], None, "Untitled Things") == "anonnduntitled"


def make_mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


@pytest.fixture
def patch_http(monkeypatch):
    """Route services' outbound HTTP through a configurable handler."""
    state = {"handler": None}
    real_client = httpx.Client

    def client_factory(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(state["handler"]))

    monkeypatch.setattr(services.httpx, "Client", client_factory)
    return state


CROSSREF_WORK = {
    "message": {
        "DOI": "10.1000/test1",
        "type": "journal-article",
        "title": ["A Crossref Paper"],
        "author": [{"family": "Curie", "given": "Marie"}],
        "issued": {"date-parts": [[2021]]},
        "container-title": ["Nature of Tests"],
        "URL": "https://doi.org/10.1000/test1",
        "is-referenced-by-count": 42,
    }
}

OPENALEX_WORK = {
    "id": "https://openalex.org/W123",
    "doi": "https://doi.org/10.1000/test1",
    "type": "article",
    "title": "An OpenAlex Paper",
    "publication_year": 2022,
    "primary_location": {"source": {"display_name": "OpenAlex Venue"}},
    "locations": [],
    "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
    "cited_by_count": 7,
    "abstract_inverted_index": {"Deep": [0], "results.": [1]},
}


class TestMetadataFetch:
    def test_crossref_preferred(self, patch_http):
        def handler(request):
            if "crossref" in request.url.host:
                return httpx.Response(200, json=CROSSREF_WORK)
            raise AssertionError("should not reach OpenAlex")

        patch_http["handler"] = handler
        meta = services.fetch_metadata_by_doi("10.1000/test1")
        assert meta["title"] == "A Crossref Paper"
        assert meta["year"] == 2021
        assert meta["citation_count"] == 42
        assert meta["entry_type"] == "article"

    def test_openalex_fallback_on_crossref_404(self, patch_http):
        def handler(request):
            if "crossref" in request.url.host:
                return httpx.Response(404)
            return httpx.Response(200, json=OPENALEX_WORK)

        patch_http["handler"] = handler
        meta = services.fetch_metadata_by_doi("10.1000/test1")
        assert meta["title"] == "An OpenAlex Paper"
        assert meta["authors"] == [{"family": "Lovelace", "given": "Ada"}]
        assert meta["abstract"] == "Deep results."

    def test_clear_error_when_both_fail(self, patch_http):
        patch_http["handler"] = lambda request: httpx.Response(404)
        with pytest.raises(services.MetadataError) as excinfo:
            services.fetch_metadata_by_doi("10.1000/missing")
        message = str(excinfo.value)
        assert "Crossref returned 404" in message
        assert "OpenAlex returned 404" in message

    def test_arxiv_via_openalex(self, patch_http):
        def handler(request):
            assert "10.48550/arxiv.2106.01234" in str(request.url)
            return httpx.Response(200, json=OPENALEX_WORK)

        patch_http["handler"] = handler
        meta = services.fetch_metadata_by_arxiv("2106.01234v3")
        assert meta["arxiv_id"] == "2106.01234"

    def test_add_by_identifier_dedups_by_doi(self, patch_http):
        patch_http["handler"] = lambda request: httpx.Response(200, json=CROSSREF_WORK)
        ref1, created1 = services.add_reference_by_identifier("10.1000/test1")
        ref2, created2 = services.add_reference_by_identifier("10.1000/TEST1")
        assert created1 and not created2
        assert ref1 == ref2
        assert Reference.objects.count() == 1


BIBTEX_SAMPLE = """
@article{smith2020thing,
  title = {A Thing About Stuff},
  author = {Smith, John and Doe, Jane},
  journal = {Journal of Stuff},
  year = {2020},
  doi = {10.1000/bib1},
}
@inproceedings{conf2019,
  title = {{Conference} Paper},
  author = {Jane Roe},
  booktitle = {Proc. of Confs},
  year = {2019},
}
"""


class TestBibtexImportExport:
    def test_import_creates_references(self):
        results = services.import_bibtex(BIBTEX_SAMPLE)
        assert len(results) == 2
        assert all(created for _, created in results)
        first = results[0][0]
        assert first.title == "A Thing About Stuff"
        assert first.authors[0] == {"family": "Smith", "given": "John"}
        assert first.doi == "10.1000/bib1"
        assert first.year == 2020
        second = results[1][0]
        assert second.entry_type == "inproceedings"
        assert second.venue == "Proc. of Confs"

    def test_import_dedups_existing_doi(self):
        ReferenceFactory(doi="10.1000/bib1")
        results = services.import_bibtex(BIBTEX_SAMPLE)
        created_flags = [created for _, created in results]
        assert created_flags == [False, True]

    def test_render_bibtex_round_trip(self):
        ref = ReferenceFactory(
            bibtex_key="curie2021radium",
            title="Radium Things",
            authors=[{"family": "Curie", "given": "Marie"}],
            year=2021,
            venue="Nature",
            doi="10.1000/r1",
        )
        bibtex = services.render_bibtex(ref)
        assert "@article{curie2021radium," in bibtex
        assert "Curie, Marie" in bibtex
        assert "doi = {10.1000/r1}" in bibtex

    def test_export_project_bib(self):
        from .factories import ProjectReferenceFactory

        link = ProjectReferenceFactory()
        content = services.export_project_bib(link.project)
        assert link.reference.bibtex_key in content


class TestCheckers:
    def test_duplicate_doi_detected(self):
        a = ReferenceFactory(doi="10.1/dup", title="Totally Different A")
        b = ReferenceFactory(doi=None, title="Unrelated B")
        b.doi = "10.1/dup"  # bypass unique constraint via direct assignment list
        refs = [a, b]
        findings = services.check_duplicates(refs)
        assert any(f["level"] == "error" for f in findings)

    def test_fuzzy_title_duplicate_detected(self):
        a = ReferenceFactory(title="Attention Is All You Need")
        b = ReferenceFactory(title="Attention is all you need!")
        findings = services.check_duplicates([a, b])
        assert any("Similar titles" in f["message"] for f in findings)

    def test_no_false_duplicate(self):
        a = ReferenceFactory(title="Graph Neural Networks for Chemistry")
        b = ReferenceFactory(title="A Survey of Reinforcement Learning")
        assert services.check_duplicates([a, b]) == []

    def test_missing_fields(self):
        ref = ReferenceFactory(entry_type="article", venue="", year=None)
        findings = services.check_missing_fields([ref])
        assert len(findings) == 1
        assert "venue" in findings[0]["message"]
        assert "year" in findings[0]["message"]

    def test_doi_resolution_flags_404(self):
        ref = ReferenceFactory(doi="10.1/broken")
        client = make_mock_client(lambda request: httpx.Response(404))
        findings = services.check_doi_resolution([ref], client=client)
        assert findings[0]["level"] == "error"

    def test_doi_resolution_passes_on_redirect(self):
        ref = ReferenceFactory(doi="10.1/good")
        client = make_mock_client(lambda request: httpx.Response(302))
        assert services.check_doi_resolution([ref], client=client) == []

    def test_retraction_flagged(self):
        ref = ReferenceFactory(doi="10.1/retracted")

        def handler(request):
            payload = {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1/notice",
                            "update-to": [{"type": "retraction", "DOI": "10.1/retracted"}],
                        }
                    ]
                }
            }
            return httpx.Response(200, content=json.dumps(payload))

        findings = services.check_retractions([ref], client=make_mock_client(handler))
        assert findings and findings[0]["level"] == "error"
        assert "RETRACTED" in findings[0]["message"]

    def test_report_offline_skips_network(self):
        ReferenceFactory()
        report = services.run_bib_report(Reference.objects.all(), include_network_checks=False)
        assert set(report) == {"duplicates", "missing_fields", "doi_resolution", "retractions"}
        assert report["doi_resolution"] == []
