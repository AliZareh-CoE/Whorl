"""#460 (backlog #129): compiles per day, from the revision snapshots."""

import datetime as dt

import pytest
from django.utils import timezone

from writing.models import ManuscriptFile, ManuscriptRevision, snapshot_manuscript
from writing.progress import compile_rhythm, compiles_since, progress
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db


def _ms():
    m = ManuscriptFactory()
    ManuscriptFile.objects.create(
        manuscript=m, path="main.tex", content="x", kind="tex", is_main=True
    )
    return m


def test_rhythm_counts_per_day_and_windows():
    m = _ms()
    for _ in range(3):
        snapshot_manuscript(m)
    old = snapshot_manuscript(m, label="old")
    ManuscriptRevision.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - dt.timedelta(days=20)
    )
    yesterday = snapshot_manuscript(m)
    ManuscriptRevision.objects.filter(pk=yesterday.pk).update(
        created_at=timezone.now() - dt.timedelta(days=1)
    )
    r = compile_rhythm(m)
    assert len(r["per_day"]) == 14 and r["today"] == 3 and r["week"] == 4 and r["total"] == 4
    assert r["per_day"][-1]["compiles"] == 3 and r["per_day"][-2]["compiles"] == 1
    assert compiles_since(timezone.localdate() - dt.timedelta(days=6)) == 4
    assert progress(m)["compiles"]["week"] == 4


def test_empty_manuscript_has_a_flat_rhythm():
    m = _ms()
    r = compile_rhythm(m, days=7)
    assert r == {
        "per_day": [{"date": d["date"], "compiles": 0} for d in r["per_day"]],
        "today": 0,
        "week": 0,
        "total": 0,
    }
    assert len(r["per_day"]) == 7
