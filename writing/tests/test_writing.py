import datetime
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from literature.tests.factories import ReferenceFactory
from writing import services
from writing.models import Manuscript, ManuscriptReference, SubmissionEvent

from .factories import ManuscriptFactory

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures"


class TestCiteParser:
    def test_parses_cite_variants_and_multiple_keys(self):
        tex = (
            r"\cite{a} \citep{b,c} \citet[p.~3]{d} \parencite{e} "
            r"\textcite{f} \autocite[see][p.2]{g} \cite*{h}"
        )
        assert services.parse_cite_keys(tex) == {"a", "b", "c", "d", "e", "f", "g", "h"}

    def test_ignores_non_cite_commands(self):
        assert services.parse_cite_keys(r"\ref{fig:one} \label{sec:two}") == set()


class TestCiteChecker:
    def make_manuscript_with_bib(self):
        manuscript = ManuscriptFactory()
        for key in ("lavie2010attention", "baddeley2003working", "neverused2001"):
            ManuscriptReference.objects.create(
                manuscript=manuscript, reference=ReferenceFactory(bibtex_key=key)
            )
        return manuscript

    def test_broken_tex_fixture_flagged_correctly(self):
        manuscript = self.make_manuscript_with_bib()
        tex = (FIXTURES / "broken.tex").read_text()
        result = services.check_citations(manuscript, tex)
        assert result["missing_from_bib"] == [
            "anotherghost2021",
            "ghostpaper1999",
            "missingkey2020",
        ]
        assert result["uncited_in_bib"] == ["neverused2001"]
        assert result["matched"] == ["baddeley2003working", "lavie2010attention"]

    def test_cite_key_override_used(self):
        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript,
            reference=ReferenceFactory(bibtex_key="original2000key"),
            cite_key_override="customkey",
        )
        result = services.check_citations(manuscript, r"\cite{customkey}")
        assert result["matched"] == ["customkey"]
        assert result["missing_from_bib"] == []

    def test_export_manuscript_bib_uses_override(self):
        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript,
            reference=ReferenceFactory(bibtex_key="original2000key"),
            cite_key_override="customkey",
        )
        bib = services.export_manuscript_bib(manuscript)
        assert "@article{customkey," in bib


class TestDeadlineLabel:
    @pytest.mark.parametrize(
        "delta_days, expected",
        [
            (None, None),
            (0, "due today"),
            (1, "1 day left"),  # correctly singular (#232-followup: was "1 days")
            (5, "5 days left"),
            (-1, "overdue by 1 day"),
            (-3, "overdue by 3 days"),
        ],
    )
    def test_deadline_label(self, delta_days, expected):
        deadline = (
            None
            if delta_days is None
            else timezone.localdate() + datetime.timedelta(days=delta_days)
        )
        m = ManuscriptFactory.build(deadline=deadline)
        assert m.deadline_label == expected

    def test_deadline_is_soon(self):
        soon = ManuscriptFactory.build(deadline=timezone.localdate() + datetime.timedelta(days=3))
        far = ManuscriptFactory.build(deadline=timezone.localdate() + datetime.timedelta(days=30))
        none = ManuscriptFactory.build(deadline=None)
        assert soon.deadline_is_soon and not far.deadline_is_soon and not none.deadline_is_soon


