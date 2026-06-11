"""Multi-file manuscript workbench tests (Owner idea #24, parity slice 6)."""

import pytest
from django.core.exceptions import ValidationError

from writing.models import (
    Manuscript,
    ManuscriptFile,
    kind_for_path,
    validate_manuscript_path,
)
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db


HOSTILE_PATHS = [
    "../x.tex",
    "a/../b.tex",
    "/etc/passwd",
    "C:\\evil.tex",
    "a\\b.tex",
    "..",
    ".hidden",
    "figs/",
    "a//b.tex",
    "",
    "a" * 201,
    "/".join(["d"] * 9) + ".tex",
    "fi‮gure.png",
    "ƒig.png",
    "fig\x00.png",
]


class TestPathValidator:
    @pytest.mark.parametrize("path", HOSTILE_PATHS)
    def test_rejects_hostile_paths(self, path):
        with pytest.raises(ValidationError):
            validate_manuscript_path(path)

    @pytest.mark.parametrize(
        "path",
        ["main.tex", "sections/01-intro.tex", "figures/fig_1-final.png", "refs.bib", "acl.sty"],
    )
    def test_accepts_sane_paths(self, path):
        assert validate_manuscript_path(path) == path

    def test_kind_inferred_from_extension(self):
        assert kind_for_path("main.tex") == "tex"
        assert kind_for_path("acl.sty") == "tex"
        assert kind_for_path("refs.bib") == "bib"
        assert kind_for_path("fig.png") == "asset"
        assert kind_for_path("noext") == "asset"

    def test_unique_path_and_single_main_constraints(self):
        from django.db import IntegrityError, transaction

        m = ManuscriptFactory()
        ManuscriptFile.objects.create(manuscript=m, path="a.tex", is_main=True)
        with pytest.raises(IntegrityError), transaction.atomic():
            ManuscriptFile.objects.create(manuscript=m, path="a.tex")
        with pytest.raises(IntegrityError), transaction.atomic():
            ManuscriptFile.objects.create(manuscript=m, path="b.tex", is_main=True)


class TestAlias:
    def test_manuscript_save_syncs_to_main_file(self):
        m = ManuscriptFactory(latex_source="\\documentclass{article}")
        main = m.main_file
        assert main is not None and main.path == "main.tex"
        assert main.content == "\\documentclass{article}"
        m.latex_source = "updated"
        m.save()
        main.refresh_from_db()
        assert main.content == "updated"

    def test_main_file_save_syncs_back_to_latex_source(self):
        m = ManuscriptFactory(latex_source="seed")
        main = m.main_file
        main.content = "from the editor"
        main.save()
        m.refresh_from_db()
        assert m.latex_source == "from the editor"

    def test_status_only_save_does_not_clobber_main_file(self):
        m = ManuscriptFactory(latex_source="real content")
        assert m.main_file is not None  # ensure it exists
        # simulate a stale in-memory latex_source while compile saves status only
        m.latex_source = "STALE"
        m.compile_status = Manuscript.CompileStatus.OK
        m.save(update_fields=["compile_status", "updated_at"])
        assert m.main_file.content == "real content"

    def test_ensure_main_file_is_idempotent(self):
        m = ManuscriptFactory(latex_source="")
        first = m.ensure_main_file()
        second = m.ensure_main_file()
        assert first.pk == second.pk
        assert m.files.count() == 1


