"""#439: comments can be resolved (PATCH) and are found by global search on both paths."""

import pytest
from django.contrib.contenttypes.models import ContentType

from core.models import Comment
from literature.models import Reference
from notes.models import Note
from projects.tests.factories import ProjectFactory
from writing.models import ManuscriptFile
from writing.tests.factories import ManuscriptFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


def _seed():
    project = ProjectFactory(name="Tide pools")
    note = Note.objects.create(project=project, title="Anemone notes", body="x")
    ref = Reference.objects.create(title="Anemones", bibtex_key="anem2020")
    ms = ManuscriptFactory(project=project, title="Paper")
    tex = ManuscriptFile.objects.create(manuscript=ms, path="main.tex", content="x", kind="tex")
    a = Comment.objects.create(target=note, body="check the anemone permit remark")
    b = Comment.objects.create(target=ref, body="anemone density looks off")
    c = Comment.objects.create(target=tex, body="tighten the anemone paragraph", page=12)
    return project, note, ref, ms, a, b, c


@pytest.mark.django_db
def test_icontains_path_finds_comments_with_routes():
    from core.search import _icontains_search, describe

    project, note, ref, ms, a, b, c = _seed()
    rows = [r for r in _icontains_search("anemone") if r["type"] == "comment"]
    assert {r["object"].pk for r in rows} == {a.pk, b.pk, c.pk}
    by = {r["object"].pk: r for r in rows}
    assert by[a.pk]["project"] == project
    d = describe(by[a.pk], "anemone")
    assert d["app_url"] == f"/projects/{project.slug}/notes/{note.pk}" and d["meta"] == "open"
    assert describe(by[b.pk], "anemone")["app_url"] == f"/references/{ref.pk}"
    dc = describe(by[c.pk], "anemone")
    assert dc["app_url"] == f"/manuscripts/{ms.pk}/editor" and "line 12" in dc["where"]


@pytest.mark.django_db
def test_fts_path_finds_comments():
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("FTS path is Postgres-only")
    from core.search import search_all

    _seed()
    assert sum(1 for r in search_all("anemone") if r["type"] == "comment") == 3


@pytest.mark.django_db
def test_search_api_lists_comments(client, owner):
    _seed()
    data = client.get("/api/v1/search/?q=anemone", **HEADERS).json()
    kinds = {r["type"] for r in data["results"]}
    assert "comment" in kinds


@pytest.mark.django_db
def test_resolve_reopen_and_rows_carry_resolved_at(client, owner):
    project, note, ref, ms, a, b, c = _seed()
    r = client.patch(
        f"/api/v1/comments/{c.pk}/", {"resolved": True}, content_type="application/json", **HEADERS
    )
    assert r.status_code == 200 and r.json()["resolved_at"]
    c.refresh_from_db()
    assert c.resolved
    rows = client.get(f"/api/v1/manuscripts/{ms.pk}/comments/", **HEADERS).json()["comments"]
    assert rows[0]["resolved_at"] is not None
    listed = client.get(f"/api/v1/comments/reference/{ref.pk}/", **HEADERS).json()["comments"]
    assert listed[0]["resolved_at"] is None
    from core.search import _icontains_search, describe

    row = next(r for r in _icontains_search("tighten") if r["type"] == "comment")
    assert describe(row, "tighten")["meta"] == "resolved"
    back = client.patch(
        f"/api/v1/comments/{c.pk}/", {"resolved": False}, content_type="application/json", **HEADERS
    )
    assert back.status_code == 200 and back.json()["resolved_at"] is None
    bad = client.patch(
        f"/api/v1/comments/{c.pk}/", {"resolved": "yes"}, content_type="application/json", **HEADERS
    )
    assert bad.status_code == 400
    assert (
        client.patch(
            "/api/v1/comments/999999/",
            {"resolved": True},
            content_type="application/json",
            **HEADERS,
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_target_route_survives_a_deleted_target():
    project, note, ref, ms, a, b, c = _seed()
    ct = ContentType.objects.get_for_model(Note)
    orphan = Comment.objects.create(content_type=ct, object_id=999999, body="gone")
    assert orphan.target_route() == (None, None)


def test_ui_wiring():
    from pathlib import Path

    from django.conf import settings

    app = Path(settings.BASE_DIR) / "frontend" / "src" / "app"
    studio = (app / "pages" / "Studio.tsx").read_text()
    for needle in (
        "resolveComment",
        'data-testid="comment-resolve"',
        "!c.resolved_at",
        "data-resolved",
    ):
        assert needle in studio, needle
    reference = (app / "pages" / "Reference.tsx").read_text()
    assert 'data-testid="comment-resolve"' in reference
    search = (app / "pages" / "Search.tsx").read_text()
    assert 'comment: "Comments"' in search