class TestManuscriptViews:
    def test_pipeline_board_groups_by_status(self, client_logged_in):
        project = ManuscriptFactory(status=Manuscript.Status.DRAFTING, title="Draft One").project
        ManuscriptFactory(project=project, status=Manuscript.Status.SUBMITTED, title="Sub One")
        response = client_logged_in.get(reverse("writing:project", args=[project.slug]))
        content = response.content.decode()
        assert "Drafting" in content and "Submitted" in content
        assert content.index("Draft One") < content.index("Sub One")

    def test_empty_board_offers_a_primary_action(self, client_logged_in):
        # product value: every empty state offers its primary action (#199 follow-on)
        from projects.tests.factories import ProjectFactory

        project = ProjectFactory()  # no manuscripts
        response = client_logged_in.get(reverse("writing:project", args=[project.slug]))
        content = response.content.decode()
        assert "Start a manuscript" in content
        assert reverse("writing:create", args=[project.slug]) in content

    def test_full_lifecycle_idea_to_published(self, client_logged_in):
        project = ManuscriptFactory(status=Manuscript.Status.IDEA).project
        manuscript = project.manuscripts.get()
        for kind, date in [
            ("submitted", "2026-01-10"),
            ("reviews_received", "2026-03-01"),
            ("revision_submitted", "2026-04-01"),
            ("accepted", "2026-05-01"),
            ("published", "2026-06-01"),
        ]:
            response = client_logged_in.post(
                reverse("writing:add_event", args=[project.slug, manuscript.pk]),
                {"kind": kind, "date": date, "notes": ""},
            )
            assert response.status_code == 302
        client_logged_in.post(
            reverse("writing:edit", args=[project.slug, manuscript.pk]),
            {
                "title": manuscript.title,
                "status": "published",
                "target_venue": "",
                "abstract": "",
                "repo_url": "",
            },
        )
        manuscript.refresh_from_db()
        assert manuscript.status == Manuscript.Status.PUBLISHED
        assert manuscript.events.count() == 5
        detail = client_logged_in.get(manuscript.get_absolute_url())
        assert b"Published" in detail.content
        assert b"Reviews received" in detail.content

    def test_cite_checker_via_view_with_fixture_upload(self, client_logged_in):
        from django.core.files.uploadedfile import SimpleUploadedFile

        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript, reference=ReferenceFactory(bibtex_key="lavie2010attention")
        )
        tex = (FIXTURES / "broken.tex").read_bytes()
        response = client_logged_in.post(
            manuscript.get_absolute_url(),
            {"tex_file": SimpleUploadedFile("paper.tex", tex, "text/x-tex")},
        )
        content = response.content.decode()
        assert "ghostpaper1999" in content
        assert "missingkey2020" in content

    def test_bib_export_download(self, client_logged_in):
        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript, reference=ReferenceFactory(bibtex_key="export2020me")
        )
        response = client_logged_in.get(
            reverse("writing:export_bib", args=[manuscript.project.slug, manuscript.pk])
        )
        assert response.status_code == 200
        assert b"export2020me" in response.content

    def test_deadline_countdown_on_overview(self, client_logged_in):
        manuscript = ManuscriptFactory(
            deadline=timezone.localdate() + datetime.timedelta(days=12),
            status=Manuscript.Status.DRAFTING,
        )
        response = client_logged_in.get(manuscript.project.get_absolute_url())
        assert b"12 days left" in response.content  # shared humanized label (#232-followup)

    def test_event_delete(self, client_logged_in):
        manuscript = ManuscriptFactory()
        event = SubmissionEvent.objects.create(
            manuscript=manuscript, kind="note", date="2026-01-01"
        )
        client_logged_in.post(
            reverse("writing:delete_event", args=[manuscript.project.slug, manuscript.pk, event.pk])
        )
        assert manuscript.events.count() == 0


class TestLatexEditor:
    def test_editor_renders_with_cite_keys(self, client_logged_in):
        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript, reference=ReferenceFactory(bibtex_key="editor2020key")
        )
        response = client_logged_in.get(
            reverse("writing:editor", args=[manuscript.project.slug, manuscript.pk])
        )
        content = response.content.decode()
        assert "latex-editor.js" in content  # the CM6 island module (no CDN editor)
        assert '"editor2020key"' in content

    def test_save_runs_cite_check(self, client_logged_in):
        manuscript = ManuscriptFactory()
        ManuscriptReference.objects.create(
            manuscript=manuscript, reference=ReferenceFactory(bibtex_key="editor2020key")
        )
        response = client_logged_in.post(
            reverse("writing:editor", args=[manuscript.project.slug, manuscript.pk]),
            {"latex_source": r"Intro \cite{editor2020key} and \cite{ghost2024}."},
        )
        manuscript.refresh_from_db()
        content = response.content.decode()
        assert "editor2020key" in manuscript.latex_source
        assert "ghost2024" in content  # flagged as missing from bib
        assert "✓ none" not in content.split("never cited")[0]  # missing column populated

    def test_editor_scoped_to_project(self, client_logged_in):
        from projects.tests.factories import ProjectFactory

        manuscript = ManuscriptFactory()
        other = ProjectFactory()
        response = client_logged_in.get(reverse("writing:editor", args=[other.slug, manuscript.pk]))
        assert response.status_code == 404


