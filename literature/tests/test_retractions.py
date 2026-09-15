"""#527: the retraction watch."""

import datetime
import json
from pathlib import Path

import httpx
import pytest
from django.conf import settings
from django.utils import timezone

from literature import retractions
from literature.library import facets, filter_references
from literature.models import Reference
from literature.tests.factories import ReferenceFactory


def notice(kind="retraction", doi="10.1/notice", date_parts=None):
    update = {"type": kind, "DOI": "10.1/paper"}
    if date_parts is not None:
        update["updated"] = {"date-parts": [date_parts]}
    return {"message": {"items": [{"DOI": doi, "update-to": [update]}]}}


def mock(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def answer(payload, status=200):
    return mock(lambda request: httpx.Response(status, content=json.dumps(payload)))


@pytest.mark.django_db
class TestLookupAndCheck:
    def test_lookup_reads_the_first_retraction_class_notice(self):
        client = answer(
            {
                "message": {
                    "items": [
                        {"DOI": "10.1/correction", "update-to": [{"type": "correction"}]},
                        {
                            "DOI": "10.1/eoc",
                            "update-to": [{"type": "expression_of_concern"}],
                        },
                        {
                            "DOI": "10.1/notice",
                            "update-to": [
                                "junk",
                                {"type": "Withdrawal", "updated": {"date-parts": [[2021, 3]]}},
                            ],
                        },
                    ]
                }
            }
        )
        found = retractions.lookup("10.1/paper", client)
        assert found == {
            "kind": "withdrawal",
            "notice": "10.1/notice",
            "date": datetime.date(2021, 3, 1),
        }
        assert retractions.lookup("10.1/paper", answer({"message": {"items": []}})) is None
        partial = notice(kind="partial_retraction", doi="10.1/partial")
        assert retractions.lookup("10.1/paper", answer(partial))["kind"] == "retraction"

    def test_lookup_raises_on_non_200(self):
        with pytest.raises(RuntimeError):
            retractions.lookup("10.1/paper", answer({}, status=503))

    def test_check_sets_then_clears_the_verdict(self):
        ref = ReferenceFactory(doi="10.1/paper")
        row = retractions.check_reference(ref, answer(notice(date_parts=[2019, 6, 12])))
        ref.refresh_from_db()
        assert row["retracted"] is True and row["kind"] == "retraction" and row["error"] == ""
        assert ref.retraction_kind == "retraction"
        assert ref.retraction_notice == "10.1/notice"
        assert ref.retraction_date == datetime.date(2019, 6, 12)
        assert ref.retraction_checked_at is not None
        # a later clean answer withdraws the flag
        retractions.check_reference(ref, answer({"message": {"items": []}}))
        ref.refresh_from_db()
        assert ref.retraction_kind == "" and ref.retraction_notice == ""
        assert ref.retraction_date is None

    def test_failures_leave_the_verdict_and_the_stamp_alone(self):
        stamp = timezone.now() - datetime.timedelta(days=40)
        ref = ReferenceFactory(
            doi="10.1/paper",
            retraction_kind="retraction",
            retraction_notice="10.1/notice",
            retraction_checked_at=stamp,
        )

        def boom(request):
            raise httpx.ConnectError("offline")

        row = retractions.check_reference(ref, mock(boom))
        assert row["error"].startswith("check failed") and row["retracted"] is True
        ref.refresh_from_db()
        assert ref.retraction_kind == "retraction" and ref.retraction_checked_at == stamp
        row = retractions.check_reference(ref, answer({}, status=500))
        assert row["error"]
        ref.refresh_from_db()
        assert ref.retraction_kind == "retraction" and ref.retraction_checked_at == stamp

    def test_no_doi_is_skipped(self):
        ref = ReferenceFactory(doi=None)
        out = retractions.check_references([ref], answer(notice()))
        assert out["skipped"] == 1 and out["checked"] == 0 and out["retracted"] == []
        ref.refresh_from_db()
        assert ref.retraction_checked_at is None

    def test_breaker_stops_an_offline_sweep(self):
        refs = [ReferenceFactory(doi=f"10.1/{i}") for i in range(10)]

        def dead(request):
            raise httpx.ReadTimeout("black hole")

        out = retractions.check_references(refs, mock(dead))
        assert out["stopped"] is True and out["errors"] == 5 and len(out["rows"]) == 5
        assert out["checked"] == 0
        assert all(r.retraction_checked_at is None for r in Reference.objects.all())

    def test_check_references_summary(self):
        a = ReferenceFactory(doi="10.1/a")
        b = ReferenceFactory(doi="10.1/b")
        c = ReferenceFactory(doi="10.1/c")

        def handler(request):
            doi = request.url.params["filter"].removeprefix("updates:")
            if doi == "10.1/a":
                return httpx.Response(200, content=json.dumps(notice()))
            if doi == "10.1/c":
                raise httpx.ReadTimeout("slow")
            return httpx.Response(200, content=json.dumps({"message": {"items": []}}))

        out = retractions.check_references([a, b, c], mock(handler))
        assert out["checked"] == 2 and out["errors"] == 1 and out["skipped"] == 0
        assert [r["id"] for r in out["retracted"]] == [a.pk]
        assert "rows" in out and len(out["rows"]) == 3


@pytest.mark.django_db
class TestStaleAndStatus:
    def test_stale_selection_never_checked_first_then_oldest(self):
        now = timezone.now()
        fresh = ReferenceFactory(doi="10.1/fresh", retraction_checked_at=now)
        old = ReferenceFactory(
            doi="10.1/old", retraction_checked_at=now - datetime.timedelta(days=45)
        )
        older = ReferenceFactory(
            doi="10.1/older", retraction_checked_at=now - datetime.timedelta(days=90)
        )
        never = ReferenceFactory(doi="10.1/never")
        ReferenceFactory(doi=None)  # no DOI: never a candidate
        got = retractions.stale_references(days=30, limit=10)
        assert [r.pk for r in got] == [never.pk, older.pk, old.pk]
        assert fresh not in got
        assert [r.pk for r in retractions.stale_references(days=30, limit=1)] == [never.pk]
        # Audit #31: days is clamped to MAX_STALE_DAYS, so a wild value cannot overflow
        assert [r.pk for r in retractions.stale_references(days=10**20, limit=10)] == [never.pk]

    def test_check_stale_asks_nothing_when_nothing_is_stale(self, monkeypatch):
        ReferenceFactory(doi="10.1/fresh", retraction_checked_at=timezone.now())
        monkeypatch.setattr(retractions, "check_references", lambda *a, **k: pytest.fail("asked"))
        out = retractions.check_stale()
        assert out["checked"] == 0 and out["retracted"] == []

    def test_watch_status_and_filter_and_facet(self):
        flagged = ReferenceFactory(
            doi="10.1/x", retraction_kind="withdrawal", retraction_checked_at=timezone.now()
        )
        ReferenceFactory(doi="10.1/y", retraction_checked_at=timezone.now())
        ReferenceFactory(doi="10.1/z")
        status = retractions.watch_status()
        assert status["retracted"] == 1 and status["unchecked"] == 1
        assert status["with_doi"] == 3 and status["last_checked_at"] is not None
        qs = filter_references(Reference.objects.all(), {"retracted": "true"})
        assert list(qs.values_list("pk", flat=True)) == [flagged.pk]
        assert facets(Reference.objects.all())["retracted"] == 1
        assert list(retractions.retracted_references()) == [flagged]


@pytest.mark.django_db
class TestApiAndReport:
    def test_endpoint_checks_ids_and_stale_and_refuses_junk(
        self, client, settings, owner, monkeypatch
    ):
        settings.ATLAS_API_KEY = "k"
        headers = {"HTTP_X_API_KEY": "k", "HTTP_HOST": "127.0.0.1"}
        a = ReferenceFactory(doi="10.1/a")
        ReferenceFactory(doi="10.1/b")
        monkeypatch.setattr(
            retractions,
            "lookup",
            lambda doi, client: (
                {"kind": "retraction", "notice": "10.1/n", "date": None}
                if doi == "10.1/a"
                else None
            ),
        )
        # 401 without the key
        assert client.post("/api/v1/references/check-retractions/").status_code == 401
        r = client.post(
            "/api/v1/references/check-retractions/",
            data=json.dumps({"ids": [a.pk]}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["checked"] == 1 and body["retracted"][0]["bibtex_key"] == a.bibtex_key
        assert body["status"]["retracted"] == 1 and "rows" not in body
        # the row now carries the verdict
        row = client.get(f"/api/v1/references/{a.pk}/", **headers).json()
        assert row["retraction_kind"] == "retraction" and row["retraction_notice"] == "10.1/n"
        assert row["retraction_checked_at"]
        # stale: only b is unchecked now
        r = client.post(
            "/api/v1/references/check-retractions/",
            data=json.dumps({"stale": True, "limit": 500}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200 and r.json()["checked"] == 1
        assert r.json()["status"]["unchecked"] == 0
        # Audit #31: a wild `days` was a datetime overflow (500); it is clamped to ten years
        r = client.post(
            "/api/v1/references/check-retractions/",
            data=json.dumps({"stale": True, "days": 10**20}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200 and r.json()["checked"] == 0
        # list filter + facet over the API
        listed = client.get("/api/v1/references/?retracted=1", **headers).json()
        assert [x["id"] for x in listed["results"]] == [a.pk]
        assert client.get("/api/v1/references/facets/", **headers).json()["retracted"] == 1
        # GET: status only
        assert (
            client.get("/api/v1/references/check-retractions/", **headers).json()["status"][
                "retracted"
            ]
            == 1
        )
        # junk ids
        for bad in ({"ids": ["x"]}, {"ids": list(range(51))}, {"ids": "1"}):
            r = client.post(
                "/api/v1/references/check-retractions/",
                data=json.dumps(bad),
                content_type="application/json",
                **headers,
            )
            assert r.status_code == 400, bad

    def test_bib_report_reports_a_stored_verdict_without_asking(self):
        from literature import services

        ref = ReferenceFactory(doi="10.1/a", retraction_kind="retraction", retraction_notice="n")

        def boom(request):
            raise AssertionError("must not ask Crossref for a flagged paper")

        findings = services.check_retractions([ref], client=mock(boom))
        assert (
            findings and findings[0]["level"] == "error" and "RETRACTED" in findings[0]["message"]
        )

    def test_preflight_row_from_stored_flags(self):
        from projects.tests.factories import ProjectFactory
        from writing.models import Manuscript, ManuscriptReference
        from writing.preflight import check_bibliography

        project = ProjectFactory()
        m = Manuscript.objects.create(project=project, title="M")
        good = ReferenceFactory(doi="10.1/good")
        bad = ReferenceFactory(doi="10.1/bad", retraction_kind="retraction")
        ManuscriptReference.objects.create(manuscript=m, reference=good)
        ManuscriptReference.objects.create(manuscript=m, reference=bad)
        rows = {r["key"]: r for r in check_bibliography(m, network=False)}
        assert rows["retractions"]["state"] == "fail"
        assert bad.bibtex_key in rows["retractions"]["detail"]
        assert "doi" not in rows  # still a network-only row


def test_ui_wiring():
    base = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"
    lib = (base / "Library.tsx").read_text()
    for needle in (
        'data-testid="rail-retracted"',
        'data-testid="check-retractions"',
        'data-testid="retracted-chip"',
        'data-testid="retraction-banner"',
        'data-testid="retraction-ok"',
        '"/references/check-retractions/"',
        'retracted: ""',
        'if (k === "retracted") return "retracted";',
        "https://doi.org/${r.retraction_notice}",
    ):
        assert needle in lib, needle
    assert lib.count('data-testid="retracted-chip"') == 2  # list row and card
    page = (base / "Reference.tsx").read_text()
    assert 'data-testid="retraction-banner"' in page and "retraction_notice" in page
