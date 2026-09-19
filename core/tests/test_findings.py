"""#572: the Diagnostics verdict — `findings(report)` turns the collected facts into "what is
wrong and what to do", the page leads with it, the pasted text leads with it, Claude gets it."""

from pathlib import Path

import pytest
from django.conf import settings

from core.diagnostics import LOW_DISK_BYTES, NO_DISK_BYTES, as_text, findings, verdict

BASE = Path(settings.BASE_DIR)


def _healthy(**over) -> dict:
    report = {
        "version": "0.1.0",
        "desktop": False,
        "platform": "x",
        "frozen": False,
        "settings_module": "m",
        "data_dir": None,
        "database": "sqlite · x",
        "engine": "/bin/tectonic",
        "latex": {"state": "ok", "log": "", "warm": True, "dir": "/c", "size_mb": 40, "seconds": 3},
        "jobs": "worker (huey)",
        "api_key_configured": True,
        "frame_ancestors": [],
        "update_feed": [],
        "update_verdict": {"state": "unchecked", "text": "not checked"},
        "last_failed_compile": None,
        "server_log": "",
        "client_errors": [],
        "access": {"summary": None, "events": []},
        "backups": {"last": None, "stale": False, "has_data": False, "stale_after_days": 7},
        "snapshots": None,
        "backup_destination": None,
        "disk": {"path": "/", "free_bytes": 50 << 30, "total_bytes": 100 << 30},
        "media_writable": True,
    }
    report.update(over)
    return report


def _ids(report):
    return [f["id"] for f in findings(report)]


def test_a_healthy_report_has_no_findings_and_a_green_verdict():
    rows = findings(_healthy())
    assert rows == []
    assert verdict(rows) == {"state": "ok", "text": "Nothing wrong that Atlas can see."}


def test_every_optional_section_may_be_missing():
    report = _healthy()
    for key in (
        "latex",
        "backups",
        "snapshots",
        "backup_destination",
        "access",
        "disk",
        "client_errors",
        "update_verdict",
    ):
        report.pop(key)
    # a missing latex section reads as cold, the only finding
    assert _ids(report) == ["latex_cold"]


@pytest.mark.parametrize(
    "over, ident, level",
    [
        ({"engine": None}, "engine", "fail"),
        (
            {"latex": {"state": "failed", "log": "x\nno network", "warm": False}},
            "latex_failed",
            "fail",
        ),
        ({"latex": {"state": "idle", "log": "", "warm": False}}, "latex_cold", "warn"),
        ({"api_key_configured": False}, "api_key", "fail"),
        ({"media_writable": False}, "media", "fail"),
        (
            {"disk": {"path": "/", "free_bytes": NO_DISK_BYTES - 1, "total_bytes": 1}},
            "disk",
            "fail",
        ),
        (
            {"disk": {"path": "/", "free_bytes": LOW_DISK_BYTES - 1, "total_bytes": 1}},
            "disk",
            "warn",
        ),
        (
            {"snapshots": {"scheduler": True, "last_error": {"at": "t", "detail": "disk"}}},
            "snapshot_error",
            "fail",
        ),
        (
            {"desktop": True, "snapshots": {"scheduler": False, "last_error": None}},
            "snapshot_scheduler",
            "warn",
        ),
        (
            {
                "backup_destination": {
                    "enabled": True,
                    "reachable": True,
                    "in_sync": True,
                    "last_error": {"at": "t", "detail": "x"},
                }
            },
            "destination_error",
            "fail",
        ),
        (
            {"backup_destination": {"enabled": True, "reachable": False, "dir": "/mnt/x"}},
            "destination_unreachable",
            "fail",
        ),
        (
            {
                "backup_destination": {
                    "enabled": True,
                    "reachable": True,
                    "in_sync": False,
                    "dir": "/mnt/x",
                }
            },
            "destination_behind",
            "warn",
        ),
        (
            {"backups": {"last": {"days_ago": 12}, "stale": True, "has_data": True}},
            "backup_stale",
            "warn",
        ),
        ({"backups": {"last": None, "stale": True, "has_data": True}}, "backup_stale", "warn"),
        (
            {"last_failed_compile": {"manuscript": 4, "title": "T", "log": "!", "at": "t"}},
            "compile_failed",
            "warn",
        ),
        (
            {
                "client_errors": [
                    {"at": "t", "where": "/today", "url": "u", "version": "", "errors": ["x"]}
                ]
            },
            "client_errors",
            "warn",
        ),
        (
            {
                "access": {
                    "summary": {
                        "days": 7,
                        "counts": {"api_key_rejected": 3},
                        "last_problem": {
                            "at": "2026-09-15T17:56:00",
                            "address": "10.0.0.9",
                            "kind": "api_key_rejected",
                        },
                    },
                    "events": [],
                }
            },
            "access_rejected",
            "warn",
        ),
        (
            {
                "access": {
                    "summary": {
                        "days": 7,
                        "counts": {"login_failed": 2, "login_locked": 1},
                        "last_problem": None,
                    },
                    "events": [],
                }
            },
            "access_logins",
            "warn",
        ),
        (
            {"update_verdict": {"state": "wrong_key", "text": "signed with another key"}},
            "update",
            "warn",
        ),
        ({"update_verdict": {"state": "offline", "text": "no network"}}, "update_offline", "warn"),
        ({"server_log": "x\nTraceback (most recent call last):\n  boom"}, "server_log", "warn"),
    ],
)
def test_each_rule(over, ident, level):
    rows = findings(_healthy(**over))
    assert [r["id"] for r in rows] == [ident], rows
    row = rows[0]
    assert row["level"] == level
    assert row["title"] and row["detail"] and row["fix"]