def test_editor_cite_keys_xss_safe(client_logged_in):
    """Audit #2: a hostile cite_key_override must not escape the JSON script block."""
    manuscript = ManuscriptFactory()
    ManuscriptReference.objects.create(
        manuscript=manuscript,
        reference=ReferenceFactory(bibtex_key="benign2020key"),
        cite_key_override="</script><script>alert(1)</script>",
    )
    response = client_logged_in.get(
        reverse("writing:editor", args=[manuscript.project.slug, manuscript.pk])
    )
    content = response.content.decode()
    assert "<script>alert(1)</script>" not in content
    assert "\\u003C/script" in content or "\\u003c/script" in content  # json_script escaping


class TestCompile:
    def make_manuscript(self, source=r"\documentclass{article}\begin{document}Hi\end{document}"):
        manuscript = ManuscriptFactory()
        manuscript.latex_source = source
        manuscript.save()
        return manuscript

    def test_compile_success_with_mocked_tectonic(self, monkeypatch, tmp_path):
        import subprocess as sp

        from writing import compile as compile_mod

        manuscript = self.make_manuscript()
        monkeypatch.setattr(compile_mod, "tectonic_available", lambda: True)

        def fake_run(cmd, cwd, **kwargs):
            (cwd / "main.pdf").write_bytes(b"%PDF-1.4 compiled")
            return sp.CompletedProcess(cmd, 0, stdout="note: ok", stderr="")

        monkeypatch.setattr(compile_mod.subprocess, "run", fake_run)
        compile_mod.compile_manuscript(manuscript)
        manuscript.refresh_from_db()
        assert manuscript.compile_status == "ok"
        assert manuscript.compiled_pdf.read().startswith(b"%PDF")
        assert manuscript.compiled_at is not None

    def test_compile_failure_keeps_log(self, monkeypatch):
        import subprocess as sp

        from writing import compile as compile_mod

        manuscript = self.make_manuscript(source=r"\badcommand")
        monkeypatch.setattr(compile_mod, "tectonic_available", lambda: True)
        monkeypatch.setattr(
            compile_mod.subprocess,
            "run",
            lambda cmd, cwd, **kw: sp.CompletedProcess(
                cmd, 1, stdout="", stderr="error: undefined"
            ),
        )
        compile_mod.compile_manuscript(manuscript)
        manuscript.refresh_from_db()
        assert manuscript.compile_status == "failed"
        assert "undefined" in manuscript.compile_log

    def test_empty_source_fails_cleanly(self):
        from writing.compile import compile_manuscript

        manuscript = ManuscriptFactory()
        compile_manuscript(manuscript)
        manuscript.refresh_from_db()
        assert manuscript.compile_status == "failed"
        assert "empty" in manuscript.compile_log

    def test_compile_view_saves_source_and_enqueues(self, client_logged_in, monkeypatch):
        manuscript = ManuscriptFactory()
        called = {}
        monkeypatch.setattr(
            "writing.tasks.compile_manuscript_task",
            lambda pk, gen=None: called.setdefault("pk", pk),
        )
        response = client_logged_in.post(
            reverse("writing:compile", args=[manuscript.project.slug, manuscript.pk]),
            {"latex_source": r"\documentclass{article}fresh"},
        )
        manuscript.refresh_from_db()
        assert response.status_code == 302
        assert "fresh" in manuscript.latex_source
        assert called["pk"] == manuscript.pk

    @pytest.mark.skipif(
        not __import__("pathlib").Path("bin/tectonic").exists(), reason="tectonic not vendored"
    )
    def test_real_tectonic_compiles_pdf(self):
        from writing.compile import compile_manuscript

        manuscript = self.make_manuscript(
            "\\documentclass{article}\n\\begin{document}\nReal compile.\n\\end{document}\n"
        )
        compile_manuscript(manuscript)
        manuscript.refresh_from_db()
        assert manuscript.compile_status == "ok", manuscript.compile_log
        assert manuscript.compiled_pdf.read().startswith(b"%PDF")


