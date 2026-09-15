"""#544: the library fills its own PDFs — the finder stamps what it learned, and a bounded
sweep runs it over the papers without a PDF."""

import datetime
import json
from pathlib import Path

import httpx
import pytest
from django.conf import settings as django_settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone

from literature import oa
from literature.models import Reference

from .factories import ReferenceFactory

pytestmark = pytest.mark.django_db

FAKE_PDF = b"%PDF-1.4 tiny"


@pytest.fixture
def patch_http(monkeypatch):
    state = {"handler": None}
    real_client = httpx.Client

    def client_factory(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(state["handler"]), **kwargs)

    monkeypatch.setattr(oa.httpx, "Client", client_factory)
    return state


class TestStamps:
    def test_an_answer_stamps_the_row_and_an_attach_records_the_source(self, patch_http):
        ref = ReferenceFactory(arxiv_id="1706.03762", doi=None)
        patch_http["handler"] = lambda request: httpx.Response(200, content=FAKE_PDF)
        out = oa.find_pdf(ref)
        ref.refresh_from_db()
        assert out["attached"] and out["answered"] and out["source"] == "arxiv"
        assert ref.pdf_source == "arxiv" and ref.pdf_checked_at is not None

    def test_a_miss_is_stamped_but_offline_is_not(self, patch_http):
        ref = ReferenceFactory(doi="10.1/closed")
        patch_http["handler"] = lambda request: httpx.Response(404, json={})
        out = oa.find_pdf(ref)
        ref.refresh_from_db()
        assert not out["attached"] and out["answered"] and out["outcome"] == oa.NOT_FOUND
        assert ref.pdf_checked_at is not None and ref.pdf_source == ""
        stamped = ref.pdf_checked_at

        def down(request):
            raise httpx.ConnectError("down")

        patch_http["handler"] = down
        ref.pdf_checked_at = None
        ref.save(update_fields=["pdf_checked_at"])
        out = oa.find_pdf(ref)
        ref.refresh_from_db()
        assert not out["answered"] and out["outcome"] == oa.NOT_FOUND
        assert ref.pdf_checked_at is None and stamped is not None

    def test_already_attached_is_not_a_lookup(self, patch_http):
        ref = ReferenceFactory(doi="10.1/have", pdf_source="unpaywall")
        ref.pdf.save("have.pdf", ContentFile(FAKE_PDF), save=True)
        patch_http["handler"] = lambda request: pytest.fail("no request expected")
        out = oa.find_pdf(ref)
        assert out == {
            "outcome": "PDF already attached.",
            "attached": True,
            "source": "unpaywall",
            "answered": False,
        }


class TestSelection:
    def test_stale_missing_orders_never_looked_first_then_oldest(self):
        now = timezone.now()
        a = ReferenceFactory(doi="10.1/a", pdf_checked_at=now - datetime.timedelta(days=40))
        b = ReferenceFactory(doi="10.1/b")  # never looked at
        c = ReferenceFactory(doi="10.1/c", pdf_checked_at=now - datetime.timedelta(days=2))
        d = ReferenceFactory(doi="10.1/d", pdf_checked_at=now - datetime.timedelta(days=90))
        ReferenceFactory(doi=None, arxiv_id="")  # nothing to ask about
        with_pdf = ReferenceFactory(doi="10.1/e")
        with_pdf.pdf.save("e.pdf", ContentFile(FAKE_PDF), save=True)
        assert [r.pk for r in oa.stale_missing()] == [b.pk, d.pk, a.pk]
        assert [r.pk for r in oa.stale_missing(limit=1)] == [b.pk]
        assert [r.pk for r in oa.stale_missing(days=1)] == [b.pk, d.pk, a.pk, c.pk]
        assert oa.missing_pdfs().count() == 4
        status = oa.watch_status()
        assert (status["missing"], status["lookable"], status["unchecked"]) == (5, 4, 1)


