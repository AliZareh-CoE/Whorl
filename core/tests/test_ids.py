"""Audit #31: ids from the wire never reach a `pk__in` past the 32-bit column — SQLite (the
desktop) raises OverflowError binding anything past 2**63, and Django's `__in` lookup does not
range-check the way `exact` / `gte` / `lte` do."""

import json

import pytest

from core.ids import MAX_PK, parse_ids
from literature.tests.factories import ReferenceFactory

HEADERS = {"HTTP_X_API_KEY": "k", "HTTP_HOST": "127.0.0.1"}


def test_parse_ids_drops_junk_out_of_range_and_duplicates():
    assert parse_ids(["3", " 1 ", "abc", "1e2", "-1", "0", 2, "3", str(10**20)]) == [3, 1, 2]
    assert parse_ids([MAX_PK, MAX_PK + 1, 2**40, 2**63, 2**70]) == [MAX_PK]
    assert parse_ids([True, False, 1.5, None, 7]) == [7]
    assert parse_ids(None) == [] and parse_ids("") == []
    assert parse_ids(range(1, 1000), limit=5) == [1, 2, 3, 4, 5]


def test_parse_ids_strict_refuses_non_integers_but_still_drops_out_of_range():
    with pytest.raises(ValueError):
        parse_ids(["a"], strict=True)
    with pytest.raises(ValueError):
        parse_ids([1.5], strict=True)
    with pytest.raises(ValueError):
        parse_ids([True], strict=True)
    assert parse_ids([10**20, 4], strict=True) == [4]


@pytest.mark.django_db
def test_endpoints_refuse_or_drop_ids_past_the_column(client, settings, owner):
    settings.ATLAS_API_KEY = "k"
    ref = ReferenceFactory(title="Kept")
    big = 10**20
    # query-string ids: the wild one is dropped, the file still carries the real paper
    r = client.get(f"/api/v1/references/export/?fmt=csv&ids={big},{ref.pk},{2**40}", **HEADERS)
    assert r.status_code == 200 and "Kept" in r.content.decode("utf-8-sig")
    r = client.get(f"/api/v1/references/cite/?ids={big},{ref.pk}", **HEADERS)
    assert r.status_code == 200
    # JSON ids: the retraction check drops it, the bulk bar and the reorders refuse it
    r = client.post(
        "/api/v1/references/check-retractions/",
        data=json.dumps({"ids": [big]}),
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 200 and r.json()["checked"] == 0
    r = client.post(
        "/api/v1/references/bulk/",
        data=json.dumps({"ids": [big], "action": "delete"}),
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 400 and "ids" in r.json()
    r = client.post(
        "/api/v1/quick-capture/bulk/",
        data=json.dumps({"ids": [big], "action": "dismiss"}),
        content_type="application/json",
        **HEADERS,
    )
    assert r.status_code == 400 and "ids" in r.json()
    for path in ("/api/v1/todos/reorder/", "/api/v1/library-views/reorder/"):
        r = client.post(
            path, data=json.dumps({"ids": [big]}), content_type="application/json", **HEADERS
        )
        assert r.status_code == 400, path