def test_quiet_states_do_not_fire():
    # a running warm-up is not "cold"; an unprobed or fine updater is not a finding; a backup
    # that is not stale, a destination that is off, a healthy desktop scheduler
    from datetime import timedelta

    from django.utils import timezone

    report = _healthy(
        last_failed_compile={
            "manuscript": 1,
            "title": "Old",
            "log": "!",
            "at": timezone.now() - timedelta(days=30),
        },
        latex={"state": "running", "log": "", "warm": False},
        update_verdict={"state": "current", "text": "up to date"},
        backups={"last": {"days_ago": 1}, "stale": False, "has_data": True},
        backup_destination={"enabled": False, "reachable": False},
        desktop=True,
        snapshots={"scheduler": True, "last_error": None},
        access={
            "summary": {
                "days": 7,
                "counts": {"login_ok": 40, "login_failed": 2},
                "last_problem": None,
            },
            "events": [],
        },
    )
    assert _ids(report) == []  # …two mistyped passwords, a compile that failed a month ago


def test_a_compile_failure_counts_while_it_is_recent():
    from django.utils import timezone

    for at in (timezone.now(), timezone.now().isoformat(), None, "junk"):
        row = {"manuscript": 1, "title": "T", "log": "!", "at": at}
        assert _ids(_healthy(last_failed_compile=row)) == ["compile_failed"], at


def test_three_failed_logins_count():
    summary = {"days": 7, "counts": {"login_failed": 3}, "last_problem": None}
    assert _ids(_healthy(access={"summary": summary, "events": []})) == ["access_logins"]


@pytest.mark.django_db
def test_a_broken_rule_input_never_breaks_the_page(
    client, settings, django_user_model, monkeypatch
):
    """The one page that must render when things are broken: a malformed cache entry lands as
    a fallback verdict, not a 500."""
    from core import diagnostics

    django_user_model.objects.create_superuser("owner", password="pw")
    settings.ATLAS_API_KEY = "test-key"
    monkeypatch.setattr(diagnostics.client_errors, "recent", lambda: ["not a dict"])
    response = client.get("/api/v1/diagnostics/", HTTP_X_API_KEY="test-key")
    assert response.status_code == 200
    body = response.json()
    assert body["findings"] == []
    assert body["verdict"]["text"] == "The verdict could not be computed — copy the report anyway."
    assert body["text"].startswith("verdict: The verdict could not be computed")


