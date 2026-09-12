"""Library v2 slice 3: the three discovery lenses, export, and bulk PDF fetch."""

import httpx
import pytest

from literature import discover, library
from literature.models import Reference


def _work(i, doi=None, cites=5, title=None):
    return {
        "id": f"https://openalex.org/W{i}",
        "title": title or f"Work {i}",
        "doi": f"https://doi.org/{doi}" if doi else None,
        "publication_year": 2000 + i,
        "cited_by_count": cites,
        "authorships": [
            {"author": {"display_name": f"Author {i}"}},
            {"author": {"display_name": "B"}},
            {"author": {"display_name": "C"}},
            {"author": {"display_name": "D"}},
        ],
        "primary_location": {"source": {"display_name": "Venue"}},
    }


def _client(routes):
    """routes: list of (predicate(request) -> bool, response json)."""
    calls = []

    def handler(request):
        calls.append(str(request.url))
        for pred, payload in routes:
            if pred(request):
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={})

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


@pytest.fixture
def anchor(db):
    return Reference.objects.create(title="Anchor", bibtex_key="anchor", doi="10.1/anchor")


def test_discover_references_resolves_id_then_batches_works(anchor):
    known = Reference.objects.create(title="Known", bibtex_key="known", doi="10.1/known")
    client, calls = _client(
        [
            (
                lambda r: r.url.path.endswith("/works/doi:10.1/anchor"),
                {"id": "https://openalex.org/W1"},
            ),
            (
                lambda r: r.url.path.endswith("/works/W1"),
                {
                    "referenced_works": [
                        "https://openalex.org/W2",
                        "https://openalex.org/W3",
                        "https://openalex.org/W4",
                    ]
                },
            ),
            (
                lambda r: (
                    r.url.path.endswith("/works")
                    and "openalex_id" in r.url.params.get("filter", "")
                ),
                {"results": [_work(2, "10.1/known"), _work(3, "10.1/new"), _work(4)]},
            ),
        ]
    )
    rows = discover.discover(anchor, "references", client=client)
    anchor.refresh_from_db()
    assert anchor.openalex_id == "W1"  # remembered for next time
    assert [r["title"] for r in rows] == ["Work 2", "Work 3", "Work 4"]
    assert rows[0]["in_library"] and rows[0]["library_id"] == known.pk and not rows[0]["addable"]
    assert rows[1]["addable"] and rows[1]["doi"] == "10.1/new"
    assert not rows[2]["addable"] and rows[2]["doi"] == ""  # no DOI → show, can't add
    assert rows[0]["authors"] == ["Author 2", "B", "C"] and rows[0]["more_authors"] == 1
    assert rows[0]["venue"] == "Venue"


def test_rows_unescape_html_entities_from_openalex(db):
    work = _work(1, "10.1/one", title="K&uuml;nstliche &amp; Natural")
    work["primary_location"] = {"source": {"display_name": "K&uuml;nstliche Intell."}}
    row = discover._rows([work])[0]
    assert row["title"] == "Künstliche & Natural" and row["venue"] == "Künstliche Intell."


def test_discover_cited_by_uses_the_cites_filter(anchor):
    anchor.openalex_id = "W1"
    anchor.save()
    client, calls = _client(
        [
            (
                lambda r: r.url.params.get("filter") == "cites:W1",
                {"results": [_work(9, "10.1/nine", cites=99)]},
            ),
        ]
    )
    rows = discover.discover(anchor, "cited_by", client=client)
    assert len(calls) == 1  # id already known → no resolution request
    assert rows[0]["citations"] == 99 and rows[0]["addable"]


def test_discover_similar_excludes_the_anchor_itself(anchor):
    anchor.openalex_id = "W1"
    anchor.save()
    client, _ = _client(
        [
            (
                lambda r: r.url.path.endswith("/works/W1"),
                {"related_works": ["https://openalex.org/W1", "https://openalex.org/W5"]},
            ),
            (
                lambda r: r.url.path.endswith("/works"),
                {"results": [_work(1, "10.1/anchor"), _work(5, "10.1/five")]},
            ),
        ]
    )
    rows = discover.discover(anchor, "similar", client=client)
    assert [r["title"] for r in rows] == ["Work 5"]


