"""Research v2 slice 1 — writable hypothesis ledger, evidence, experiments, datasets."""

import pytest

from literature.tests.factories import ReferenceFactory
from notes.models import Note
from projects.tests.factories import ProjectFactory
from research.models import Dataset, Evidence, ExperimentEntry, Hypothesis

pytestmark = pytest.mark.django_db
H = {"HTTP_X_API_KEY": "k", "content_type": "application/json"}


@pytest.fixture
def world(settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    return ProjectFactory(slug="deep")


def test_hypothesis_crud_and_suggested_status(client, world):
    made = client.post(
        "/api/v1/hypotheses/", {"project": "deep", "statement": "Load is strategic"}, **H
    )
    assert (
        made.status_code == 201
        and made.json()["status"] == "proposed"
        and made.json()["suggested_status"] is None
    )
    hid = made.json()["id"]
    ref = ReferenceFactory(bibtex_key="lavie2010attention", title="Load")
    note = Note.objects.create(project=world, title="Pilot", body="")
    ev = client.post(
        "/api/v1/evidence/",
        {
            "hypothesis": hid,
            "direction": "supports",
            "summary": "n=12 pilot agrees",
            "reference": ref.pk,
            "note": note.pk,
        },
        **H,
    )
    assert (
        ev.status_code == 201
        and ev.json()["reference_detail"]["bibtex_key"] == "lavie2010attention"
        and ev.json()["note_title"] == "Pilot"
    )
    client.post(
        "/api/v1/evidence/",
        {"hypothesis": hid, "direction": "contradicts", "summary": "RT data disagree"},
        **H,
    )
    got = client.get(f"/api/v1/hypotheses/{hid}/", HTTP_X_API_KEY="k").json()
    assert (got["supports"], got["contradicts"], got["mixed"]) == (1, 1, 0) and got[
        "suggested_status"
    ] == "inconclusive"
    assert len(got["evidence"]) == 2 and got["evidence"][-1]["reference_detail"]["title"] == "Load"
    patched = client.patch(f"/api/v1/hypotheses/{hid}/", {"status": "testing"}, **H)
    assert patched.status_code == 200 and Hypothesis.objects.get(pk=hid).status == "testing"
    listed = client.get("/api/v1/evidence/?project=deep", HTTP_X_API_KEY="k").json()
    assert listed["count"] == 2
    assert (
        client.delete(f"/api/v1/evidence/{ev.json()['id']}/", HTTP_X_API_KEY="k").status_code == 204
    )
    assert Evidence.objects.count() == 1
    assert client.delete(f"/api/v1/hypotheses/{hid}/", HTTP_X_API_KEY="k").status_code == 204
    assert not Hypothesis.objects.exists() and not Evidence.objects.exists()


def test_experiments_and_datasets_are_writable(client, world):
    h = Hypothesis.objects.create(project=world, statement="H1")
    made = client.post(
        "/api/v1/experiments/",
        {"project": "deep", "title": "Pilot run", "body": "n=12", "hypotheses": [h.pk]},
        **H,
    )
    assert made.status_code == 201, made.content
    entry = ExperimentEntry.objects.get(pk=made.json()["id"])
    assert (
        entry.project == world
        and list(entry.hypotheses.all()) == [h]
        and made.json()["date"] == str(entry.date)
    )
    ds = client.post(
        "/api/v1/datasets/",
        {"project": "deep", "name": "pilot.csv", "location": "data/pilot.csv"},
        **H,
    )
    assert ds.status_code == 201 and Dataset.objects.get(pk=ds.json()["id"]).project == world
    patched = client.patch(f"/api/v1/experiments/{entry.pk}/", {"body": "n=12, clean"}, **H)
    assert patched.status_code == 200 and patched.json()["body"] == "n=12, clean"


def test_evidence_changes_bust_hypothesis_etag(client, world, settings):
    """Regression: adding evidence used to leave the hypothesis list ETag unchanged (304 → stale UI)."""
    settings.ATLAS_API_KEY = "k"
    made = client.post(
        "/api/v1/hypotheses/", {"project": world.slug, "statement": "ETag moves"}, **H
    )
    hid = made.json()["id"]
    url = f"/api/v1/hypotheses/?project={world.slug}"
    first = client.get(url, HTTP_X_API_KEY="k")
    assert first.status_code == 200 and first["ETag"]
    assert client.get(url, HTTP_X_API_KEY="k", HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304
    ev = client.post(
        "/api/v1/evidence/", {"hypothesis": hid, "direction": "supports", "summary": "pilot"}, **H
    )
    assert ev.status_code == 201
    again = client.get(url, HTTP_X_API_KEY="k", HTTP_IF_NONE_MATCH=first["ETag"])
    assert again.status_code == 200 and again.json()["results"][0]["supports"] == 1
    client.delete(f"/api/v1/evidence/{ev.json()['id']}/", HTTP_X_API_KEY="k")
    assert client.get(url, HTTP_X_API_KEY="k", HTTP_IF_NONE_MATCH=again["ETag"]).status_code == 200
