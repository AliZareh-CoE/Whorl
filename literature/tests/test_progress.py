"""#523 — reading progress: the reader's remembered page, started / finished stamps."""

from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

from literature import progress
from literature.reading import add_highlight
from literature.tests.factories import ProjectReferenceFactory, ReferenceFactory
from projects.tests.factories import ProjectFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY, "HTTP_HOST": "127.0.0.1"}
BASE = Path(settings.BASE_DIR)


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def paper(db, django_user_model):
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    ref = ReferenceFactory(title="Attention is all you need", bibtex_key="vaswani2017attention")
    link = ProjectReferenceFactory(project=project, reference=ref)
    return project, ref, link


# --- percent and positions --------------------------------------------------------------------


def test_percent_is_half_up_and_none_without_pages():
    assert progress.percent_of(5, 12) == 42  # 41.67
    assert progress.percent_of(1, 8) == 13  # 12.5 rounds up, not to even
    assert progress.percent_of(12, 12) == 100
    assert progress.percent_of(3, None) is None
    assert progress.percent_of(None, 10) is None


def test_record_position_sets_fields_and_bumps_updated_at(paper):
    project, ref, link = paper
    before = ref.updated_at
    out = progress.record_position(ref, 5, page_count=12)
    ref.refresh_from_db()
    assert (ref.last_page, ref.page_count) == (5, 12)
    assert ref.last_read_at is not None and ref.updated_at > before
    assert out["percent"] == 42 and out["page"] == 5
    # without a page count the count stays; with one it is authoritative
    progress.record_position(ref, 7)
    ref.refresh_from_db()
    assert (ref.last_page, ref.page_count) == (7, 12)


def test_record_position_refuses_bad_pages(paper):
    _, ref, _ = paper
    with pytest.raises(progress.ProgressError):
        progress.record_position(ref, 0)
    with pytest.raises(progress.ProgressError):
        progress.record_position(ref, "x")
    progress.record_position(ref, 3, page_count=10)
    with pytest.raises(progress.ProgressError):
        progress.record_position(ref, 11)
    with pytest.raises(progress.ProgressError):
        progress.record_position(ref, 2, page_count=0)


def test_record_position_with_project_stamps_started_once(paper):
    project, ref, link = paper
    assert link.started_at is None
    progress.record_position(ref, 2, page_count=9, project=project)
    link.refresh_from_db()
    first = link.started_at
    assert first is not None and link.reading_status == "to_read"  # never a status change
    progress.record_position(ref, 4, project=project)
    link.refresh_from_db()
    assert link.started_at == first
    other = ProjectFactory(slug="other")
    with pytest.raises(progress.ProgressError):
        progress.record_position(ref, 4, project=other)


# --- the stamps -----------------------------------------------------------------------------


def test_status_transitions_stamp_started_and_finished(paper):
    project, ref, link = paper
    link.reading_status = "skimmed"
    link.save(update_fields=["reading_status", "updated_at"])  # the bulk / classic path
    link.refresh_from_db()
    assert link.started_at is not None and link.finished_at is None
    started = link.started_at
    link.reading_status = "read"
    link.save()
    link.refresh_from_db()
    assert link.started_at == started and link.finished_at is not None
    # "I overstated that": read → skimmed withdraws the finish, the start is history
    link.reading_status = "skimmed"
    link.save(update_fields=["reading_status", "updated_at"])
    link.refresh_from_db()
    assert link.finished_at is None and link.started_at == started
    link.reading_status = "annotated"
    link.save()
    link.refresh_from_db()
    assert link.finished_at is not None
    # back to the queue: the same
    link.reading_status = "to_read"
    link.save(update_fields=["reading_status", "updated_at"])
    link.refresh_from_db()
    assert link.finished_at is None and link.started_at == started
    # an unrelated save changes nothing
    link.notes = "hi"
    link.save(update_fields=["notes", "updated_at"])
    link.refresh_from_db()
    assert link.finished_at is None


def test_created_as_read_is_finished_on_arrival(db):
    link = ProjectReferenceFactory(reading_status="annotated")
    assert link.started_at is not None and link.finished_at is not None
    plain = ProjectReferenceFactory()
    assert plain.started_at is None and plain.finished_at is None


def test_highlight_auto_skim_stamps_started(paper):
    project, ref, link = paper
    add_highlight(ref, "a passage worth keeping", page=2, project=project, mirror_to_note=False)
    link.refresh_from_db()
    assert link.reading_status == "skimmed" and link.started_at is not None


# --- continue reading -----------------------------------------------------------------------