def test_discover_without_identifier_is_empty_and_offline_explains(db):
    stub = Reference.objects.create(title="Stub", bibtex_key="stub")
    assert discover.discover(stub, "similar") == []

    def boom(request):
        raise httpx.ConnectError("offline", request=request)

    ref = Reference.objects.create(title="R", bibtex_key="r", doi="10.1/r")
    with pytest.raises(discover.DiscoverError, match="unreachable"):
        discover.discover(ref, "cited_by", client=httpx.Client(transport=httpx.MockTransport(boom)))


def test_rate_limited_list_query_falls_back_to_single_lookups(anchor):
    # OpenAlex meters list queries per day; single-work lookups keep answering
    anchor.openalex_id = "W1"
    anchor.save()
    limited = {"error": "Rate limit exceeded", "retryAfter": 7200}

    def handler(request):
        if request.url.path.endswith("/works/W1"):
            return httpx.Response(
                200,
                json={"referenced_works": ["https://openalex.org/W2", "https://openalex.org/W3"]},
            )
        if request.url.path.endswith("/works"):
            return httpx.Response(429, json=limited)
        wid = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=_work(int(wid[1:]), f"10.1/{wid}"))

    rows = discover.discover(
        anchor, "references", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert [r["title"] for r in rows] == ["Work 2", "Work 3"]


def test_rate_limited_cited_by_explains_with_retry_time(anchor):
    anchor.openalex_id = "W1"
    anchor.save()

    def handler(request):
        return httpx.Response(429, json={"error": "Rate limit exceeded", "retryAfter": 7200})

    with pytest.raises(discover.DiscoverError, match="about 2 h.*ATLAS_OPENALEX_API_KEY"):
        discover.discover(
            anchor, "cited_by", client=httpx.Client(transport=httpx.MockTransport(handler))
        )


def test_client_passes_the_optional_api_key(settings):
    settings.ATLAS_OPENALEX_API_KEY = "k-123"
    with discover._client() as c:
        assert dict(c.params)["api_key"] == "k-123"
    settings.ATLAS_OPENALEX_API_KEY = ""
    with discover._client() as c:
        assert "api_key" not in dict(c.params)


def test_discover_rejects_unknown_kind(anchor):
    with pytest.raises(ValueError):
        discover.discover(anchor, "bogus")


def test_legacy_discover_similar_keeps_its_shape(anchor, monkeypatch):
    monkeypatch.setattr(
        discover,
        "discover",
        lambda ref, kind, limit=12, client=None: [
            {
                "doi": "10.1/x",
                "title": "X",
                "year": 2020,
                "citations": 3,
                "authors": ["A"],
                "addable": True,
            },
            {
                "doi": "",
                "title": "Y",
                "year": 2020,
                "citations": 3,
                "authors": [],
                "addable": False,
            },
        ],
    )
    assert discover.discover_similar(anchor) == [
        {"doi": "10.1/x", "title": "X", "year": 2020, "citations": 3, "first_author": "A"}
    ]


def test_export_bibtex_renders_every_reference(db):
    a = Reference.objects.create(
        title="Alpha", bibtex_key="alpha2020", year=2020, authors=[{"family": "A", "given": "B"}]
    )
    b = Reference.objects.create(title="Beta", bibtex_key="beta2019", year=2019)
    text = library.export_bibtex([a, b])
    assert "@" in text and "alpha2020" in text and "beta2019" in text and text.endswith("\n")
    assert library.export_bibtex([]) == ""


def test_bulk_fetch_pdf_queues_only_pdf_less_references(db, monkeypatch):
    from django.core.files.base import ContentFile

    from literature import tasks

    a = Reference.objects.create(title="A", bibtex_key="a")
    b = Reference.objects.create(title="B", bibtex_key="b")
    b.pdf.save("b.pdf", ContentFile(b"%PDF-1.4"), save=True)
    queued = []
    monkeypatch.setattr(tasks, "fetch_oa_pdf_task", lambda pk: queued.append(pk))
    out = library.bulk([a.pk, b.pk], "fetch_pdf")
    assert out["affected"] == 1 and queued == [a.pk]