class TestWorkbenchCompile:
    def _patch_tectonic(self, monkeypatch, captured):
        from types import SimpleNamespace

        from writing import compile as compile_mod

        monkeypatch.setattr(compile_mod, "tectonic_available", lambda: True)

        def fake_run(cmd, cwd, **kwargs):
            captured["cmd"] = cmd
            captured["tree"] = {
                str(p.relative_to(cwd)): p.read_bytes()
                for p in __import__("pathlib").Path(cwd).rglob("*")
                if p.is_file()
            }
            main = cmd[-1]
            (__import__("pathlib").Path(cwd) / main).with_suffix(".pdf").write_bytes(b"%PDF-1.4")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(compile_mod.subprocess, "run", fake_run)

    def test_writes_tree_and_passes_untrusted(self, monkeypatch):
        from writing.compile import compile_manuscript

        m = ManuscriptFactory(latex_source="")
        ManuscriptFile.objects.create(
            manuscript=m, path="main.tex", content="\\input{sections/body}", is_main=True
        )
        ManuscriptFile.objects.create(manuscript=m, path="sections/body.tex", content="Hi")
        captured = {}
        self._patch_tectonic(monkeypatch, captured)
        compile_manuscript(m)
        assert "--untrusted" in captured["cmd"]
        assert "sections/body.tex" in captured["tree"]
        m.refresh_from_db()
        assert m.compile_status == "ok"

    def test_user_references_bib_not_clobbered(self, monkeypatch):
        from writing.compile import compile_manuscript

        m = ManuscriptFactory(latex_source="")
        ManuscriptFile.objects.create(manuscript=m, path="main.tex", content="x", is_main=True)
        ManuscriptFile.objects.create(manuscript=m, path="references.bib", content="@misc{mine}")
        captured = {}
        self._patch_tectonic(monkeypatch, captured)
        compile_manuscript(m)
        assert captured["tree"]["references.bib"] == b"@misc{mine}"

    def test_legacy_manuscript_without_files_uses_latex_source(self, monkeypatch):
        from writing.compile import compile_manuscript

        m = ManuscriptFactory(latex_source="")
        # bypass the alias so no file rows exist
        Manuscript.objects.filter(pk=m.pk).update(latex_source="legacy body")
        m = Manuscript.objects.get(pk=m.pk)
        assert m.files.count() == 0
        captured = {}
        self._patch_tectonic(monkeypatch, captured)
        compile_manuscript(m)
        assert captured["tree"]["main.tex"] == b"legacy body"

    def test_hostile_path_row_fails_safely(self, monkeypatch):
        from writing.compile import compile_manuscript

        m = ManuscriptFactory(latex_source="")
        ManuscriptFile.objects.create(manuscript=m, path="main.tex", content="x", is_main=True)
        # inject a hostile row past validation via bulk_create
        ManuscriptFile.objects.bulk_create(
            [ManuscriptFile(manuscript=m, path="ok.tex", kind="tex", content="y")]
        )
        ManuscriptFile.objects.filter(manuscript=m, path="ok.tex").update(path="../escape.tex")
        from types import SimpleNamespace

        from writing import compile as compile_mod

        monkeypatch.setattr(compile_mod, "tectonic_available", lambda: True)
        monkeypatch.setattr(
            compile_mod.subprocess,
            "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
        )
        compile_manuscript(m)
        m.refresh_from_db()
        assert m.compile_status == "failed"
        assert "outside the build" in m.compile_log

    def test_renamed_main_finds_pdf(self, monkeypatch):
        from writing.compile import compile_manuscript

        m = ManuscriptFactory(latex_source="")
        main = ManuscriptFile.objects.create(
            manuscript=m, path="main.tex", content="x", is_main=True
        )
        main.path = "paper.tex"
        main.save()
        captured = {}
        self._patch_tectonic(monkeypatch, captured)
        compile_manuscript(m)
        m.refresh_from_db()
        assert m.compile_status == "ok"
        assert captured["cmd"][-1] == "paper.tex"

    def test_files_but_no_main_fails(self, monkeypatch):
        from writing.compile import compile_manuscript

        m = ManuscriptFactory(latex_source="")
        ManuscriptFile.objects.create(manuscript=m, path="orphan.tex", content="x")
        compile_manuscript(m)
        m.refresh_from_db()
        assert m.compile_status == "failed"
        assert "main file" in m.compile_log.lower()