class TestEditorSplitView:
    def test_compile_status_endpoint(self, client_logged_in):
        manuscript = ManuscriptFactory()
        manuscript.compile_status = "failed"
        manuscript.compile_log = "error: undefined control sequence"
        manuscript.save()
        response = client_logged_in.get(
            reverse("writing:compile_status", args=[manuscript.project.slug, manuscript.pk])
        )
        data = response.json()
        assert data["status"] == "failed"
        assert "undefined" in data["log"]
        assert data["pdf_url"] is None

    def test_status_includes_pdf_url_when_compiled(self, client_logged_in):
        from django.core.files.base import ContentFile
        from django.utils import timezone

        manuscript = ManuscriptFactory()
        manuscript.compiled_pdf.save("m.pdf", ContentFile(b"%PDF-1.4"), save=False)
        manuscript.compile_status = "ok"
        manuscript.compiled_at = timezone.now()
        manuscript.save()
        data = client_logged_in.get(
            reverse("writing:compile_status", args=[manuscript.project.slug, manuscript.pk])
        ).json()
        assert data["status"] == "ok"
        assert data["pdf_url"].endswith(".pdf")
        assert data["log"] == ""

    def test_editor_has_preview_pane(self, client_logged_in):
        manuscript = ManuscriptFactory()
        response = client_logged_in.get(
            reverse("writing:editor", args=[manuscript.project.slug, manuscript.pk])
        )
        content = response.content.decode()
        assert 'id="preview-pane"' in content
        assert 'id="toggle-preview"' in content
        assert "compile/status/" in content


class TestCompileDiagnostics:
    """Owner idea #24 parity slice 1: parsed diagnostics + API compile surface."""

    def test_parser_handles_real_tectonic_output(self):
        from writing.log_parser import parse_compile_log

        log = (
            "error: main.tex:4: Undefined control sequence\n"
            "error: halted on potentially-recoverable error as specified\n"
        )
        diags = parse_compile_log(log)
        assert diags == [
            {
                "level": "error",
                "file": "main.tex",
                "line": 4,
                "message": "Undefined control sequence",
            }
        ]

    def test_parser_latex_warnings_and_bare_lines(self):
        from writing.log_parser import parse_compile_log

        log = (
            "LaTeX Warning: Reference `nolabel' on page 1 undefined on input line 3.\n"
            "warning: main.tex:9: Citation `nokey' undefined\n"
            "error: something engine-level went wrong\n"
        )
        diags = parse_compile_log(log)
        assert diags[0]["line"] == 3 and diags[0]["level"] == "warning"
        assert diags[1] == {
            "level": "warning",
            "file": "main.tex",
            "line": 9,
            "message": "Citation `nokey' undefined",
        }
        assert diags[2]["line"] is None and diags[2]["level"] == "error"

    def test_failed_compile_stores_diagnostics(self, monkeypatch):
        from types import SimpleNamespace

        from writing import compile as compile_mod
        from writing.tests.factories import ManuscriptFactory

        manuscript = ManuscriptFactory(latex_source="\\broken")
        monkeypatch.setattr(compile_mod, "tectonic_available", lambda: True)
        monkeypatch.setattr(
            compile_mod.subprocess,
            "run",
            lambda *a, **k: SimpleNamespace(
                returncode=1, stdout="error: main.tex:1: Undefined control sequence", stderr=""
            ),
        )
        compile_mod.compile_manuscript(manuscript)
        manuscript.refresh_from_db()
        assert manuscript.compile_status == "failed"
        assert manuscript.compile_diagnostics[0]["line"] == 1

    def test_api_exposes_source_and_compile(self, client_logged_in, monkeypatch):
        from writing.tests.factories import ManuscriptFactory

        manuscript = ManuscriptFactory(latex_source="")
        patched = client_logged_in.patch(
            f"/api/v1/manuscripts/{manuscript.pk}/",
            {"latex_source": "\\documentclass{article}"},
            content_type="application/json",
        )
        assert patched.status_code == 200
        manuscript.refresh_from_db()
        assert manuscript.latex_source.startswith("\\documentclass")

        called = {}
        monkeypatch.setattr(
            "writing.tasks.compile_manuscript_task",
            lambda pk, gen=None: called.setdefault("pk", pk),
        )
        queued = client_logged_in.post(f"/api/v1/manuscripts/{manuscript.pk}/compile/")
        assert queued.status_code == 202
        assert called["pk"] == manuscript.pk
        status_data = client_logged_in.get(
            f"/api/v1/manuscripts/{manuscript.pk}/compile-status/"
        ).json()
        assert status_data["status"] == "running"
        assert status_data["diagnostics"] == []

    def test_api_compile_empty_source_rejected(self, client_logged_in):
        from writing.tests.factories import ManuscriptFactory

        manuscript = ManuscriptFactory(latex_source="   ")
        response = client_logged_in.post(f"/api/v1/manuscripts/{manuscript.pk}/compile/")
        assert response.status_code == 400


