"""#553: file history — a general document's earlier states survive every overwrite path
(replace, in-place edit, API / MCP write, restore), a same-name upload is never a silent
duplicate, and manuscript sources are refused everywhere."""

from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from documents import history
from documents.models import Document, DocumentVersion
from mcp_server import client as mcp_client
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
BASE = Path(settings.BASE_DIR)


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _csv(project, body=b"a,b\n1,2\n", name="data.csv", **kw):
    return Document.objects.create(
        project=project,
        title=name,
        rel_path=name,
        kind="other",
        file=ContentFile(body, name=name),
        content_type="text/csv",
        **kw,
    )


class TestService:
    def test_replace_files_the_old_bytes_and_bumps_the_version(self):
        doc = _csv(ProjectFactory())
        out = history.replace_file(
            doc, SimpleUploadedFile("x.csv", b"a,b\n9,9\n", "text/csv"), note="fixed"
        )
        doc.refresh_from_db()
        assert out == {"version": 2, "filed": 1, "size": 8} and doc.version == 2
        assert doc.file.read() == b"a,b\n9,9\n" and doc.rel_path == "data.csv"
        v1 = doc.versions.get()
        assert v1.number == 1 and v1.file.read() == b"a,b\n1,2\n" and v1.note == "fixed"
        assert v1.source == "upload" and v1.file_size == 8 and v1.content_type == "text/csv"
        assert v1.file.name.startswith(f"projects/{doc.project.slug}/versions/{doc.id}/v1-")

    def test_replace_content_skips_unchanged_text(self):
        doc = _csv(ProjectFactory())
        assert history.replace_content(doc, "a,b\n1,2\n", source="edit") is None
        assert doc.versions.count() == 0 and doc.version == 1
        assert history.replace_content(doc, "a,b\n3,3\n", source="write", note="n") == {
            "version": 2,
            "filed": 1,
        }
        doc.refresh_from_db()
        assert history.current_text(doc) == "a,b\n3,3\n" and doc.versions.get().source == "write"

    def test_inline_text_node_versions_carry_content_not_a_file(self):
        doc = Document.objects.create(
            project=ProjectFactory(),
            title="notes.md",
            rel_path="notes.md",
            kind="other",
            content="one",
        )
        history.replace_content(doc, "two", source="edit")
        v = doc.versions.get()
        assert v.content == "one" and not v.file and v.file_size == 3
        assert history.version_text(v) == "one"

    def test_restore_files_the_current_state_first(self):
        doc = _csv(ProjectFactory())
        history.replace_file(doc, SimpleUploadedFile("x.csv", b"v2", "text/csv"))
        out = history.restore(doc, doc.versions.get(number=1))
        doc.refresh_from_db()
        assert out == {"version": 3, "restored": 1, "filed": 2} and doc.file.read() == b"a,b\n1,2\n"
        assert [(v.number, v.source) for v in doc.versions.order_by("number")] == [
            (1, "upload"),
            (2, "restore"),
        ]
        assert doc.versions.get(number=2).file.read() == b"v2"

    def test_only_the_last_keep_versions_survive(self):
        doc = _csv(ProjectFactory())
        for i in range(history.KEEP + 3):
            history.replace_content(doc, f"a,b\n{i},{i}\n", source="edit")
        numbers = list(doc.versions.order_by("number").values_list("number", flat=True))
        assert len(numbers) == history.KEEP and numbers[0] == 4 and numbers[-1] == history.KEEP + 3

    def test_manuscript_sources_are_refused(self):
        doc = Document.objects.create(
            project=ProjectFactory(),
            title="main.tex",
            rel_path="manuscript-1/main.tex",
            role=Document.Role.MANUSCRIPT_SOURCE,
            kind="tex",
            content="x",
        )
        with pytest.raises(history.HistoryError):
            history.replace_content(doc, "y", source="edit")
        assert DocumentVersion.objects.count() == 0

    def test_restore_refuses_another_files_version(self):
        p = ProjectFactory()
        a, b = _csv(p, name="a.csv"), _csv(p, name="b.csv")
        history.replace_file(a, SimpleUploadedFile("a.csv", b"2", "text/csv"))
        with pytest.raises(history.HistoryError):
            history.restore(b, a.versions.get())