def test_reading_now_orders_and_excludes(db):
    now = timezone.now()
    a = ReferenceFactory(title="A")
    b = ReferenceFactory(title="B")
    c = ReferenceFactory(title="C")
    d = ReferenceFactory(title="D")
    e = ReferenceFactory(title="E")
    progress.record_position(a, 5, page_count=12, now=now - timedelta(days=1))
    progress.record_position(b, 3, page_count=12, now=now)
    progress.record_position(c, 12, page_count=12, now=now)  # at the end
    progress.record_position(d, 1, page_count=12, now=now)  # never past the first page
    progress.record_position(e, 6, page_count=12, now=now - timedelta(days=45))  # stale
    finished = ReferenceFactory(title="F")
    progress.record_position(finished, 4, page_count=10, now=now)
    ProjectReferenceFactory(reference=finished, reading_status="read")
    rows = progress.reading_now(now=now)
    assert [r["title"] for r in rows] == ["B", "A"]
    assert rows[0]["percent"] == 25 and rows[1]["page"] == 5
    assert [r["title"] for r in progress.reading_now(limit=1, now=now)] == ["B"]


# --- API --------------------------------------------------------------------------------------


def test_progress_api_roundtrip(client, paper):
    project, ref, link = paper
    r = client.get(f"/api/v1/references/{ref.pk}/progress/", **HEADERS)
    assert r.status_code == 200 and r.json()["page"] is None
    r = client.post(
        f"/api/v1/references/{ref.pk}/progress/",
        {"page": 5, "page_count": 12, "project": "deep"},
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 200, r.content
    body = r.json()
    assert (body["page"], body["pages"], body["percent"]) == (5, 12, 42)
    assert body["links"][0]["project"] == "deep" and body["links"][0]["started_at"]
    # past the end, page 0, unknown project → 400 with the reason
    r = client.post(
        f"/api/v1/references/{ref.pk}/progress/",
        {"page": 40},
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 400 and "past the end" in r.json()["page"][0]
    r = client.post(
        f"/api/v1/references/{ref.pk}/progress/",
        {"page": 0},
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 400
    r = client.post(
        f"/api/v1/references/{ref.pk}/progress/",
        {"page": 2, "project": "nope"},
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 400 and "project" in r.json()
    # the list row and the queue row carry it; the link serializer carries the stamps
    row = next(
        x
        for x in client.get("/api/v1/references/", **HEADERS).json()["results"]
        if x["id"] == ref.pk
    )
    assert row["progress"]["page"] == 5 and row["projects"][0]["started_at"]
    queue = client.get("/api/v1/projects/deep/reading-queue/", **HEADERS).json()
    assert queue[0]["progress"]["percent"] == 42 and queue[0]["started_at"]
    link_row = client.get(f"/api/v1/project-references/{link.pk}/", **HEADERS).json()
    assert "started_at" in link_row and "finished_at" in link_row
    # the position cannot be written through the reference PATCH
    r = client.patch(
        f"/api/v1/references/{ref.pk}/",
        {"last_page": 1},
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 200
    ref.refresh_from_db()
    assert ref.last_page == 5


def test_reading_now_api_and_auth(client, paper):
    project, ref, link = paper
    progress.record_position(ref, 4, page_count=8)
    r = client.get("/api/v1/references/reading-now/?limit=zzz", **HEADERS)
    assert r.status_code == 200 and r.json()[0]["id"] == ref.pk and r.json()[0]["pdf"] is None
    assert client.get("/api/v1/references/reading-now/", HTTP_HOST="127.0.0.1").status_code == 401
    assert (
        client.get(f"/api/v1/references/{ref.pk}/progress/", HTTP_HOST="127.0.0.1").status_code
        == 401
    )
    assert client.get("/api/v1/references/999999/progress/", **HEADERS).status_code == 404


# --- the UI is wired ------------------------------------------------------------------------


def test_reader_and_library_are_wired():
    reader = (BASE / "frontend/src/app/pages/library/PdfReader.tsx").read_text()
    assert 'queryKey: ["progress", refId]' in reader and "/progress/" in reader
    assert "restored.current = true" in reader and "report(current, numPages)" in reader
    lib = (BASE / "frontend/src/app/pages/Library.tsx").read_text()
    for needle in (
        'data-testid="continue-reading"',
        'data-testid="row-progress"',
        'data-testid="card-progress"',
        '"resume-read"',
        "/references/reading-now/?limit=3",
        "finished ${dayLabel(p.finished_at)}",
    ):
        assert needle in lib, needle
