"""Writing v2 slice 2 — reviewer-response tracker."""

import datetime

import pytest

from projects.tests.factories import ProjectFactory
from writing import reviews
from writing.models import Manuscript, SubmissionEvent

pytestmark = pytest.mark.django_db

REVIEWS = """Reviewer 1
1. The sample is small (n=12); please justify.
2) The load manipulation conflates perceptual and cognitive load.

Reviewer #2
- Figure 2 is unreadable.
- Cite the 2019 replication.
Some closing remark that is not a point marker
but continues the previous one.
"""


def test_parse_review_points():
    pts = reviews.parse_review_points(REVIEWS)
    assert [(p["reviewer"], p["n"]) for p in pts] == [("1", 1), ("1", 2), ("2", 1), ("2", 2)]
    assert pts[0]["text"].startswith("The sample is small")
    assert (
        pts[3]["text"]
        == "Cite the 2019 replication. Some closing remark that is not a point marker but continues the previous one."
    )
    assert reviews.parse_review_points("") == []
    solo = reviews.parse_review_points("Just one paragraph of feedback.")
    assert solo == [{"reviewer": "1", "n": 1, "text": "Just one paragraph of feedback."}]


def test_log_reviews_creates_event_and_note_and_progress():
    project = ProjectFactory(slug="deep")
    m = Manuscript.objects.create(project=project, title="Load paper", status="under_review")
    event, note, points = reviews.log_reviews(m, REVIEWS, received=datetime.date(2026, 9, 6))
    assert event.kind == "reviews_received" and event.date == datetime.date(2026, 9, 6)
    assert "4 point(s) from 2 reviewer(s)" in event.notes and f"[[{note.title}]]" in event.notes
    assert note.title == "Response to reviewers — Load paper (2026-09-06)"
    assert "## Reviewer 1" in note.body and "- [ ] **R2.2** Cite the 2019" in note.body
    assert note.body.count("> Response:") == 4
    progress = reviews.response_progress(m)
    assert progress["total"] == 4 and progress["done"] == 0 and progress["note_id"] == note.pk
    note.body = note.body.replace("- [ ] **R1.1**", "- [x] **R1.1**").replace(
        "- [ ] **R2.1**", "- [X] **R2.1**"
    )
    note.save()
    progress = reviews.response_progress(m)
    assert (progress["done"], progress["percent"]) == (2, 50)
    # a second round gets a distinct title
    _, note2, _ = reviews.log_reviews(
        m, "Reviewer 1\n1. Still small.", received=datetime.date(2026, 9, 6)
    )
    assert note2.title.endswith("(2)") and reviews.response_progress(m)["note_id"] == note2.pk
    assert SubmissionEvent.objects.count() == 2


def test_log_reviews_with_no_points_still_scaffolds():
    project = ProjectFactory()
    m = Manuscript.objects.create(project=project, title="Empty")
    _, note, points = reviews.log_reviews(m, "   ")
    assert points == [] and "- [ ] **R1.1**" in note.body
    assert (
        reviews.response_progress(Manuscript.objects.create(project=project, title="Other")) is None
    )


def test_reviews_api(client, settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    m = Manuscript.objects.create(project=ProjectFactory(slug="deep"), title="Load paper")
    out = client.post(
        f"/api/v1/manuscripts/{m.pk}/reviews/",
        {"text": REVIEWS, "date": "2026-09-06"},
        content_type="application/json",
        HTTP_X_API_KEY="k",
    )
    assert out.status_code == 201, out.content
    body = out.json()
    assert (
        body["points"] == 4
        and body["event"]["kind"] == "reviews_received"
        and body["note"]["title"].startswith("Response to reviewers")
    )
    progress = client.get(
        f"/api/v1/manuscripts/{m.pk}/response-progress/", HTTP_X_API_KEY="k"
    ).json()["progress"]
    assert progress["total"] == 4 and progress["app_url"].endswith(f"/notes/{body['note']['id']}")
    none = client.get(
        f"/api/v1/manuscripts/{Manuscript.objects.create(project=m.project, title='x').pk}/response-progress/",
        HTTP_X_API_KEY="k",
    )
    assert none.status_code == 200 and none.json() == {"progress": None}
