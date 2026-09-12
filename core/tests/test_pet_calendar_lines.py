"""#56 — the pet has a line for the weekday and one for the season, alongside the data lines."""

import datetime

import pytest
from django.utils import timezone

from core.pet import REACTION_LINES, SEASON_LINES, WEEKDAY_LINES, _speech_candidates, calendar_lines

pytestmark = pytest.mark.django_db


def test_every_weekday_and_month_has_a_line():
    assert sorted(WEEKDAY_LINES) == list(range(7)) and sorted(SEASON_LINES) == list(range(1, 13))
    assert all(line.strip() for line in [*WEEKDAY_LINES.values(), *SEASON_LINES.values()])


def test_calendar_lines_follow_the_date():
    friday = timezone.make_aware(datetime.datetime(2026, 10, 2, 10, 0))
    assert calendar_lines(friday) == [WEEKDAY_LINES[4], SEASON_LINES[10]]
    assert "Friday" in calendar_lines(friday)[0] and "October" in calendar_lines(friday)[1]


def test_candidates_include_the_calendar_lines_and_stay_calm():
    now = timezone.localtime()
    lines = _speech_candidates(now)
    assert WEEKDAY_LINES[now.weekday()] in lines and SEASON_LINES[now.month] in lines
    banned = ("hurry", "you must", "you should", "don't forget", "!!")
    assert not any(b in line.lower() for line in lines for b in banned)


def test_milestone_reactions_have_variety():
    assert len(REACTION_LINES["milestone"]) >= 6
    assert len(set(REACTION_LINES["milestone"])) == len(REACTION_LINES["milestone"])