def test_details_name_the_evidence():
    rows = findings(
        _healthy(
            access={
                "summary": {
                    "days": 7,
                    "counts": {"api_key_rejected": 19},
                    "last_problem": {
                        "at": "2026-09-15T17:56:02",
                        "address": "127.0.0.1",
                        "kind": "api_key_rejected",
                    },
                },
                "events": [],
            },
            last_failed_compile={"manuscript": 9, "title": "Draft", "log": "!", "at": "t"},
        )
    )
    by_id = {r["id"]: r for r in rows}
    assert by_id["access_rejected"]["title"] == "19 requests carried a wrong API key"
    assert "last 2026-09-15 17:56 from 127.0.0.1" in by_id["access_rejected"]["detail"]
    assert by_id["access_rejected"]["link"] == "/connect"
    assert by_id["compile_failed"]["link"] == "/manuscripts/9/editor"
    assert "Draft" in by_id["compile_failed"]["title"]


def test_fails_sort_before_warns_and_the_verdict_counts_them():
    rows = findings(
        _healthy(
            engine=None,
            api_key_configured=False,
            server_log=" ERROR x",
            client_errors=[{"at": "t", "where": "w", "url": "u", "version": "", "errors": []}],
        )
    )
    assert [r["level"] for r in rows] == ["fail", "fail", "warn", "warn"]
    assert verdict(rows) == {"state": "fail", "text": "2 things broken · 2 to watch."}
    assert verdict(rows[2:]) == {"state": "warn", "text": "2 to watch."}
    assert verdict(rows[:1]) == {"state": "fail", "text": "1 thing broken."}


def test_the_text_leads_with_the_verdict():
    report = _healthy(engine=None)
    report["findings"] = findings(report)
    report["verdict"] = verdict(report["findings"])
    text = as_text(report)
    assert text.startswith(
        "verdict: 1 thing broken.\n  FAIL: No LaTeX engine — Every compile fails"
    )
    assert "→ Desktop builds bundle it" in text.splitlines()[1]
    healthy = _healthy()
    healthy["findings"], healthy["verdict"] = [], verdict([])
    assert as_text(healthy).startswith("verdict: Nothing wrong that Atlas can see.\n\nAtlas 0.1.0")


@pytest.mark.django_db
def test_the_api_and_the_live_collector_carry_it(client, settings, django_user_model):
    django_user_model.objects.create_superuser("owner", password="pw")
    settings.ATLAS_API_KEY = "test-key"
    body = client.get("/api/v1/diagnostics/", HTTP_X_API_KEY="test-key").json()
    assert body["verdict"]["state"] in ("ok", "warn", "fail")
    assert isinstance(body["findings"], list)
    assert body["disk"] is None or body["disk"]["free_bytes"] >= 0
    assert body["media_writable"] in (True, False, None)
    assert body["text"].startswith("verdict: ")


def test_ui_wiring():
    page = (BASE / "frontend" / "src" / "app" / "pages" / "Diagnostics.tsx").read_text()
    for needle in (
        'data-testid="verdict" data-state={r.verdict.state}',
        'data-testid="verdict-text"',
        'data-testid="finding" data-level={f.level} data-id={f.id}',
        'data-testid="finding-link"',
        "Nothing wrong",  # nothing hard-coded: the sentence comes from the server
        "the backups are fresh",  # the ok-state copy claims only what the rules establish
    ):
        absent = needle in ("Nothing wrong", "the backups are fresh")
        assert (needle in page) == (not absent), needle
    assert "Nothing needs doing." in page
    # the verdict block sits first inside the report render, above "This install"
    assert page.index('data-testid="verdict"') < page.index('data-testid="diag-summary"')
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "verdict-text" in chunks and "finding-link" in chunks
    server = (BASE / "mcp_server" / "server.py").read_text()
    assert "`verdict` + `findings` first" in server
