"""#442 (backlog #131): the compile keeps the .bbl and the submission zip ships it."""

import io
import zipfile
from pathlib import Path

import pytest

from writing import compile as compile_mod
from writing.models import Manuscript, ManuscriptFile
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(client, django_user_model):
    user = django_user_model.objects.create_superuser("owner", password="pw")
    client.force_login(user)
    return user


def test_compile_keeps_intermediates_and_stores_the_bbl(monkeypatch, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    ms = ManuscriptFactory()
    ManuscriptFile.objects.create(
        manuscript=ms, path="main.tex", content="\\documentclass{article}", kind="tex", is_main=True
    )
    monkeypatch.setattr(compile_mod, "tectonic_path", lambda: Path("/fake/tectonic"))
    seen = {}

    def fake_run(args, cwd, **kw):
        seen["args"] = args
        (Path(cwd) / "main.pdf").write_bytes(b"%PDF-1.4\n%fake")
        (Path(cwd) / "main.bbl").write_text(
            "\\begin{thebibliography}{1}\n\\bibitem{a} A.\n\\end{thebibliography}\n"
        )

        class Proc:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Proc()

    monkeypatch.setattr(compile_mod.subprocess, "run", fake_run)
    compile_mod.compile_manuscript(ms)
    assert "--keep-intermediates" in seen["args"]
    ms.refresh_from_db()
    assert ms.compile_status == Manuscript.CompileStatus.OK
    assert ms.compiled_bbl.startswith("\\begin{thebibliography}")


def test_submission_zip_ships_the_bbl_named_after_the_main_file(client, owner):
    ms = ManuscriptFactory(title="Paper")
    ManuscriptFile.objects.create(
        manuscript=ms, path="paper.tex", content="x", kind="tex", is_main=True
    )
    ManuscriptFile.objects.create(manuscript=ms, path="sections/a.tex", content="y", kind="tex")
    ms.compiled_bbl = "\\begin{thebibliography}{1}\\end{thebibliography}"
    ms.save(update_fields=["compiled_bbl"])
    url = f"/projects/{ms.project.slug}/writing/{ms.pk}/submission.zip"
    r = client.get(url)
    assert r.status_code == 200
    names = set(zipfile.ZipFile(io.BytesIO(r.content)).namelist())
    assert "paper.bbl" in names and "paper.tex" in names and "sections/a.tex" in names
    # a tree that already carries a .bbl is left alone
    ManuscriptFile.objects.create(manuscript=ms, path="paper.bbl", content="mine", kind="tex")
    names = set(zipfile.ZipFile(io.BytesIO(client.get(url).content)).namelist())
    assert names.count("paper.bbl") if isinstance(names, list) else "paper.bbl" in names
    z = zipfile.ZipFile(io.BytesIO(client.get(url).content))
    assert z.read("paper.bbl") == b"mine"


def test_zip_without_a_compile_has_no_bbl(client, owner):
    ms = ManuscriptFactory(title="Fresh")
    ManuscriptFile.objects.create(
        manuscript=ms, path="main.tex", content="x", kind="tex", is_main=True
    )
    r = client.get(f"/projects/{ms.project.slug}/writing/{ms.pk}/submission.zip")
    assert not any(n.endswith(".bbl") for n in zipfile.ZipFile(io.BytesIO(r.content)).namelist())
