"""#411 — where a paper appears: backlinks for references."""

import pytest

from literature.models import Reference
from literature.usage import usage_of
from notes.models import Note, QuickCapture
from projects.models import DecisionRecord, Project
from research.models import Evidence, ExperimentEntry, Hypothesis, Protocol
from writing.models import Manuscript, ManuscriptReference

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings, django_user_model):
    settings.ATLAS_API_KEY = KEY
    django_user_model.objects.create_superuser("owner", password="pw")
    project = Project.objects.create(name="Attention")
    ref = Reference.objects.create(title="Load theory", bibtex_key="lavie2010attention", year=2010)
    other = Reference.objects.create(title="Longer key", bibtex_key="lavie2010attentionb")
    linked = Note.objects.create(project=project, title="Linked note", body="no mention")
    linked.references.add(ref)
    Note.objects.create(project=project, title="Citing note", body="see @lavie2010attention.")
    Note.objects.create(project=project, title="Prefix only", body="see @lavie2010attentionb")
    DecisionRecord.objects.create(
        project=project, title="Dual task", decision="because @lavie2010attention"
    )
    ExperimentEntry.objects.create(project=project, title="Pilot", body="cf. @lavie2010attention")
    Protocol.objects.create(project=project, title="Procedure", body="after @lavie2010attention")
    QuickCapture.objects.create(text="re-read @lavie2010attention\nsoon")
    ms = Manuscript.objects.create(project=project, title="Paper one")
    ManuscriptReference.objects.create(manuscript=ms, reference=ref)
    hyp = Hypothesis.objects.create(project=project, statement="Load costs are strategic")
    Evidence.objects.create(hypothesis=hyp, direction="supports", summary="pilot", reference=ref)
    return project, ref, other


def test_usage_collects_every_kind_and_respects_whole_keys(world):
    project, ref, other = world
    out = usage_of(ref)
    kinds = {(r["kind"], r["title"]) for r in out["rows"]}
    assert ("note", "Linked note") in kinds and ("note", "Citing note") in kinds
    assert ("note", "Prefix only") not in kinds  # @lavie2010attentionb is another paper
    assert ("decision", "Dual task") in kinds and ("experiment", "Pilot") in kinds
    assert ("protocol", "Procedure v1") in kinds and ("manuscript", "Paper one") in kinds
    assert ("evidence", "Load costs are strategic") in kinds
    assert any(r["kind"] == "capture" and r["url"] == "/inbox" for r in out["rows"])
    assert out["total"] == 8 and out["counts"]["note"] == 2
    hows = {r["title"]: r["how"] for r in out["rows"]}
    assert hows["Linked note"] == "linked" and hows["Citing note"] == "mentioned"
    assert hows["Paper one"] == "bibliography" and hows["Load costs are strategic"] == "supports"
    note_row = next(r for r in out["rows"] if r["title"] == "Citing note")
    assert note_row["url"].startswith(f"/projects/{project.slug}/notes/")
    assert out["rows"][0]["kind"] == "manuscript"  # manuscripts first: the costliest place to break
    assert usage_of(other)["total"] == 1 and usage_of(other)["rows"][0]["title"] == "Prefix only"


def test_usage_api_and_ui_wiring(client, world):
    _, ref, _ = world
    r = client.get(f"/api/v1/references/{ref.pk}/usage/", **HEADERS)
    assert r.status_code == 200 and r.json()["total"] == 8 and r.json()["key"] == ref.bibtex_key
    src = open("frontend/src/app/pages/Reference.tsx").read()
    assert (
        "/usage/" in src
        and 'data-testid="usage-section"' in src
        and 'data-testid="usage-row"' in src
    )
    server = open("mcp_server/server.py").read()
    assert "def get_reference_usage(" in server
