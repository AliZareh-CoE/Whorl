"""The LaTeX engine resolver (Owner report 2026-09-06: desktop builds shipped no engine)."""

from pathlib import Path

from writing import compile as compile_mod


def test_env_override_wins(monkeypatch, tmp_path):
    engine = tmp_path / "tectonic"
    engine.write_text("")
    monkeypatch.setenv("ATLAS_TECTONIC", str(engine))
    assert compile_mod.tectonic_path() == engine
    assert compile_mod.tectonic_available()


def test_bundled_bin_then_path(monkeypatch, tmp_path):
    monkeypatch.delenv("ATLAS_TECTONIC", raising=False)
    monkeypatch.setattr(compile_mod, "TECTONIC", tmp_path / "bin" / "tectonic")
    monkeypatch.setattr(compile_mod.shutil, "which", lambda name: None)
    assert compile_mod.tectonic_path() is None
    (tmp_path / "bin").mkdir()
    exe = tmp_path / "bin" / "tectonic.exe"  # Windows desktop build
    exe.write_text("")
    assert compile_mod.tectonic_path() == exe
    exe.unlink()
    monkeypatch.setattr(compile_mod.shutil, "which", lambda name: "/usr/bin/tectonic")
    assert compile_mod.tectonic_path() == Path("/usr/bin/tectonic")


def test_missing_engine_message_is_actionable():
    assert "Desktop builds bundle it" in compile_mod.MISSING_ENGINE
    assert "make tectonic" in compile_mod.MISSING_ENGINE


def test_file_list_bootstraps_main_tex(client_logged_in, db):
    """The studio lists files first — a manuscript with only latex_source gets its main.tex."""
    from projects.tests.factories import ProjectFactory
    from writing.models import Manuscript

    project = ProjectFactory()
    m = Manuscript.objects.create(project=project, title="Studio", latex_source="\\section{A}")
    data = client_logged_in.get(f"/projects/{project.slug}/writing/{m.pk}/files/").json()
    assert [f["path"] for f in data["files"]] == ["main.tex"] and data["files"][0]["is_main"]
