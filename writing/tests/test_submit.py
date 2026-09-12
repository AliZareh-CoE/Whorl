"""#469 — submitting goes through the pre-flight."""

import datetime

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone

from literature.tests.factories import ReferenceFactory
from projects.tests.factories import ProjectFactory
from writing.compile import source_hash
from writing.models import Manuscript, ManuscriptFile, ManuscriptReference, SubmissionEvent
from writing.services import SubmissionBlocked, submit_manuscript

pytestmark = pytest.mark.django_db


def _clean_manuscript(**kw):
    ref = ReferenceFactory(bibtex_key="clean2021key", doi="10.1/c", year=2021)
    m = Manuscript.objects.create(
        project=ProjectFactory(),
        title="Paper",
        status=kw.pop("status", "drafting"),
        target_venue="CogSci",
        deadline=kw.pop("deadline", timezone.localdate() + datetime.timedelta(days=10)),
        abstract="a fine abstract",
        compile_status="ok",
        compiled_bbl="x",
    )
    ManuscriptFile.objects.create(
        manuscript=m,
        path="main.tex",
        kind="tex",
        content="Text \\cite{clean2021key}.",
        is_main=True,
    )
    ManuscriptReference.objects.create(manuscript=m, reference=ref)
    m.compiled_pdf.save("m.pdf", ContentFile(b"%PDF-1.4"), save=False)
    m.compiled_source_hash = source_hash(m)
    m.compiled_at = timezone.now()
    m.save(update_fields=["compiled_pdf", "compiled_source_hash", "compiled_at"])
    return m


def test_never_compiled_paper_is_blocked_unless_forced():
    m = Manuscript.objects.create(project=ProjectFactory(), title="Raw", status="drafting")
    ManuscriptFile.objects.create(
        manuscript=m, path="main.tex", kind="tex", content="x", is_main=True
    )
    with pytest.raises(SubmissionBlocked) as blocked:
        submit_manuscript(m)
    assert blocked.value.preflight["ready"] is False
    m.refresh_from_db()
    assert m.status == "drafting" and not m.events.exists()
    out = submit_manuscript(m, force=True, notes="editor asked for it today")
    m.refresh_from_db()
    assert m.status == "submitted" and out["forced"] is True
    event = m.events.get()
    assert event.kind == "submitted" and event.date == timezone.localdate()
    assert "Submitted anyway over" in event.notes and "editor asked for it today" in event.notes
    assert "Compiled PDF" in event.notes


def test_clean_paper_submits_and_a_passed_deadline_does_not_block():
    m = _clean_manuscript(deadline=timezone.localdate() - datetime.timedelta(days=1))
    out = submit_manuscript(m, date=datetime.date(2026, 9, 1))
    assert out["forced"] is False and out["preflight"]["fails"] == 1  # the deadline row
    m.refresh_from_db()
    assert m.status == "submitted"
    assert m.events.get().date == datetime.date(2026, 9, 1)
    assert m.files.get().content == "Text \\cite{clean2021key}."  # update_fields: no alias sync


def test_revision_submits_as_revision_submitted_into_under_review():
    m = _clean_manuscript(status="revision")
    out = submit_manuscript(m)
    assert out["event"].kind == "revision_submitted"
    m.refresh_from_db()
    assert m.status == "under_review"


def test_api_409_then_force(client_logged_in):
    m = Manuscript.objects.create(project=ProjectFactory(), title="Raw", status="drafting")
    ManuscriptFile.objects.create(
        manuscript=m, path="main.tex", kind="tex", content="x", is_main=True
    )
    blocked = client_logged_in.post(
        f"/api/v1/manuscripts/{m.id}/submit/", {}, content_type="application/json"
    )
    assert blocked.status_code == 409 and blocked.json()["preflight"]["ready"] is False
    bad = client_logged_in.post(
        f"/api/v1/manuscripts/{m.id}/submit/",
        {"force": True, "date": "nope"},
        content_type="application/json",
    )
    assert bad.status_code == 400
    ok = client_logged_in.post(
        f"/api/v1/manuscripts/{m.id}/submit/",
        {"force": True, "date": "2026-09-10"},
        content_type="application/json",
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["manuscript"]["status"] == "submitted" and body["forced"] is True
    assert body["event"]["kind"] == "submitted" and body["event"]["date"] == "2026-09-10"
    assert SubmissionEvent.objects.filter(manuscript=m).count() == 1


def test_pipeline_routes_submitted_through_the_endpoint():
    from pathlib import Path

    tsx = Path("frontend/src/app/pages/Writing.tsx").read_text()
    assert "/submit/" in tsx and "Submit anyway" in tsx