class TestEpicSlice2:
    """Owner idea #24 slice 2: autosave JSON mode, in-place compile, stale-drop guard."""

    def test_autosave_returns_json_with_cite_counts(self, client_logged_in):
        from writing.tests.factories import ManuscriptFactory

        manuscript = ManuscriptFactory(latex_source="")
        url = f"/projects/{manuscript.project.slug}/writing/{manuscript.pk}/editor/"
        response = client_logged_in.post(
            url, {"latex_source": "\\cite{ghostkey}"}, headers={"X-SPA": "1"}
        )
        data = response.json()
        assert data["saved"] is True
        assert data["cite"]["missing_from_bib"] == 1
        manuscript.refresh_from_db()
        assert manuscript.latex_source == "\\cite{ghostkey}"

    def test_compile_spa_mode_returns_json_and_bumps_generation(
        self, client_logged_in, monkeypatch
    ):
        from writing.tests.factories import ManuscriptFactory

        manuscript = ManuscriptFactory(latex_source="x")
        seen = {}
        monkeypatch.setattr(
            "writing.tasks.compile_manuscript_task",
            lambda pk, gen=None: seen.update(pk=pk, gen=gen),
        )
        url = f"/projects/{manuscript.project.slug}/writing/{manuscript.pk}/compile/"
        response = client_logged_in.post(url, {"latex_source": "y"}, headers={"X-SPA": "1"})
        assert response.json() == {"status": "running"}
        manuscript.refresh_from_db()
        assert manuscript.compile_generation == 1
        assert seen == {"pk": manuscript.pk, "gen": 1}
        assert manuscript.latex_source == "y"

    def test_stale_compile_result_is_dropped(self, monkeypatch):
        from types import SimpleNamespace

        from writing import compile as compile_mod
        from writing.tests.factories import ManuscriptFactory

        manuscript = ManuscriptFactory(latex_source="x", compile_generation=2)
        monkeypatch.setattr(compile_mod, "tectonic_available", lambda: True)
        monkeypatch.setattr(
            compile_mod.subprocess,
            "run",
            lambda *a, **k: SimpleNamespace(returncode=1, stdout="error: nope", stderr=""),
        )
        # queued at generation 1, but generation 2 was queued since -> drop
        result = compile_mod.compile_manuscript(manuscript, generation=1)
        assert "skipped" in result
        manuscript.refresh_from_db()
        assert manuscript.compile_status != "failed"  # stale result never written
