"""#446 (backlog #128): duplicate a manuscript — sources, assets, limits, bibliography links."""

import pytest
from django.core.files.base import ContentFile

from literature.models import Reference
from projects.tests.factories import ProjectFactory
from writing.models import Manuscript, ManuscriptFile, ManuscriptReference
from writing.services import duplicate_manuscript
from writing.tests.factories import ManuscriptFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


@pytest.fixture(autouse=True)
def api_key(settings, tmp_path):
    settings.ATLAS_API_KEY = KEY
    settings.MEDIA_ROOT = str(tmp_path / "media")


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.fixture
def source(db):
    ms = ManuscriptFactory(title="Original", target_venue="Cognition", venue_limits={"words": 8000})
    ms.status = Manuscript.Status.SUBMITTED
    ms.compile_log = "old log"
    ms.save()
    ManuscriptFile.objects.create(
        manuscript=ms, path="main.tex", content="\\input{sections/a}", kind="tex", is_main=True
    )
    ManuscriptFile.objects.create(manuscript=ms, path="sections/a.tex", content="A", kind="tex")
    fig = ManuscriptFile(manuscript=ms, path="figures/pilot.png", kind="asset")
    fig.asset.save("pilot.png", ContentFile(PNG), save=False)
    fig.save()
    ref = Reference.objects.create(title="R", bibtex_key="r2020")
    ManuscriptReference.objects.create(manuscript=ms, reference=ref, cite_key_override="mine")
    return ms


def test_service_copies_everything_that_belongs_to_a_skeleton(source):
    copy = duplicate_manuscript(source, title="Second paper")
    assert copy.pk != source.pk and copy.project == source.project
    assert copy.title == "Second paper" and copy.status == Manuscript.Status.IDEA
    assert copy.target_venue == "Cognition" and copy.venue_limits == {"words": 8000}
    assert copy.compile_log == "" and copy.compiled_pdf.name in ("", None)
    paths = dict(copy.files.values_list("path", "content"))
    assert paths == {
        "main.tex": "\\input{sections/a}",
        "sections/a.tex": "A",
        "figures/pilot.png": "",
    }
    assert copy.files.get(path="main.tex").is_main
    asset = copy.files.get(path="figures/pilot.png")
    assert asset.kind == "asset" and asset.asset and asset.asset.read() == PNG
    assert (
        asset.asset.name != source.files.get(path="figures/pilot.png").asset.name
    )  # its own bytes
    link = copy.manuscriptreference_set.get()
    assert link.reference.bibtex_key == "r2020" and link.cite_key == "mine"
    copy.refresh_from_db()
    assert copy.root_folder_id is not None  # the tree mirror ran for the copy
    assert source.files.count() == 3 and source.manuscriptreference_set.count() == 1


def test_service_defaults_and_options(source):
    other = ProjectFactory()
    copy = duplicate_manuscript(source, project=other, bibliography=False)
    assert copy.title == "Copy of Original" and copy.project == other
    assert copy.manuscriptreference_set.count() == 0


@pytest.mark.django_db
def test_api_duplicates_and_validates(client, owner, source):
    r = client.post(
        f"/api/v1/manuscripts/{source.pk}/duplicate/",
        {"title": "Via API"},
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["title"] == "Via API" and body["status"] == "idea" and body["id"] != source.pk
    assert Manuscript.objects.get(pk=body["id"]).files.count() == 3
    bad = client.post(
        f"/api/v1/manuscripts/{source.pk}/duplicate/",
        {"project": "no-such-project"},
        content_type="application/json",
        **HEADERS,
    )
    assert bad.status_code == 400


def test_mcp_tool_posts_the_options(monkeypatch):
    from mcp_server import client as mcp_client
    from mcp_server import server

    seen = {}
    monkeypatch.setattr(mcp_client, "_request", lambda m, p, **kw: seen.update(kw, path=p) or {})
    server.duplicate_manuscript(5, title="T", project="p", bibliography=False)
    assert seen["path"] == "/manuscripts/5/duplicate/"
    assert seen["json"] == {"bibliography": False, "title": "T", "project": "p"}


def test_writing_page_offers_duplicate():
    from pathlib import Path

    from django.conf import settings as dj

    src = (Path(dj.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Writing.tsx").read_text()
    assert 'label: "Duplicate…"' in src and "/duplicate/`" in src
