"""Frozen contract for the manuscript-files surface (file-workspace epic, slice 1c).

These tests pin the EXACT request/response shapes that the unified-tree flip (slice
1c-ii: ManuscriptFile rows become Documents under the manuscript's root_folder) must
preserve byte-for-byte. They pass today against the ManuscriptFile-backed
implementation; keeping them green through the flip proves the API and the six MCP
file tools (which consume this API over the X-API-Key path) see no difference.
"""

import pytest
from django.utils import timezone

from projects.tests.factories import ProjectFactory
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}

FILE_FIELDS = {
    "id",
    "manuscript",
    "path",
    "kind",
    "content",
    "asset",
    "is_main",
    "created_at",
    "updated_at",
}
SUMMARY_FIELDS = {"id", "path", "kind", "is_main"}


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    # owner: API-key auth resolves to the superuser, which must exist
    settings.ATLAS_API_KEY = KEY


def _manuscript_with_tree():
    project = ProjectFactory()
    m = ManuscriptFactory(project=project, latex_source="\\documentclass{article}\\n")
    main = m.ensure_main_file()  # main.tex from the alias
    m.files.create(path="refs.bib", content="@article{x,title={t}}")
    m.files.create(path="sections/intro.tex", content="intro")
    return m, main


class TestManuscriptFilesContract:
    def test_list_shape_via_api_key(self, client):
        m, _ = _manuscript_with_tree()
        rows = client.get(f"/api/v1/manuscript-files/?manuscript={m.pk}", **HEADERS).json()
        rows = rows["results"] if isinstance(rows, dict) else rows
        assert len(rows) == 3
        for row in rows:
            assert set(row) == FILE_FIELDS
        paths = {r["path"] for r in rows}
        assert paths == {"main.tex", "refs.bib", "sections/intro.tex"}
        # paths are relative (no leading slash / manuscript prefix) — MCP depends on this
        assert all(not p.startswith("/") for p in paths)

    def test_kind_is_derived_and_read_only(self, client):
        m, _ = _manuscript_with_tree()
        rows = client.get(f"/api/v1/manuscript-files/?manuscript={m.pk}", **HEADERS).json()
        rows = rows["results"] if isinstance(rows, dict) else rows
        by_path = {r["path"]: r for r in rows}
        assert by_path["main.tex"]["kind"] == "tex"
        assert by_path["refs.bib"]["kind"] == "bib"
        # kind ignores client input (read-only, derived from path)
        created = client.post(
            "/api/v1/manuscript-files/",
            data={"manuscript": m.pk, "path": "fig.png", "kind": "tex"},
            content_type="application/json",
            **HEADERS,
        ).json()
        assert created["kind"] == "asset"

    def test_exactly_one_main_and_summary_shape(self, client):
        m, main = _manuscript_with_tree()
        detail = client.get(f"/api/v1/manuscripts/{m.pk}/", **HEADERS).json()
        files = detail["files"]
        for row in files:
            assert set(row) == SUMMARY_FIELDS
        mains = [f for f in files if f["is_main"]]
        assert len(mains) == 1 and mains[0]["path"] == "main.tex"

    def test_create_save_rename_delete_round_trip(self, client):
        m, _ = _manuscript_with_tree()
        # create
        created = client.post(
            "/api/v1/manuscript-files/",
            data={"manuscript": m.pk, "path": "sections/methods.tex", "content": "m"},
            content_type="application/json",
            **HEADERS,
        ).json()
        assert created["path"] == "sections/methods.tex" and created["kind"] == "tex"
        fid = created["id"]
        # save content
        client.patch(
            f"/api/v1/manuscript-files/{fid}/",
            data={"content": "methods body"},
            content_type="application/json",
            **HEADERS,
        )
        assert client.get(f"/api/v1/manuscript-files/{fid}/", **HEADERS).json()["content"] == (
            "methods body"
        )
        # rename
        client.patch(
            f"/api/v1/manuscript-files/{fid}/",
            data={"path": "sections/method.tex"},
            content_type="application/json",
            **HEADERS,
        )
        assert client.get(f"/api/v1/manuscript-files/{fid}/", **HEADERS).json()["path"] == (
            "sections/method.tex"
        )
        # delete
        assert client.delete(f"/api/v1/manuscript-files/{fid}/", **HEADERS).status_code == 204

    def test_traversal_rejected(self, client):
        m, _ = _manuscript_with_tree()
        resp = client.post(
            "/api/v1/manuscript-files/",
            data={"manuscript": m.pk, "path": "../escape.tex", "content": "x"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 400


class TestLatexSourceAliasContract:
    def test_alias_round_trips_through_main_file(self):
        m, _ = _manuscript_with_tree()
        m.latex_source = "\\documentclass{book}\n\\begin{document}new\\end{document}"
        m.save()
        assert m.main_file.content == m.latex_source
        # editing the main file is reflected by source_text()
        main = m.main_file
        main.content = "edited in workbench"
        main.save()
        assert m.source_text() == "edited in workbench"

    def test_status_only_save_preserves_main(self):
        m, _ = _manuscript_with_tree()
        original = m.main_file.content
        m.compile_status = m.CompileStatus.OK
        m.compiled_at = timezone.now()
        m.save(update_fields=["compile_status", "compiled_at", "updated_at"])
        assert m.main_file.content == original
