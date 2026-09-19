"""#573 (backlog 370): the Access section lists the problems first. The owner's own logins
used to push the rows that matter out of `recent(12)` entirely."""

from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings

from core import access
from core.diagnostics import as_text
from core.models import AccessEvent

BASE = Path(settings.BASE_DIR)
KEY = "test-key"


@pytest.fixture
def owner(django_user_model, settings):
    settings.ATLAS_API_KEY = KEY
    return django_user_model.objects.create_superuser("owner", password="pw")


def _event(kind, days_ago=0, address="10.0.0.9"):
    from django.utils import timezone

    row = AccessEvent.objects.create(kind=kind, address=address, user_agent="probe/1", detail="x")
    if days_ago:
        AccessEvent.objects.filter(pk=row.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
    return row


@pytest.mark.django_db
def test_problems_are_windowed_capped_and_newest_first():
    for _ in range(15):
        _event(AccessEvent.Kind.LOGIN_OK)
    _event(AccessEvent.Kind.API_KEY_REJECTED, days_ago=8)  # out of the window
    old = _event(AccessEvent.Kind.LOGIN_FAILED, days_ago=2)
    new = _event(AccessEvent.Kind.LOGIN_LOCKED, days_ago=1)
    rows = access.problems()
    assert [r["id"] for r in rows] == [new.id, old.id]
    assert {r["kind"] for r in rows} == {"login_locked", "login_failed"}
    # the cap and the window together
    for _ in range(14):
        _event(AccessEvent.Kind.API_KEY_REJECTED)
    assert len(access.problems()) == 12
    assert len(access.problems(limit=3)) == 3
    assert len(access.problems(days=30, limit=50)) == 17  # the 8-day-old one comes back
    # the owner's logins never crowd them out; recent() keeps its old meaning
    assert all(r["kind"] != "login_ok" for r in access.problems())
    assert access.recent(3)[0]["kind"] == "api_key_rejected"


@pytest.mark.django_db
def test_recent_logins_are_logins_only():
    _event(AccessEvent.Kind.API_KEY_REJECTED)
    for _ in range(7):
        _event(AccessEvent.Kind.LOGIN_OK, address="127.0.0.1")
    rows = access.recent_logins()
    assert len(rows) == 5 and all(r["kind"] == "login_ok" for r in rows)


@pytest.mark.django_db
def test_the_report_carries_problems_logins_and_the_tail(client, owner):
    _event(AccessEvent.Kind.API_KEY_REJECTED, days_ago=1, address="203.0.113.5")
    for _ in range(13):
        _event(AccessEvent.Kind.LOGIN_OK, address="127.0.0.1")
    body = client.get("/api/v1/diagnostics/", HTTP_X_API_KEY=KEY).json()
    acc = body["access"]
    assert [r["kind"] for r in acc["problems"]] == ["api_key_rejected"]
    assert len(acc["logins"]) == 5 and all(r["kind"] == "login_ok" for r in acc["logins"])
    assert len(acc["events"]) == 12 and all(r["kind"] == "login_ok" for r in acc["events"])
    # the text names the problem row under the counts line
    text = body["text"]
    counts_line = next(line for line in text.splitlines() if line.startswith("access ("))
    after = text.split(counts_line, 1)[1].splitlines()[1]
    assert "API key rejected" in after and "203.0.113.5" in after and "probe/1" in after


@pytest.mark.django_db
def test_the_access_events_endpoint_can_list_problems_only(client, owner):
    _event(AccessEvent.Kind.LOGIN_FAILED)
    _event(AccessEvent.Kind.LOGIN_OK)
    everything = client.get("/api/v1/access-events/?limit=5", HTTP_X_API_KEY=KEY).json()
    assert [r["kind"] for r in everything["events"]] == ["login_ok", "login_failed"]
    only = client.get("/api/v1/access-events/?problems=1", HTTP_X_API_KEY=KEY).json()
    assert [r["kind"] for r in only["events"]] == ["login_failed"]


def test_the_text_names_what_the_cap_left_out():
    from core.diagnostics import hidden_problems

    counts = {"api_key_rejected": 12, "login_locked": 1, "login_failed": 5}
    shown = [
        {"kind": "api_key_rejected", "at": "2026-09-15T17:56:00", "label": "API key rejected"}
    ] * 12
    assert hidden_problems(counts, shown) == ["5 failed logins", "1 lockout"]
    assert hidden_problems({"api_key_rejected": 19}, shown) == ["7 rejected keys"]
    assert hidden_problems({"api_key_rejected": 12}, shown) == []
    report = {
        "version": "x",
        "desktop": False,
        "platform": "p",
        "frozen": False,
        "settings_module": "m",
        "data_dir": None,
        "database": "d",
        "engine": None,
        "latex": {"warm": False, "size_mb": 0, "dir": "", "state": "idle"},
        "jobs": "j",
        "api_key_configured": True,
        "update_feed": [],
        "last_failed_compile": None,
        "server_log": "",
        "client_errors": [],
        "access": {"summary": {"days": 7, "counts": counts}, "problems": shown},
    }
    assert "  … 5 failed logins · 1 lockout more in the window, not listed" in as_text(report)


def test_one_window_for_the_counts_and_the_list():
    import inspect

    assert access.WINDOW_DAYS == 7
    assert inspect.signature(access.problems).parameters["days"].default == access.WINDOW_DAYS
    assert inspect.signature(access.summary).parameters["days"].default == access.WINDOW_DAYS


def test_as_text_skips_a_malformed_problem_row():
    report = {
        "version": "x",
        "desktop": False,
        "platform": "p",
        "frozen": False,
        "settings_module": "m",
        "data_dir": None,
        "database": "d",
        "engine": None,
        "latex": {"warm": False, "size_mb": 0, "dir": "", "state": "idle"},
        "jobs": "j",
        "api_key_configured": True,
        "update_feed": [],
        "last_failed_compile": None,
        "server_log": "",
        "client_errors": [],
        "access": {
            "summary": {"days": 7, "counts": {}},
            "problems": [
                "junk",
                {
                    "at": "2026-09-15T17:56:00",
                    "label": "API key rejected",
                    "address": "",
                    "detail": "",
                    "user_agent": "",
                },
            ],
        },
    }
    text = as_text(report)
    assert "  2026-09-15 17:56 · API key rejected · ?" in text


def test_ui_wiring():
    page = (BASE / "frontend" / "src" / "app" / "pages" / "Diagnostics.tsx").read_text()
    for needle in (
        'data-testid="access-log"',
        'data-testid="access-problems"',
        'data-testid="access-problem" data-kind={e.kind}',
        'data-testid="access-more"',
        "{hiddenKinds(c, problems)} more in the window, not listed",
        'data-testid="access-quiet"',
        'data-testid="access-logins"',
        'data-testid="access-all-toggle"',
        'data-testid="access-events"',
        "None in the last {r.access!.summary!.days} days — no failed login, no lockout, no rejected key.",
        "The last one was on ${stamp(last.at).slice(0, 10)}",
    ):
        assert needle in page, needle
    # problems above logins above the raw tail; the toggle's state hook sits with the others
    assert (
        page.index('data-testid="access-problems"')
        < page.index('data-testid="access-logins"')
        < page.index('data-testid="access-events"')
    )
    assert page.index("const [allEvents, setAllEvents]") < page.index("{q.isLoading &&")
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "access-problems" in chunks and "access-all-toggle" in chunks
