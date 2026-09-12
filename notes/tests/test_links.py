"""Notes v2 slice 1 — @cite-keys, the link panel, autocomplete, unwritten titles API."""

import pytest

from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from notes import services
from notes.models import Note
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
KEY = "k"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture
def world(settings, django_user_model):
    settings.ATLAS_API_KEY = KEY
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    lavie = ReferenceFactory(bibtex_key="lavie2010attention", title="Load theory")
    ProjectReferenceFactory(project=project, reference=lavie)
    other = ReferenceFactory(bibtex_key="smith2020survey", title="A survey")
    return project, lavie, other


def test_parse_cite_keys():
    assert services.parse_cite_keys(
        "See @lavie2010attention and @Smith2020survey. Not me@x.com or a/@path"
    ) == [
        "lavie2010attention",
        "Smith2020survey",
    ]
    assert services.parse_cite_keys("@lavie2010attention, again @LAVIE2010attention") == [
        "lavie2010attention"
    ]


def test_sync_note_references_is_additive_and_case_insensitive(world):
    project, lavie, other = world
    note = Note.objects.create(
        project=project, title="Load", body="Per @LAVIE2010attention and @nobody2000x"
    )
    assert services.sync_note_references(note) == ["nobody2000x"]
    assert list(note.references.all()) == [lavie]
    note.body = "no citations any more"
    note.save()
    services.sync_note_references(note)
    assert list(note.references.all()) == [lavie]  # additive: manual/previous links survive


def test_note_links_panel(world):
    project, lavie, _ = world
    hub = Note.objects.create(
        project=project,
        title="Hub",
        body="Links [[Spoke]] and [[Missing one]]; cites @lavie2010attention and @ghost99",
    )
    spoke = Note.objects.create(project=project, title="Spoke", body="Back to [[Hub]]")
    mention = Note.objects.create(
        project=project, title="Aside", body="The hub matters but I did not link it."
    )
    for n in (hub, spoke, mention):
        services.sync_note_links(n)
        services.sync_note_references(n)
    panel = services.note_links(hub)
    assert panel["outgoing"] == [{"id": spoke.pk, "title": "Spoke"}]
    assert panel["backlinks"] == [{"id": spoke.pk, "title": "Spoke"}]
    assert panel["references"][0]["bibtex_key"] == "lavie2010attention"
    assert panel["unresolved"] == ["Missing one"] and panel["unresolved_keys"] == ["ghost99"]
    assert panel["mentions"] == [{"id": mention.pk, "title": "Aside"}]


def test_suggest(world):
    project, lavie, other = world
    Note.objects.create(project=project, title="Load theory notes", body="first line\nsecond")
    Note.objects.create(project=project, title="Methods", body="")
    assert [s["label"] for s in services.suggest(project, "load")] == ["Load theory notes"]
    assert services.suggest(project, "load")[0]["sublabel"] == "first line"
    assert [s["label"] for s in services.suggest(project, "", kind="reference")] == [
        "lavie2010attention"
    ]
    assert services.suggest(project, "survey", kind="reference") == []  # not filed in the project


def test_notes_api_endpoints(client, world):
    project, lavie, _ = world
    created = client.post(
        "/api/v1/notes/",
        {"project": "deep", "title": "Hub", "body": "[[Nowhere]] and @lavie2010attention"},
        content_type="application/json",
        **HEADERS,
    )
    assert created.status_code == 201
    nid = created.json()["id"]
    assert (
        created.json()["references_detail"] == []
        or created.json()["references_detail"][0]["bibtex_key"] == "lavie2010attention"
    )
    got = client.get(f"/api/v1/notes/{nid}/", **HEADERS).json()
    assert got["references_detail"][0]["bibtex_key"] == "lavie2010attention"
    links = client.get(f"/api/v1/notes/{nid}/links/", **HEADERS).json()
    assert links["unresolved"] == ["Nowhere"] and links["references"][0]["id"] == lavie.pk
    sugg = client.get("/api/v1/notes/suggest/?project=deep&q=hu", **HEADERS).json()
    assert sugg[0]["label"] == "Hub"
    unwritten = client.get("/api/v1/notes/unwritten/?project=deep", **HEADERS).json()
    assert unwritten == {"titles": ["Nowhere"]}
    html = client.post(
        "/api/v1/notes/preview/",
        {"body": "cite @lavie2010attention and @ghost", "project": "deep"},
        content_type="application/json",
        **HEADERS,
    ).json()["html"]
    assert f"/library/{lavie.pk}/" in html and "<em>@ghost</em>" in html