class TestSweep:
    def test_counts_sources_and_the_offline_breaker(self, monkeypatch):
        refs = [ReferenceFactory(doi=f"10.1/{i}") for i in range(6)]
        script = iter(
            [
                {"attached": True, "source": "arxiv", "answered": True},
                {"attached": False, "source": "", "answered": True},
                {"attached": True, "source": "unpaywall", "answered": True},
                {"attached": False, "source": "", "answered": False},
                {"attached": False, "source": "", "answered": False},
                {"attached": False, "source": "", "answered": False},
            ]
        )

        def fake(reference):
            step = next(script)
            return {"outcome": "x", **step}

        monkeypatch.setattr(oa, "find_pdf", fake)
        out = oa.find_pdfs(refs)
        assert out["checked"] == 6 and out["not_found"] == 1 and out["errors"] == 3
        assert [r["source"] for r in out["attached"]] == ["arxiv", "unpaywall"]
        assert out["attached"][0]["bibtex_key"] == refs[0].bibtex_key
        assert out["stopped"] == "offline"

    def test_budget_stops_the_run_and_skips_what_it_cannot_ask(self, monkeypatch):
        refs = [ReferenceFactory(doi=f"10.1/b{i}") for i in range(3)]
        refs.append(ReferenceFactory(doi=None, arxiv_id=""))
        calls = []
        monkeypatch.setattr(
            oa,
            "find_pdf",
            lambda r: (
                calls.append(r.pk)
                or {"outcome": "x", "attached": False, "source": "", "answered": True}
            ),
        )
        out = oa.find_pdfs(refs, budget_seconds=-1)
        assert out["stopped"] == "budget" and out["checked"] == 0 and calls == []
        out = oa.find_pdfs(refs)
        assert out["checked"] == 3 and out["skipped"] == 1 and out["stopped"] == ""

    def test_sweep_missing_carries_the_status_and_the_command_prints(self, monkeypatch, capsys):
        ref = ReferenceFactory(doi="10.1/sweep")
        monkeypatch.setattr(
            oa,
            "find_pdf",
            lambda r: {"outcome": "x", "attached": True, "source": "s2", "answered": True},
        )
        out = oa.sweep_missing()
        assert out["checked"] == 1 and out["attached"][0]["id"] == ref.pk and "status" in out
        call_command("find_pdfs", "--limit", "5")
        printed = capsys.readouterr().out
        assert "checked 1" in printed and "ATTACHED" in printed

    def test_huey_task_and_desktop_tick_honour_the_auto_fetch_gate(self, monkeypatch, settings):
        from literature import tasks

        called = []
        monkeypatch.setattr(oa, "sweep_missing", lambda *a, **k: called.append(k) or {})
        settings.ATLAS_AUTO_FETCH_PDF = False
        assert tasks.find_pdfs_task.func() is None and called == []
        settings.ATLAS_AUTO_FETCH_PDF = True
        tasks.find_pdfs_task.func()
        assert len(called) == 1


class TestApi:
    def test_status_sweep_ids_and_junk(self, client, owner, settings, monkeypatch):
        settings.ATLAS_API_KEY = "k"
        headers = {"HTTP_X_API_KEY": "k"}
        a = ReferenceFactory(doi="10.1/api-a")
        b = ReferenceFactory(doi="10.1/api-b")
        monkeypatch.setattr(
            oa,
            "find_pdf",
            lambda r: {
                "outcome": "x",
                "attached": r.pk == a.pk,
                "source": "openalex" if r.pk == a.pk else "",
                "answered": True,
            },
        )
        assert client.post("/api/v1/references/find-pdfs/").status_code == 401
        status = client.get("/api/v1/references/find-pdfs/", **headers).json()["status"]
        assert (status["lookable"], status["unchecked"], status["found_30d"]) == (2, 2, 0)
        r = client.post(
            "/api/v1/references/find-pdfs/",
            data=json.dumps({"ids": [a.pk]}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["checked"] == 1 and body["attached"][0]["source"] == "openalex"
        assert body["status"]["lookable"] == 2  # find_pdf is mocked: nothing really attached
        r = client.post(
            "/api/v1/references/find-pdfs/",
            data=json.dumps({"stale": True, "limit": 500}),
            content_type="application/json",
            **headers,
        )
        assert r.status_code == 200 and r.json()["checked"] == 2 and r.json()["not_found"] == 1
        assert b.pk in {a.pk, b.pk}
        for bad in ({"ids": ["x"]}, {"ids": list(range(21))}, {"ids": "1"}, {"days": "soon"}):
            r = client.post(
                "/api/v1/references/find-pdfs/",
                data=json.dumps(bad),
                content_type="application/json",
                **headers,
            )
            assert r.status_code == 400, bad
        row = client.get(f"/api/v1/references/{a.pk}/", **headers).json()
        assert "pdf_checked_at" in row and "pdf_source" in row


def test_ui_is_wired():
    root = Path(django_settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"
    lib = (root / "Library.tsx").read_text()
    for needle in (
        'data-testid="find-pdfs"',
        'data-testid="pdf-sweep-status"',
        "/references/find-pdfs/",
    ):
        assert needle in lib, needle


def test_settings_example_names_the_gate():
    text = (Path(django_settings.BASE_DIR) / ".env.example").read_text()
    assert "ATLAS_AUTO_FETCH_PDF=" in text


def test_reference_model_has_the_stamps():
    fields = {f.name for f in Reference._meta.get_fields()}
    assert {"pdf_checked_at", "pdf_source"} <= fields
