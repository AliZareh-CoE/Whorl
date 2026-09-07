"""#455 (backlog #115): identical source is not compiled twice."""

import pytest
from django.core.files.base import ContentFile

from literature.models import Reference
from writing.compile import source_hash
from writing.models import Manuscript, ManuscriptFile, ManuscriptReference
from writing.tests.factories import ManuscriptFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.fixture
def ms(db):
    m = ManuscriptFactory()
    ManuscriptFile.objects.create(
        manuscript=m, path="main.tex", content="\\cite{a}", kind="tex", is_main=True
    )
    return m


def test_hash_follows_content_assets_and_bibliography(ms):
    h0 = source_hash(ms)
    assert h0 == source_hash(ms)
    f = ms.files.get(path="main.tex")
    f.content = "\\cite{a} changed"
    f.save()
    h1 = source_hash(ms)
    assert h1 != h0
    ref = Reference.objects.create(title="A", bibtex_key="a2020")
    ManuscriptReference.objects.create(manuscript=ms, reference=ref)
    h2 = source_hash(ms)
    assert h2 != h1  # the generated bibliography is part of what a compile reads
    ManuscriptFile.objects.create(
        manuscript=ms, path="references.bib", content="@misc{a2020}", kind="bib"
    )
    h3 = source_hash(ms)
    assert h3 != h2
    fig = ManuscriptFile(manuscript=ms, path="figures/x.png", kind="asset")
    fig.asset.save("x.png", ContentFile(b"\x89PNG" + b"\x00" * 8), save=False)
    fig.save()
    assert source_hash(ms) != h3


@pytest.mark.django_db
def test_action_dedupes_running_and_skips_unchanged(client, owner, ms, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "writing.tasks.enqueue_compile", lambda pk, gen: calls.append((pk, gen)) or "thread"
    )
    url = f"/api/v1/manuscripts/{ms.pk}/compile/"
    first = client.post(url, **HEADERS)
    assert first.status_code == 202 and first.json() == {"status": "running"} and len(calls) == 1
    ms.refresh_from_db()
    assert ms.compile_source_hash == source_hash(ms) and ms.compile_generation == 1
    again = client.post(url, **HEADERS)
    assert again.status_code == 202 and again.json()["deduped"] is True and len(calls) == 1
    # the compile finished with this tree → a further request is already answered
    ms.compile_status = Manuscript.CompileStatus.OK
    ms.compiled_source_hash = ms.compile_source_hash
    ms.compiled_pdf.save("m.pdf", ContentFile(b"%PDF-1.4"), save=False)
    ms.save()
    done = client.post(url, **HEADERS)
    assert done.status_code == 200 and done.json()["unchanged"] is True and len(calls) == 1
    # force compiles anyway
    forced = client.post(url, {"force": True}, content_type="application/json", **HEADERS)
    assert forced.status_code == 202 and forced.json() == {"status": "running"} and len(calls) == 2
    # a change to the source compiles
    ms.refresh_from_db()
    ms.compile_status = Manuscript.CompileStatus.OK
    ms.save()
    f = ms.files.get(path="main.tex")
    f.content = "new"
    f.save()
    changed = client.post(url, **HEADERS)
    assert changed.status_code == 202 and "deduped" not in changed.json() and len(calls) == 3


def test_successful_compile_records_the_hash(ms, monkeypatch, tmp_path):
    """compile_manuscript stamps compiled_source_hash from the queued hash on success."""
    import subprocess

    from writing import compile as compile_mod

    monkeypatch.setattr(compile_mod, "tectonic_path", lambda: tmp_path / "tectonic")
    monkeypatch.setattr(compile_mod, "tectonic_available", lambda: True)

    def fake_run(cmd, cwd, **kw):
        (cwd / "main.pdf").write_bytes(b"%PDF-1.4\n")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(compile_mod.subprocess, "run", fake_run)
    ms.compile_source_hash = "queued-hash"
    ms.save(
        update_fields=["compile_source_hash"]
    )  # a bare save would alias latex_source over main.tex
    compile_mod.compile_manuscript(ms)
    ms.refresh_from_db()
    assert ms.compile_status == "ok", ms.compile_log
    assert ms.compiled_source_hash == "queued-hash"


def test_mcp_and_studio_wiring(monkeypatch):
    from pathlib import Path

    from django.conf import settings as dj

    from mcp_server import client as mcp_client
    from mcp_server import server

    seen = {}
    monkeypatch.setattr(mcp_client, "_request", lambda m, p, **kw: seen.update(kw, path=p) or {})
    server.compile_manuscript(3, force=True)
    assert seen["json"] == {"force": True}
    src = (Path(dj.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Studio.tsx").read_text()
    assert "out.unchanged" in src and "nothing changed since the last compile" in src