class TestApi:
    def test_same_name_upload_keeps_both_by_default_and_replaces_on_request(self, client):
        p = ProjectFactory()
        url = f"/api/v1/projects/{p.slug}/upload-file/"
        r = client.post(url, {"files": SimpleUploadedFile("d.csv", b"1", "text/csv")}, **HEADERS)
        assert r.status_code == 201 and r.json()["created"] == ["d.csv"]
        r = client.post(url, {"files": SimpleUploadedFile("d.csv", b"2", "text/csv")}, **HEADERS)
        assert r.json()["created"] == ["d-2.csv"] and r.json()["renamed"] == ["d-2.csv"]
        r = client.post(url, {"files": SimpleUploadedFile("d.csv", b"3", "text/csv")}, **HEADERS)
        assert r.json()["created"] == ["d-3.csv"]
        first = p.documents.get(rel_path="d.csv")
        r = client.post(
            url,
            {
                "files": SimpleUploadedFile("d.csv", b"4", "text/csv"),
                "on_conflict": "replace",
                "note": "again",
            },
            **HEADERS,
        )
        assert r.json()["replaced"] == [{"id": first.id, "name": "d.csv", "version": 2}]
        first.refresh_from_db()
        assert first.file.read() == b"4" and first.versions.get().note == "again"
        assert p.documents.count() == 3  # never a fourth node for the same path
        r = client.post(
            url, {"files": SimpleUploadedFile("d.csv", b"5"), "on_conflict": "junk"}, **HEADERS
        )
        assert r.status_code == 400

    def test_replace_versions_raw_and_restore(self, client):
        doc = _csv(ProjectFactory())
        r = client.post(
            f"/api/v1/documents/{doc.id}/replace/",
            {"file": SimpleUploadedFile("new.csv", b"a,b\n9,9\n", "text/csv"), "note": "fixed"},
            **HEADERS,
        )
        assert r.status_code == 200 and r.json() == {
            "id": doc.id,
            "version": 2,
            "filed": 1,
            "size": 8,
        }
        rows = client.get(f"/api/v1/documents/{doc.id}/versions/", **HEADERS).json()
        assert rows["version"] == 2 and [v["number"] for v in rows["versions"]] == [1]
        assert rows["versions"][0]["note"] == "fixed" and rows["versions"][0]["is_text"]
        r = client.get(f"/api/v1/documents/{doc.id}/content/?version=1", **HEADERS)
        assert r.json()["content"] == "a,b\n1,2\n" and r.json()["version"] == 1
        assert client.get(f"/api/v1/documents/{doc.id}/content/", **HEADERS).json()["version"] == 2
        r = client.get(f"/api/v1/documents/{doc.id}/versions/1/raw/", **HEADERS)
        assert (
            r.status_code == 200
            and r["Content-Disposition"] == 'attachment; filename="v1-data.csv"'
        )
        assert b"".join(r.streaming_content) == b"a,b\n1,2\n" and r.has_header("ETag")
        r = client.post(f"/api/v1/documents/{doc.id}/versions/1/restore/", **HEADERS)
        assert r.json() == {"id": doc.id, "version": 3, "restored": 1, "filed": 2}
        doc.refresh_from_db()
        assert doc.file.read() == b"a,b\n1,2\n"
        for path in ("versions/9/raw/", "versions/0/restore/", "content/?version=9"):
            r = (
                client.get(f"/api/v1/documents/{doc.id}/{path}", **HEADERS)
                if "restore" not in path
                else client.post(f"/api/v1/documents/{doc.id}/{path}", **HEADERS)
            )
            assert r.status_code == 404, path
        assert client.post(f"/api/v1/documents/{doc.id}/replace/", {}, **HEADERS).status_code == 400
        assert client.get(f"/api/v1/documents/{doc.id}/", **HEADERS).json()["version"] == 3
        r = client.patch(
            f"/api/v1/documents/{doc.id}/",
            {"version": 99},
            content_type="application/json",
            **HEADERS,
        )
        assert r.json()["version"] == 3  # read-only

    def test_edit_and_write_file_record_versions_and_the_tree_counts_them(self, client):
        p = ProjectFactory()
        doc = _csv(p)
        r = client.put(
            f"/api/v1/documents/{doc.id}/content/",
            {"content": "a,b\n2,2\n", "note": "typo"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.json() == {"id": doc.id, "saved": True, "version": 2}
        r = client.post(
            f"/api/v1/projects/{p.slug}/write-file/",
            {"path": "data.csv", "content": "a,b\n3,3\n", "note": "from Claude"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 200
        r = client.post(
            f"/api/v1/projects/{p.slug}/write-file/",
            {"path": "data.csv", "content": "a,b\n3,3\n"},
            content_type="application/json",
            **HEADERS,
        )
        assert r.status_code == 200  # unchanged: nothing filed
        assert [(v.number, v.source, v.note) for v in doc.versions.order_by("number")] == [
            (1, "edit", "typo"),
            (2, "write", "from Claude"),
        ]
        row = next(
            f
            for f in client.get(f"/api/v1/projects/{p.slug}/tree/", **HEADERS).json()["files"]
            if f["id"] == doc.id
        )
        assert row["version"] == 3 and row["versions"] == 2

    def test_manuscript_source_refused_over_the_api(self, client):
        doc = Document.objects.create(
            project=ProjectFactory(),
            title="main.tex",
            rel_path="manuscript-1/main.tex",
            role=Document.Role.MANUSCRIPT_SOURCE,
            kind="tex",
            content="x",
        )
        r = client.post(
            f"/api/v1/documents/{doc.id}/replace/",
            {"file": SimpleUploadedFile("main.tex", b"y", "text/plain")},
            **HEADERS,
        )
        assert r.status_code == 403


def test_mcp_client_carries_version_and_note(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mcp_client, "_request", lambda method, path, **kw: seen.update(kw, path=path) or {}
    )
    mcp_client.read_project_file(4)
    assert seen["path"] == "/documents/4/content/" and seen["params"] is None
    mcp_client.read_project_file(4, version=2)
    assert seen["params"] == {"version": 2}
    mcp_client.write_project_file("p", "a.md", "x", note="why")
    assert seen["json"] == {"path": "a.md", "content": "x", "note": "why"}
    mcp_client.write_project_file("p", "a.md", "x")
    assert seen["json"] == {"path": "a.md", "content": "x"}


def test_ui_wiring():
    files = (BASE / "frontend" / "src" / "app" / "pages" / "Files.tsx").read_text()
    for needle in (
        "function HistoryPanel(",
        'data-testid="file-history"',
        'data-testid="file-version"',
        'data-testid="restore-version"',
        'data-testid="replace-file"',
        'data-testid="replace-picker"',
        'data-testid="history-toggle"',
        'data-testid="version-chip"',
        'data-testid="version-line"',
        '"Replace with a newer version…"',
        'fd.append("on_conflict", onConflict);',
        'confirmLabel: "Replace (keeps history)", cancelLabel: "Keep both"',
        "/versions/${v.number}/raw/",
        "/versions/${n}/restore/",
    ):
        assert needle in files, needle
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "file-history" in chunks and "restore-version" in chunks and "on_conflict" in chunks
