"""#502 — link hygiene: renames follow their links; unlinked mentions become links."""

from pathlib import Path

import pytest

from notes.models import Note, NoteLink, QuickCapture
from notes.relink import link_mentions, rename_links
from notes.services import sync_note_links
from projects.models import DecisionRecord
from projects.tests.factories import ProjectFactory
from research.models import ExperimentEntry

pytestmark = pytest.mark.django_db


def _project():
    p = ProjectFactory(slug="attention")
    target = Note.objects.create(project=p, title="Load theory", body="The claim.")
    a = Note.objects.create(
        project=p, title="Alpha", body="See [[Load theory]] and [[load theory|the theory]]."
    )
    b = Note.objects.create(project=p, title="Beta", body="Load theory says so; Load Theory again.")
    for n in (a, b):
        sync_note_links(n)
    DecisionRecord.objects.create(
        project=p, title="D", decision="Per [[Load theory]] we drop block 3.", context="x"
    )
    ExperimentEntry.objects.create(project=p, title="E", body="Pilot; cf. [[ Load theory ]].")
    QuickCapture.objects.create(project=p, text="reread [[Load theory]] tonight")
    other = ProjectFactory(slug="other")
    Note.objects.create(project=other, title="Elsewhere", body="[[Load theory]] here must stay.")
    return p, target, a, b


def test_rename_links_rewrites_every_link_in_the_project_and_keeps_aliases():
    p, target, a, b = _project()
    target.title = "Perceptual load"
    target.save()
    out = rename_links(p, "Load theory", "Perceptual load")
    assert out == {"links": 5, "notes": 1, "decisions": 1, "experiments": 1, "captures": 1}
    a.refresh_from_db()
    assert a.body == "See [[Perceptual load]] and [[Perceptual load|the theory]]."
    assert set(NoteLink.objects.filter(source=a).values_list("target_id", flat=True)) == {target.pk}
    assert (
        DecisionRecord.objects.get(title="D").decision == "Per [[Perceptual load]] we drop block 3."
    )
    assert ExperimentEntry.objects.get(title="E").body == "Pilot; cf. [[Perceptual load]]."
    assert QuickCapture.objects.get(project=p).text == "reread [[Perceptual load]] tonight"
    b.refresh_from_db()
    assert "[[" not in b.body  # plain mentions are not links; they are left alone
    assert Note.objects.get(title="Elsewhere").body == "[[Load theory]] here must stay."
    # a case-only rename changes nothing; blank titles are ignored
    assert rename_links(p, "Perceptual load", "perceptual LOAD")["links"] == 0
    assert rename_links(p, "", "x")["links"] == 0


def test_link_mentions_wraps_the_first_plain_mention_and_syncs():
    p, target, a, b = _project()
    out = link_mentions(target)
    assert out == {"linked": [{"id": b.pk, "title": "Beta"}]}
    b.refresh_from_db()
    assert b.body == "[[Load theory]] says so; Load Theory again."
    assert NoteLink.objects.filter(source=b, target=target).exists()
    assert link_mentions(target)["linked"] == []  # nothing left to link
    c = Note.objects.create(
        project=p, title="Gamma", body="Overloaded: Load theoryx and Load theory."
    )
    d = Note.objects.create(project=p, title="Delta", body="Load theory too")
    assert link_mentions(target, source_ids=[d.pk])["linked"] == [{"id": d.pk, "title": "Delta"}]
    c.refresh_from_db()
    assert "[[" not in c.body  # only Delta was asked for
    assert link_mentions(target)["linked"] == [{"id": c.pk, "title": "Gamma"}]
    c.refresh_from_db()
    assert c.body == "Overloaded: Load theoryx and [[Load theory]]."  # the glued one is not a word


def test_api_rename_reports_relinked_and_link_mentions_action(client, settings, django_user_model):
    p, target, a, b = _project()
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("atlas", "a@b.c", "atlas")
    hdr = {"HTTP_X_API_KEY": "k", "HTTP_HOST": "127.0.0.1"}
    url = f"/api/v1/notes/{target.id}/"
    r = client.post(
        url + "link-mentions/", {"sources": "x"}, content_type="application/json", **hdr
    )
    assert r.status_code == 400
    r = client.post(url + "link-mentions/", {}, content_type="application/json", **hdr)
    assert r.status_code == 200 and [x["title"] for x in r.json()["linked"]] == ["Beta"]
    r = client.patch(url, {"title": "Perceptual load"}, content_type="application/json", **hdr)
    assert r.status_code == 200 and r.json()["relinked"]["links"] == 6  # Beta's new link too
    r = client.patch(url, {"body": "edited"}, content_type="application/json", **hdr)
    assert r.status_code == 200 and r.json()["relinked"] is None
    anon = client.post(
        url + "link-mentions/", {}, content_type="application/json", HTTP_HOST="127.0.0.1"
    )
    assert anon.status_code == 401
    tsx = Path("frontend/src/app/pages/Notes.tsx").read_text()
    for needle in (
        "/link-mentions/",
        'data-testid="link-mention"',
        'data-testid="link-all-mentions"',
        "relinked",
    ):
        assert needle in tsx, needle
