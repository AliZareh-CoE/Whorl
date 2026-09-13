"""#474 — the status clock and the venue turnaround."""

import datetime
from pathlib import Path

import pytest

from projects.tests.factories import ProjectFactory
from writing import clock as C
from writing.models import Manuscript, SubmissionEvent

pytestmark = pytest.mark.django_db

D = datetime.date


def _paper(status, venue="JEP:G", events=()):
    m = Manuscript.objects.create(
        project=ProjectFactory(), title=f"P-{status}", status=status, target_venue=venue
    )
    for kind, when in events:
        SubmissionEvent.objects.create(manuscript=m, kind=kind, date=when)
    return Manuscript.objects.get(pk=m.pk)


def test_status_clock_reads_the_timeline_per_status():
    today = D(2026, 9, 13)
    ev = [
        ("submitted", D(2026, 3, 1)),
        ("reviews_received", D(2026, 5, 1)),
        ("revision_submitted", D(2026, 6, 1)),
    ]
    under = C.status_clock(_paper("under_review", events=ev), today)
    assert under == {
        "status": "under_review",
        "since": "2026-06-01",
        "days": 104,
        "source": "revision_submitted",
        "label": "104 d under review",
    }
    revising = C.status_clock(_paper("revision", events=ev), today)
    assert revising["since"] == "2026-05-01" and revising["label"] == "135 d revising"
    first = C.status_clock(_paper("submitted", events=ev[:1]), today)
    assert first["days"] == 196 and first["label"] == "196 d since submission"
    acc = C.status_clock(_paper("accepted", events=ev + [("accepted", D(2026, 9, 10))]), today)
    assert acc["label"] == "3 d since acceptance" and acc["source"] == "accepted"
    # no matching event, or a drafting status: the clock starts at the last change
    draft = C.status_clock(_paper("drafting"), today)
    assert (
        draft["source"] == "updated"
        and draft["days"] == 0
        and draft["label"].endswith("d drafting")
    )
    lost = C.status_clock(_paper("under_review"), today)
    assert lost["source"] == "updated"


def test_venue_turnaround_pairs_submissions_with_the_next_decision():
    _paper(
        "revision",
        events=[
            ("submitted", D(2026, 1, 1)),
            ("reviews_received", D(2026, 3, 2)),  # 60 d first decision
            ("revision_submitted", D(2026, 4, 1)),
            ("accepted", D(2026, 4, 21)),  # 20 d
        ],
    )
    _paper(
        "rejected" if False else "shelved",
        venue="jep:g",  # case-insensitive
        events=[("submitted", D(2025, 6, 1)), ("desk_reject", D(2025, 6, 11))],  # 10 d
    )
    mine = _paper("under_review", events=[("submitted", D(2026, 9, 1))])  # open, no decision
    _paper(
        "under_review",
        venue="Other",
        events=[("submitted", D(2026, 1, 1)), ("accepted", D(2026, 1, 3))],
    )
    out = C.venue_turnaround("JEP:G", exclude_id=mine.id)
    assert out == {
        "venue": "JEP:G",
        "manuscripts": 2,
        "rounds": 3,
        "median_days": 20,
        "first_decision_median_days": 35,
        "fastest_days": 10,
        "slowest_days": 60,
    }
    assert C.venue_turnaround("Nowhere")["rounds"] == 0
    assert C.venue_turnaround("")["manuscripts"] == 0


