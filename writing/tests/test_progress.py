"""#413 — writing progress: daily word samples, deltas, streak, API and UI wiring."""

import datetime as dt

import pytest
from django.utils import timezone

from projects.tests.factories import ProjectFactory
from writing.models import Manuscript, ManuscriptFile, WordCountSample
from writing.progress import progress, record_words

KEY = "k"
HEADERS = {"HTTP_X_API_KEY": KEY}
pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings, django_user_model):
    settings.ATLAS_API_KEY = KEY
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory(slug="deep")
    ms = Manuscript.objects.create(project=project, title="Paper")
    return project, ms


def test_tex_save_records_today_and_last_save_wins(world):
    _, ms = world
    f = ManuscriptFile.objects.create(
        manuscript=ms, path="main.tex", is_main=True, content="one two three"
    )
    today = timezone.localdate()
    assert WordCountSample.objects.get(manuscript=ms, date=today).words == 3
    f.content = "one two three four five"
    f.save()
    assert WordCountSample.objects.get(manuscript=ms, date=today).words == 5
    assert WordCountSample.objects.filter(manuscript=ms).count() == 1
    ManuscriptFile.objects.create(manuscript=ms, path="refs.bib", content="@article{x, title={y}}")
    assert WordCountSample.objects.get(manuscript=ms, date=today).words == 5  # bib: no sample


def test_progress_deltas_streak_and_best_day(world):
    _, ms = world
    today = timezone.localdate()
    for days_ago, words in ((5, 100), (4, 100), (3, 250), (2, 300), (1, 300)):
        record_words(ms, words, today - dt.timedelta(days=days_ago))
    record_words(ms, 420, today)
    out = progress(ms, days=7)
    assert out["words"] == 420 and out["today_delta"] == 120
    assert out["streak"] == 1  # yesterday added nothing, so the streak is today alone
    assert out["best_day"]["delta"] == 150 and out["days_with_writing"] == 3
    assert out["week_delta"] == 150 + 50 + 120
    by_date = {s["date"]: s for s in out["samples"]}
    assert by_date[(today - dt.timedelta(days=6)).isoformat()]["words"] is None  # before data
    assert by_date[(today - dt.timedelta(days=4)).isoformat()]["delta"] == 0
    # a day with no sample carries the previous count forward with a zero delta
    record_words(ms, 500, today + dt.timedelta(days=0))
    assert progress(ms, days=7)["today_delta"] == 200


def test_progress_api_and_card_field(client, world):
    _, ms = world
    today = timezone.localdate()
    record_words(ms, 900, today - dt.timedelta(days=1))
    ManuscriptFile.objects.create(
        manuscript=ms, path="main.tex", is_main=True, content=" ".join(["w"] * 1000)
    )
    r = client.get(f"/api/v1/manuscripts/{ms.pk}/progress/?days=7", **HEADERS)
    assert r.status_code == 200
    assert r.json()["today_delta"] == 100 and len(r.json()["samples"]) == 7
    wc = client.get(f"/api/v1/manuscripts/{ms.pk}/word-count/", **HEADERS).json()
    assert wc["words"] == 1000 and wc["today_delta"] == 100 and wc["streak"] == 1
    card = client.get(f"/api/v1/manuscripts/{ms.pk}/", **HEADERS).json()["progress"]
    assert card["today_delta"] == 100 and len(card["samples"]) == 14 and card["samples"][-1] == 100
    studio = open("frontend/src/app/pages/Studio.tsx").read()
    assert 'data-testid="words-today"' in studio
    writing = open("frontend/src/app/pages/Writing.tsx").read()
    assert 'data-testid="progress-spark"' in writing and "progress.today_delta" in writing
    assert "def get_writing_progress(" in open("mcp_server/server.py").read()


def test_dashboard_words_written_this_month(world):
    """#418: the dashboard stat sums positive daily deltas across manuscripts this month."""
    from core.dashboard import monthly_stats, words_written_since

    project, ms = world
    today = timezone.localdate()
    start = today.replace(day=1)
    record_words(ms, 1000, start - dt.timedelta(days=1))  # last month's baseline
    record_words(ms, 1300, start)  # +300 on the 1st
    if today > start:
        record_words(ms, 1200, today)  # a cut is not negative writing
    other = Manuscript.objects.create(project=project, title="Second")
    record_words(other, 50, today)  # first sample ever: no delta to count
    assert words_written_since(start) == 300
    assert monthly_stats()["words_written"] == 300
