"""#466 — submission pre-flight: every check from real data, ready when nothing fails."""

import datetime

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone

from literature.tests.factories import ReferenceFactory
from projects.tests.factories import ProjectFactory
from writing import preflight as pf
from writing.compile import source_hash
from writing.models import Manuscript, ManuscriptFile, ManuscriptReference

pytestmark = pytest.mark.django_db


def _by(out):
    return {c["key"]: c for c in out["checks"]}


def _manuscript(**kw):
    defaults = dict(
        project=ProjectFactory(),
        title="Paper",
        target_venue="CogSci",
        deadline=timezone.localdate() + datetime.timedelta(days=30),
        abstract="a fine abstract",
    )
    defaults.update(kw)
    return Manuscript.objects.create(**defaults)


def test_never_compiled_manuscript_is_not_ready_and_says_why():
    m = _manuscript(target_venue="", deadline=None, abstract="")
    ManuscriptFile.objects.create(
        manuscript=m, path="main.tex", kind="tex", content="hello", is_main=True
    )
    out = pf.preflight(m)
    by = _by(out)
    assert out["ready"] is False and by["compile"]["state"] == "fail"
    assert by["compile"]["fix"] == {"kind": "compile"}
    assert by["errors"]["state"] == "skip" and by["cite_missing"]["state"] == "skip"
    assert by["venue"]["state"] == "warn" and by["deadline"]["state"] == "warn"
    assert by["abstract"]["state"] == "warn" and by["budget"]["state"] == "skip"
    assert by["figures"]["state"] == "skip" and by["leftovers"]["state"] == "ok"
    assert "Not ready" in out["summary"] and out["fails"] == 1


def test_every_failing_check_fires_on_a_broken_paper():
    m = _manuscript(
        deadline=timezone.localdate() - datetime.timedelta(days=2),
        venue_limits={"words": 3},
        compile_status="ok",
        compile_diagnostics=[
            {
                "level": "error",
                "file": "main.tex",
                "line": 4,
                "message": "Undefined control sequence",
            },
            {
                "level": "warning",
                "file": "main.tex",
                "line": 9,
                "message": "Citation `ghost' undefined",
            },
        ],
    )
    m.compiled_pdf.save("m.pdf", ContentFile(b"%PDF-1.4 stale"), save=False)
    m.compiled_source_hash = "stale"
    m.save(update_fields=["compiled_pdf", "compiled_source_hash"])
    ManuscriptFile.objects.create(
        manuscript=m,
        path="main.tex",
        kind="tex",
        content="one two three four five \\cite{ghost}\n% TODO tighten this\n"
        "\\includegraphics[width=1cm]{figures/missing}\n\\includegraphics{figures/ok.png}",
        is_main=True,
    )
    ManuscriptFile.objects.create(manuscript=m, path="figures/ok.png", kind="asset")
    ManuscriptReference.objects.create(
        manuscript=m, reference=ReferenceFactory(bibtex_key="unused2020x")
    )
    out = pf.preflight(m)
    by = _by(out)
    assert by["compile"]["state"] == "warn"  # stale PDF
    assert by["errors"]["state"] == "fail" and by["errors"]["fix"] == {
        "kind": "line",
        "path": "main.tex",
        "line": 4,
    }
    assert by["undefined"]["state"] == "fail" and "ghost" in by["undefined"]["detail"]
    assert by["cite_missing"]["state"] == "fail" and "ghost" in by["cite_missing"]["detail"]
    assert by["cite_unused"]["state"] == "warn" and "unused2020x" in by["cite_unused"]["detail"]
    assert by["budget"]["state"] == "fail" and "words" in by["budget"]["detail"]
    assert by["figures"]["state"] == "fail" and "figures/missing" in by["figures"]["detail"]
    assert by["figures"]["fix"] == {"kind": "line", "path": "main.tex", "line": 3}
    assert by["leftovers"]["state"] == "warn" and by["leftovers"]["fix"]["line"] == 2
    assert by["bbl"]["state"] == "warn"
    assert by["deadline"]["state"] == "fail" and "passed 2 days ago" in by["deadline"]["detail"]
    assert out["ready"] is False and out["fails"] >= 6


def test_a_clean_paper_is_ready(client_logged_in):
    ref = ReferenceFactory(bibtex_key="smith2020clean", doi="10.1/clean", year=2020)
    m = _manuscript(
        venue_limits={"words": 100}, compile_status="ok", compiled_bbl="\\bibitem{smith2020clean} x"
    )
    ManuscriptFile.objects.create(
        manuscript=m,
        path="main.tex",
        kind="tex",
        content="A short paper \\cite{smith2020clean}.\n\\includegraphics{fig1}",
        is_main=True,
    )
    ManuscriptFile.objects.create(manuscript=m, path="fig1.pdf", kind="asset")
    ManuscriptReference.objects.create(manuscript=m, reference=ref)
    m.compiled_pdf.save("m.pdf", ContentFile(b"%PDF-1.4 fresh"), save=False)
    m.compiled_source_hash = source_hash(m)
    m.compiled_at = timezone.now()
    m.save(update_fields=["compiled_pdf", "compiled_source_hash", "compiled_at"])
    out = pf.preflight(m)
    by = _by(out)
    assert by["compile"]["state"] == "ok" and by["figures"]["state"] == "ok"
    assert by["cite_missing"]["state"] == "ok" and by["cite_unused"]["state"] == "ok"
    assert by["bbl"]["state"] == "ok" and by["budget"]["state"] == "ok"
    assert out["ready"] is True and out["fails"] == 0
    # the same over the API, and the bib hygiene row carries no network rows unless asked
    api = client_logged_in.get(f"/api/v1/manuscripts/{m.id}/preflight/").json()
    assert api["ready"] is True and api["network"] is False
    assert "doi" not in _by(api)
    assert _by(api)["retractions"]["state"] == "ok"  # #527: stored verdicts, no network


def test_studio_has_the_panel_and_the_action():
    from pathlib import Path

    tsx = Path("frontend/src/app/pages/Studio.tsx").read_text()
    for needle in (
        '["preflight", ClipboardCheck, "Pre-flight"]',  # the tab (testid is built at runtime)
        "preflight/",
        'data-testid="preflight-run"',
        "Pre-flight check",
    ):
        assert needle in tsx, needle


def test_manuscript_page_has_the_readiness_card_and_the_studio_opens_the_panel():
    """#467: the summary lives where the status is changed; the Studio honours ?panel=."""
    from pathlib import Path

    writing = Path("frontend/src/app/pages/Writing.tsx").read_text()
    assert 'data-testid="preflight-card"' in writing and "/editor?panel=preflight" in writing
    studio = Path("frontend/src/app/pages/Studio.tsx").read_text()
    assert 'params.get("panel")' in studio
