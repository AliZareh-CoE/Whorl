"""Mochi v2 (Owner report 2026-09-06): streak, achievements, rename via the API."""

import datetime

import pytest
from django.core.cache import cache

from core import pet as pet_mod
from core.models import Pet

pytestmark = pytest.mark.django_db


def test_streak_counts_consecutive_days_ending_today_or_yesterday():
    today = datetime.date(2026, 9, 6)
    d = datetime.timedelta
    assert pet_mod.streak_days({today, today - d(1), today - d(2)}, today) == 3
    assert pet_mod.streak_days({today - d(1), today - d(2)}, today) == 2  # morning visit
    assert pet_mod.streak_days({today - d(2), today - d(3)}, today) == 0
    assert pet_mod.streak_days(set(), today) == 0


def test_state_has_achievements_legend_and_streak(client_logged_in):
    cache.delete("atlas-pet-state")
    data = client_logged_in.get("/api/v1/pet/").json()
    assert {a["key"] for a in data["achievements"]} >= {"first_light", "sage", "week_long"}
    assert all("unlocked" in a and a["description"] for a in data["achievements"])
    assert data["points_legend"][0] == {"action": "milestone completed", "points": 3}
    assert [s["name"] for s in data["stages"]] == ["egg", "hatchling", "scholar", "sage"]
    assert data["streak_days"] >= 0 and data["stage_floor"] == 0


def test_rename_via_api(client_logged_in):
    cache.delete("atlas-pet-state")
    response = client_logged_in.post(
        "/api/v1/pet/", {"name": "Nocturne"}, content_type="application/json"
    )
    assert response.status_code == 200 and response.json()["name"] == "Nocturne"
    assert Pet.objects.get(pk=1).name == "Nocturne"
    assert (
        client_logged_in.post(
            "/api/v1/pet/", {"name": "  "}, content_type="application/json"
        ).status_code
        == 400
    )
    assert client_logged_in.get("/api/v1/pet/").json()["name"] == "Nocturne"
