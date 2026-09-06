"""Library v2 slice 5: tags (global labels) and smart views (saved filter sets)."""

import pytest

from literature import library
from literature.models import LibraryTag, Reference, SavedView

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.fixture
def refs(db):
    a = Reference.objects.create(title="Alpha attention", bibtex_key="a", year=2020)
    b = Reference.objects.create(title="Beta memory", bibtex_key="b", year=2019)
    return a, b


def test_get_or_create_named_is_case_insensitive_and_trims(db):
    t1 = LibraryTag.get_or_create_named("  Load  theory ")
    t2 = LibraryTag.get_or_create_named("load THEORY")
    assert t1.pk == t2.pk and t1.name == "Load theory"
    with pytest.raises(ValueError):
        LibraryTag.get_or_create_named("   ")


def test_bulk_tag_untag_and_filters(refs):
    a, b = refs
    out = library.bulk([a.pk, b.pk], "tag", value="to-cite")
    assert out["affected"] == 2 and LibraryTag.objects.count() == 1
    assert (
        library.bulk([a.pk], "tag", value="TO-CITE")["affected"] == 0
    )  # idempotent, case-insensitive
    qs = Reference.objects.all()
    assert list(library.filter_references(qs, {"tag": "to-cite", "sort": "title"})) == [a, b]
    assert library.bulk([a.pk], "untag", value="to-cite")["affected"] == 1
    assert list(library.filter_references(qs, {"tag": "to-cite"})) == [b]
    assert list(library.filter_references(qs, {"untagged": "true"})) == [a]
    with pytest.raises(ValueError):
        library.bulk([a.pk], "tag", value="")


def test_facets_include_tags_untagged_and_views(refs):
    a, b = refs
    library.bulk([a.pk], "tag", value="pilot")
    SavedView.objects.create(name="Pilot papers", params={"tag": "pilot"}, position=1)
    f = library.facets(Reference.objects.all())
    assert f["tags"] == [{"name": "pilot", "color": "", "count": 1}]
    assert f["untagged"] == 1
    assert f["views"][0]["name"] == "Pilot papers" and f["views"][0]["params"] == {"tag": "pilot"}


@pytest.mark.django_db
def test_reference_serializer_reads_and_writes_tags(client, owner, refs):
    a, b = refs
    data = client.patch(
        f"/api/v1/references/{a.pk}/",
        {"tags": ["Pilot", "load"]},
        content_type="application/json",
        **HEADERS,
    ).json()
    assert data["tags"] == ["load", "Pilot"] or sorted(data["tags"], key=str.lower) == [
        "load",
        "Pilot",
    ]
    assert LibraryTag.objects.count() == 2
    listed = client.get("/api/v1/references/?tag=pilot", **HEADERS).json()["results"]
    assert [r["id"] for r in listed] == [a.pk]
    created = client.post(
        "/api/v1/references/",
        {"title": "Gamma", "entry_type": "misc", "authors": [], "tags": ["new-tag"]},
        content_type="application/json",
        **HEADERS,
    ).json()
    assert created["tags"] == ["new-tag"]


@pytest.mark.django_db
def test_tag_and_view_endpoints(client, owner, refs):
    a, b = refs
    library.bulk([a.pk, b.pk], "tag", value="core")
    tags = client.get("/api/v1/library-tags/", **HEADERS).json()["results"]
    assert tags[0]["name"] == "core" and tags[0]["count"] == 2
    again = client.post(
        "/api/v1/library-tags/", {"name": "CORE"}, content_type="application/json", **HEADERS
    )
    assert again.status_code == 201 and LibraryTag.objects.count() == 1  # reused, not duplicated
    view = client.post(
        "/api/v1/library-views/",
        {"name": "Core 2020", "params": {"tag": "core", "year": "2020"}},
        content_type="application/json",
        **HEADERS,
    ).json()
    assert view["position"] == 1
    second = client.post(
        "/api/v1/library-views/",
        {"name": "Older", "params": {"year_max": "2019"}},
        content_type="application/json",
        **HEADERS,
    ).json()
    assert second["position"] == 2
    assert (
        client.get("/api/v1/references/facets/", **HEADERS).json()["views"][0]["name"]
        == "Core 2020"
    )
    assert client.delete(f"/api/v1/library-views/{view['id']}/", **HEADERS).status_code == 204


def test_ui_wiring():
    from pathlib import Path

    from django.conf import settings

    src = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Library.tsx"
    ).read_text()
    for needle in (
        "Smart views",
        "/library-views/",
        "library-tag-names",
        'action: "tag"',
        "Untagged",
    ):
        assert needle in src, needle
    chunks = " ".join(
        p.read_text(errors="ignore")
        for p in (Path(settings.BASE_DIR) / "static" / "js" / "islands").glob("Library*.js")
    )
    assert "Smart views" in chunks and "/library-views/" in chunks
