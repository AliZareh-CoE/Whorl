"""#505 — note history: snapshots, coalescing, diffs and restore."""

from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from notes.history import COALESCE_MINUTES, KEEP, restore, revision_diff, revision_rows, snapshot
from notes.models import Note, NoteLink, NoteRevision
from notes.services import sync_note_links
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def _age(revision, minutes):
    NoteRevision.objects.filter(pk=revision.pk).update(
        created_at=timezone.now() - timedelta(minutes=minutes)
    )


def test_snapshot_files_the_state_a_save_replaces_and_coalesces_bursts():
    p = ProjectFactory()
    n = Note.objects.create(project=p, title="Draft", body="one two three")
    first = snapshot(n)
    assert first is not None and first.words == 3 and first.body == "one two three"
    n.body = "one two three four"
    n.save()
    assert snapshot(n) is None  # inside the coalescing window: the burst is one edit
    _age(first, COALESCE_MINUTES + 1)
    second = snapshot(n)
    assert second is not None and second.words == 4
    _age(second, COALESCE_MINUTES + 1)
    assert snapshot(n) is None  # nothing changed since the last snapshot
    assert snapshot(n, force=True) is None  # even forced: a duplicate of the newest is pointless
    rows = revision_rows(n)
    assert [r["words"] for r in rows] == [4, 3] and rows[-1]["delta_words"] == 1
    assert rows[0]["delta_words"] == 0 and rows[0]["title_changed"] is False
    # the last KEEP are kept
    for i in range(KEEP + 5):
        r = NoteRevision.objects.create(note=n, title="Draft", body=f"v{i}", words=1)
        _age(r, 1000 - i)
    n.body = "final"
    n.save()
    snapshot(n, force=True)
    assert n.revisions.count() == KEEP


def test_diff_and_restore_refile_the_current_state_and_resync_links(
    client, settings, django_user_model
):
    p = ProjectFactory(slug="attention")
    other = Note.objects.create(project=p, title="Other", body="see [[Alpha]]")
    n = Note.objects.create(project=p, title="Alpha", body="line one\nline two")
    sync_note_links(other)
    old = snapshot(n, force=True)
    _age(old, COALESCE_MINUTES + 1)
    n.title = "Alpha renamed"
    n.body = "line one\nline two changed\nline three #tagged"
    n.save()
    d = revision_diff(n, old)
    assert d["added"] == 2 and d["removed"] == 1 and d["same"] is False
    assert "-line two" in d["diff"] and "+line two changed" in d["diff"] and "(then)" in d["diff"]
    out = restore(n, old)
    n.refresh_from_db()
    assert n.title == "Alpha" and n.body == "line one\nline two" and n.tags == []
    assert out["restored"] == old.pk and out["filed"] is not None
    filed = NoteRevision.objects.get(pk=out["filed"])
    assert filed.title == "Alpha renamed" and "line three" in filed.body  # undoable
    assert NoteLink.objects.filter(source=other, target=n).exists()  # the rename followed back

    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("atlas", "a@b.c", "atlas")
    hdr = {"HTTP_X_API_KEY": "k", "HTTP_HOST": "127.0.0.1"}
    url = f"/api/v1/notes/{n.id}/"
    r = client.get(url + "revisions/", **hdr)
    assert r.status_code == 200 and [x["id"] for x in r.json()["revisions"]][:1] == [filed.pk]
    r = client.get(url + f"revisions/{old.pk}/", **hdr)
    assert r.status_code == 200 and r.json()["same"] is True  # restored: identical now
    assert client.get(url + "revisions/999999/", **hdr).status_code == 404
    assert client.get(url + "revisions/", HTTP_HOST="127.0.0.1").status_code == 401
    # a PATCH that changes the body files the replaced state (past the window; the newest
    # revision must differ from the note, else there is nothing new to file)
    _age(old, COALESCE_MINUTES + 30)
    _age(filed, COALESCE_MINUTES + 1)
    before = n.revisions.count()
    r = client.patch(url, {"body": "edited over the API"}, content_type="application/json", **hdr)
    assert r.status_code == 200 and n.revisions.count() == before + 1
    assert n.revisions.first().body == "line one\nline two"
    r = client.patch(url, {"body": "edited over the API"}, content_type="application/json", **hdr)
    assert n.revisions.count() == before + 1  # unchanged body: nothing filed
    r = client.post(url + f"revisions/{filed.pk}/restore/", **hdr)
    assert (
        r.status_code == 200
        and r.json()["title"] == "Alpha renamed"
        and r.json()["restored"]["restored"] == filed.pk
    )
    tsx = Path("frontend/src/app/pages/Notes.tsx").read_text()
    for needle in (
        'data-testid="history-toggle"',
        'data-testid="revision-row"',
        'data-testid="revision-diff"',
        'data-testid="revision-restore"',
        "/revisions/",
    ):
        assert needle in tsx, needle