def test_clock_in_the_api_and_the_turnaround_endpoint(client_logged_in):
    m = _paper(
        "under_review", events=[("submitted", D(2026, 1, 1)), ("reviews_received", D(2026, 2, 1))]
    )
    m2 = _paper("under_review", events=[("submitted", D(2026, 8, 1))])
    body = client_logged_in.get(f"/api/v1/manuscripts/{m2.id}/").json()
    assert body["clock"]["source"] == "submitted" and body["clock"]["label"].endswith(
        "d under review"
    )
    rows = client_logged_in.get("/api/v1/manuscripts/").json()["results"]
    assert all("clock" in r for r in rows)
    r = client_logged_in.get(f"/api/v1/manuscripts/venue-turnaround/?venue=jep%3Ag&exclude={m2.id}")
    assert r.status_code == 200 and r.json()["rounds"] == 1 and r.json()["median_days"] == 31
    assert client_logged_in.get("/api/v1/manuscripts/venue-turnaround/").status_code == 400
    assert (
        client_logged_in.get("/api/v1/manuscripts/venue-turnaround/?venue=x&exclude=no").status_code
        == 400
    )
    assert m.id  # the excluded paper's own round is what the endpoint counted


def test_writing_pages_show_the_clock():
    tsx = Path("frontend/src/app/pages/Writing.tsx").read_text()
    for needle in (
        'data-testid="card-clock"',
        'data-testid="status-clock"',
        'data-testid="venue-turnaround"',
        "/manuscripts/venue-turnaround/",
    ):
        assert needle in tsx, needle


# --- #475: the nudge -------------------------------------------------------------------


def test_nudge_thresholds_and_the_logged_nudge_resets_the_count():
    today = D(2026, 9, 13)
    # history at the venue: one 40-day round → threshold max(60, 60) = 60
    _paper("accepted", events=[("submitted", D(2026, 1, 1)), ("accepted", D(2026, 2, 10))])
    m = _paper("under_review", events=[("submitted", D(2026, 6, 1))])  # waited 104
    n = C.nudge(m, C.status_clock(m, today), today)
    assert n["due"] and n["after_days"] == 60 and n["waited"] == 104 and n["last"] is None
    assert "1.5× your median of 40 d" in n["basis"]
    # a logged nudge restarts the count from its date
    SubmissionEvent.objects.create(
        manuscript=m, kind="note", date=D(2026, 9, 1), notes="Nudged the editor"
    )
    m = Manuscript.objects.get(pk=m.pk)
    n = C.nudge(m, C.status_clock(m, today), today)
    assert not n["due"] and n["waited"] == 12 and n["last"] == "2026-09-01"
    # no history → 90 days; a paper not waiting → never
    fresh = _paper("submitted", venue="Elsewhere", events=[("submitted", D(2026, 5, 1))])
    n = C.nudge(fresh, C.status_clock(fresh, today), today)
    assert n["due"] and n["after_days"] == 90 and n["basis"].startswith("no history")
    rev = _paper("revision", events=[("reviews_received", D(2026, 1, 1))])
    assert C.nudge(rev, C.status_clock(rev, today), today)["due"] is False


def test_waiting_manuscripts_feeds_the_dashboard(client_logged_in):
    today = D(2026, 9, 13)
    due = _paper("under_review", venue="Slow", events=[("submitted", D(2026, 1, 1))])
    _paper("under_review", venue="Slow", events=[("submitted", D(2026, 9, 1))])  # 12 d: fine
    rows = C.waiting_manuscripts(today)
    assert [r["id"] for r in rows] == [due.id] and rows[0]["after_days"] == 90
    body = client_logged_in.get("/api/v1/dashboard/").json()
    titles = [w["title"] for w in body["attention"]["waiting"]]
    assert due.title in titles
    detail = client_logged_in.get(f"/api/v1/manuscripts/{due.id}/").json()
    assert detail["clock"]["nudge"]["due"] is True


def test_nudge_surfaces_in_the_ui():
    writing = Path("frontend/src/app/pages/Writing.tsx").read_text()
    for needle in ('data-testid="nudge-hint"', 'data-testid="log-nudge"', "Nudged the editor"):
        assert needle in writing, needle
    dash = Path("frontend/src/app/pages/Dashboard.tsx").read_text()
    assert 'data-testid="attention-waiting"' in dash and "waiting.length" in dash