class TestWorkbenchViews:
    def _url(self, m, suffix=""):
        return f"/projects/{m.project.slug}/writing/{m.pk}/files/{suffix}"

    def test_list_and_create_json(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        created = client_logged_in.post(self._url(m), {"path": "sections/intro.tex"})
        assert created.status_code == 201
        listing = client_logged_in.get(self._url(m)).json()
        assert {f["path"] for f in listing["files"]} == {"main.tex", "sections/intro.tex"}

    def test_create_rejects_bad_path_and_duplicate(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        assert client_logged_in.post(self._url(m), {"path": "../evil.tex"}).status_code == 400
        assert client_logged_in.post(self._url(m), {"path": "main.tex"}).status_code == 400

    def test_file_save_returns_cite_counts(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        main = m.main_file
        res = client_logged_in.post(
            self._url(m, f"{main.pk}/save/"),
            {"content": "\\cite{ghostkey}"},
            headers={"X-SPA": "1"},
        )
        data = res.json()
        assert data["saved"] is True
        assert data["cite"]["missing_from_bib"] == 1
        main.refresh_from_db()
        assert main.content == "\\cite{ghostkey}"

    def test_rename_validates_and_renames(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        f = ManuscriptFile.objects.create(manuscript=m, path="a.tex", content="")
        ok = client_logged_in.post(self._url(m, f"{f.pk}/rename/"), {"path": "b.tex"})
        assert ok.status_code == 200
        bad = client_logged_in.post(self._url(m, f"{f.pk}/rename/"), {"path": "../x.tex"})
        assert bad.status_code == 400

    def test_delete_main_forbidden(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        res = client_logged_in.post(self._url(m, f"{m.main_file.pk}/delete/"))
        assert res.status_code == 400

    def test_delete_asset_removes_filefield(self, client_logged_in):
        from django.core.files.uploadedfile import SimpleUploadedFile

        m = ManuscriptFactory(latex_source="x")
        f = ManuscriptFile.objects.create(
            manuscript=m,
            path="fig.png",
            kind="asset",
            asset=SimpleUploadedFile("fig.png", b"\x89PNG", "image/png"),
        )
        res = client_logged_in.post(self._url(m, f"{f.pk}/delete/"))
        assert res.json()["deleted"] is True
        assert not ManuscriptFile.objects.filter(pk=f.pk).exists()

    def test_upload_rejects_disallowed_extension(self, client_logged_in):
        from django.core.files.uploadedfile import SimpleUploadedFile

        m = ManuscriptFactory(latex_source="x")
        res = client_logged_in.post(
            self._url(m, "upload/"),
            {"file": SimpleUploadedFile("evil.exe", b"MZ", "application/octet-stream")},
        )
        assert res.status_code == 400

    def test_upload_tex_lands_as_text(self, client_logged_in):
        from django.core.files.uploadedfile import SimpleUploadedFile

        m = ManuscriptFactory(latex_source="x")
        res = client_logged_in.post(
            self._url(m, "upload/"),
            {"file": SimpleUploadedFile("extra.tex", b"\\section{X}", "text/x-tex")},
        )
        assert res.status_code == 201
        f = ManuscriptFile.objects.get(manuscript=m, path="extra.tex")
        assert f.kind == "tex" and f.content == "\\section{X}"

    def test_endpoints_scoped_to_project(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        other = ManuscriptFactory(latex_source="y")
        # other manuscript's file id under m's url must 404
        res = client_logged_in.get(self._url(m, f"{other.main_file.pk}/"))
        assert res.status_code == 404

    def test_editor_get_bootstraps_main(self, client_logged_in):
        from django.urls import reverse

        m = ManuscriptFactory(latex_source="")
        client_logged_in.get(reverse("writing:editor", args=[m.project.slug, m.pk]))
        assert m.files.filter(is_main=True).count() == 1


class TestWorkbenchAPI:
    def test_files_crud_and_manuscript_filter(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        created = client_logged_in.post(
            "/api/v1/manuscript-files/",
            {"manuscript": m.pk, "path": "extra.tex", "content": "hi"},
            content_type="application/json",
        )
        assert created.status_code == 201
        assert created.json()["kind"] == "tex"
        listing = client_logged_in.get(f"/api/v1/manuscript-files/?manuscript={m.pk}").json()
        assert listing["count"] == 2

    def test_create_rejects_traversal(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        res = client_logged_in.post(
            "/api/v1/manuscript-files/",
            {"manuscript": m.pk, "path": "../evil.tex", "content": ""},
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_set_main_demotes_previous(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        old_main = m.main_file
        other = ManuscriptFile.objects.create(manuscript=m, path="b.tex", content="")
        res = client_logged_in.patch(
            f"/api/v1/manuscript-files/{other.pk}/",
            {"is_main": True},
            content_type="application/json",
        )
        assert res.status_code == 200
        old_main.refresh_from_db()
        other.refresh_from_db()
        assert other.is_main and not old_main.is_main

    def test_manuscript_includes_files_summary(self, client_logged_in):
        m = ManuscriptFactory(latex_source="x")
        data = client_logged_in.get(f"/api/v1/manuscripts/{m.pk}/").json()
        assert any(f["is_main"] for f in data["files"])

    def test_api_patch_latex_source_writes_main_file(self, client_logged_in):
        m = ManuscriptFactory(latex_source="orig")
        client_logged_in.patch(
            f"/api/v1/manuscripts/{m.pk}/",
            {"latex_source": "via api"},
            content_type="application/json",
        )
        assert m.main_file.content == "via api"

    def test_schema_includes_manuscript_files(self, client_logged_in):
        schema = client_logged_in.get("/api/schema/").content.decode()
        assert "/api/v1/manuscript-files/" in schema


class TestWordCount:
    """Owner idea #24 slice 8: approximate detex word count."""

    def test_strips_commands_math_and_comments(self):
        from writing.wordcount import word_count

        src = (
            "% a comment with five words here\n"
            "\\section{Introduction}\n"
            "This sentence has exactly six words.\n"
            "\\begin{equation} E = mc^2 \\end{equation}\n"
            "Inline $x + y$ math and \\textbf{bold text} here.\n"
        )
        result = word_count(src)
        assert result["headers"] == 1
        assert result["math_inlines"] == 1
        # "This sentence has exactly six words" (6) + "Inline math and bold text here" (6)
        # + "Introduction" heading text (1) = 13; comment excluded
        assert result["words"] == 13

    def test_counts_captions(self):
        from writing.wordcount import word_count

        src = "\\caption{First}\n\\caption{Second}\nbody words two"
        assert word_count(src)["captions"] == 2

    def test_endpoint_counts_all_tex_files(self, client_logged_in):
        m = ManuscriptFactory(latex_source="")
        ManuscriptFile.objects.create(
            manuscript=m, path="main.tex", content="one two three", is_main=True
        )
        ManuscriptFile.objects.create(manuscript=m, path="sections/a.tex", content="four five")
        data = client_logged_in.get(f"/projects/{m.project.slug}/writing/{m.pk}/word-count/").json()
        assert data["words"] == 5


class TestRevisions:
    """Owner idea #24 slice 9: version history — snapshot, label, diff, restore, trim."""

    def test_snapshot_captures_text_files(self):
        from writing.models import ManuscriptFile, snapshot_manuscript

        m = ManuscriptFactory(latex_source="")
        ManuscriptFile.objects.create(manuscript=m, path="main.tex", content="hello", is_main=True)
        ManuscriptFile.objects.create(manuscript=m, path="refs.bib", content="@misc{a}")
        rev = snapshot_manuscript(m, label="v1")
        assert rev.files == {"main.tex": "hello", "refs.bib": "@misc{a}"}
        assert rev.is_labeled

    def test_trim_keeps_labeled_and_last_50_auto(self):
        from writing.models import snapshot_manuscript

        m = ManuscriptFactory(latex_source="x")
        snapshot_manuscript(m, label="keep me")
        for _ in range(55):
            snapshot_manuscript(m)
        revs = m.revisions.all()
        assert revs.filter(label="keep me").count() == 1
        assert revs.filter(label="").count() == 50  # auto trimmed to 50

    def test_compile_creates_snapshot(self, monkeypatch):
        from types import SimpleNamespace

        from writing import compile as compile_mod
        from writing.models import ManuscriptFile

        m = ManuscriptFactory(latex_source="")
        ManuscriptFile.objects.create(manuscript=m, path="main.tex", content="hi", is_main=True)
        monkeypatch.setattr(compile_mod, "tectonic_available", lambda: True)

        def fake_run(cmd, cwd, **kwargs):
            (__import__("pathlib").Path(cwd) / cmd[-1]).with_suffix(".pdf").write_bytes(b"%PDF")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(compile_mod.subprocess, "run", fake_run)
        compile_mod.compile_manuscript(m)
        assert m.revisions.filter(label="").exists()

    def test_list_and_label_endpoints(self, client_logged_in):
        m = ManuscriptFactory(latex_source="content here")
        labeled = client_logged_in.post(
            f"/projects/{m.project.slug}/writing/{m.pk}/revisions/", {"label": "draft 1"}
        )
        assert labeled.status_code == 201
        listing = client_logged_in.get(
            f"/projects/{m.project.slug}/writing/{m.pk}/revisions/"
        ).json()
        assert listing["revisions"][0]["label"] == "draft 1"

    def test_diff_endpoint(self, client_logged_in):
        from writing.models import snapshot_manuscript

        m = ManuscriptFactory(latex_source="original line")
        rev = snapshot_manuscript(m, label="before")
        main = m.main_file
        main.content = "changed line"
        main.save()
        data = client_logged_in.get(
            f"/projects/{m.project.slug}/writing/{m.pk}/revisions/{rev.pk}/diff/"
        ).json()
        assert not data["unchanged"]
        assert any("changed line" in d["diff"] for d in data["diffs"])

    def test_restore_endpoint(self, client_logged_in):
        from writing.models import snapshot_manuscript

        m = ManuscriptFactory(latex_source="version A")
        rev = snapshot_manuscript(m, label="A")
        main = m.main_file
        main.content = "version B"
        main.save()
        res = client_logged_in.post(
            f"/projects/{m.project.slug}/writing/{m.pk}/revisions/{rev.pk}/restore/"
        )
        assert res.json()["restored"] is True
        m.refresh_from_db()
        assert m.main_file.content == "version A"
        # the restore itself snapshotted the pre-restore state
        assert m.revisions.filter(label="Before restore").exists()


class TestCiteLibrary:
    """Beyond-Overleaf B1: \\cite{} completes from the whole project library + auto-link."""

    def _setup(self):
        from literature.tests.factories import ProjectReferenceFactory
        from writing.tests.factories import ManuscriptFactory

        m = ManuscriptFactory(latex_source="x")
        # two references in the project library, neither linked to the manuscript yet
        pr1 = ProjectReferenceFactory(project=m.project)
        pr2 = ProjectReferenceFactory(project=m.project)
        return m, pr1.reference, pr2.reference

    def test_lists_project_library_with_linked_flag(self, client_logged_in):
        from writing.models import ManuscriptReference

        m, ref1, ref2 = self._setup()
        ManuscriptReference.objects.create(manuscript=m, reference=ref1)
        data = client_logged_in.get(
            f"/projects/{m.project.slug}/writing/{m.pk}/cite-library/"
        ).json()
        by_key = {c["key"]: c for c in data["candidates"]}
        assert by_key[ref1.bibtex_key]["linked"] is True
        assert by_key[ref2.bibtex_key]["linked"] is False
        assert "title" in by_key[ref2.bibtex_key]

    def test_post_auto_links_reference(self, client_logged_in):
        from writing.models import ManuscriptReference

        m, ref1, ref2 = self._setup()
        assert not ManuscriptReference.objects.filter(manuscript=m, reference=ref2).exists()
        res = client_logged_in.post(
            f"/projects/{m.project.slug}/writing/{m.pk}/cite-library/",
            {"reference": ref2.pk},
        )
        assert res.status_code == 201
        assert res.json()["key"] == ref2.bibtex_key
        assert ManuscriptReference.objects.filter(manuscript=m, reference=ref2).exists()

    def test_cannot_link_reference_outside_project(self, client_logged_in):
        from literature.tests.factories import ReferenceFactory

        m, _, _ = self._setup()
        stranger = ReferenceFactory()  # not in this project's library
        res = client_logged_in.post(
            f"/projects/{m.project.slug}/writing/{m.pk}/cite-library/",
            {"reference": stranger.pk},
        )
        assert res.status_code == 404


class TestWritingContext:
    """Beyond-Overleaf B3: research side panel context — bib, notes, hypotheses."""

    def test_context_returns_bib_notes_hypotheses(self, client_logged_in):
        from literature.tests.factories import ReferenceFactory
        from notes.models import Note
        from research.models import Hypothesis
        from writing.models import ManuscriptReference
        from writing.tests.factories import ManuscriptFactory

        m = ManuscriptFactory(latex_source="x")
        ref = ReferenceFactory(bibtex_key="panel2020key", year=2020)
        ManuscriptReference.objects.create(manuscript=m, reference=ref)
        Note.objects.create(project=m.project, title="Method note")
        Hypothesis.objects.create(project=m.project, statement="Load degrades vigilance")
        data = client_logged_in.get(f"/projects/{m.project.slug}/writing/{m.pk}/context/").json()
        assert data["bib"][0]["key"] == "panel2020key"
        assert data["bib"][0]["year"] == 2020
        assert {n["title"] for n in data["notes"]} == {"Method note"}
        assert data["hypotheses"][0]["statement"].startswith("Load degrades")

    def test_context_notes_filter(self, client_logged_in):
        from notes.models import Note
        from writing.tests.factories import ManuscriptFactory

        m = ManuscriptFactory(latex_source="x")
        Note.objects.create(project=m.project, title="Pupillometry rig")
        Note.objects.create(project=m.project, title="Unrelated")
        data = client_logged_in.get(
            f"/projects/{m.project.slug}/writing/{m.pk}/context/?q=pupil"
        ).json()
        assert {n["title"] for n in data["notes"]} == {"Pupillometry rig"}


class TestApiWordCount:
    """B4 prerequisite: word count exposed in DRF for the MCP latex_word_count tool."""

    def test_word_count_action_returns_counts(self, client_logged_in):
        from writing.models import ManuscriptFile
        from writing.tests.factories import ManuscriptFactory

        m = ManuscriptFactory(latex_source="")
        ManuscriptFile.objects.create(
            manuscript=m, path="main.tex", content="\\section{X}\none two three", is_main=True
        )
        data = client_logged_in.get(f"/api/v1/manuscripts/{m.pk}/word-count/").json()
        assert data["headers"] == 1
        assert data["words"] == 4  # "X" + one two three
