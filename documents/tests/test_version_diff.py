"""#555 (backlog 352): compare an earlier version with the file as it is now — a unified line
diff for any text file and, for a .csv / .tsv, the changed cells with rows aligned by content
and columns by header; GET /documents/{id}/versions/{n}/diff/; read_project_file(diff=True);
a Compare toggle per history row in the explorer."""

from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from documents import history
from documents.models import Document
from mcp_server import client as mcp_client
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

BASE = Path(settings.BASE_DIR)
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _file(project, name, body, content_type="text/plain"):
    return Document.objects.create(
        project=project,
        title=name,
        rel_path=name,
        kind="other",
        file=ContentFile(body, name=name),
        content_type=content_type,
    )


def _replace(doc, body, note=""):
    history.replace_file(doc, SimpleUploadedFile(doc.title, body, doc.content_type), note=note)
    doc.refresh_from_db()


class TestTableDiff:
    def test_changed_cell_and_a_row_removed_in_the_middle(self):
        then = "id,cond,rt\n1,low,412\n2,low,398\n7,high,1290\n"
        now = "id,cond,rt\n1,low,415\n7,high,1290\n"
        out = history.table_diff(then, now)
        assert out["changes"] == [{"row": 2, "column": "rt", "then": "412", "now": "415"}]
        assert out["rows_removed"] == 1 and out["rows_added"] == 0  # not "two rows changed"
        assert out["cols_added"] == [] and out["cols_removed"] == [] and not out["truncated"]

    def test_added_column_compares_the_shared_ones(self):
        then = "id,rt\n1,412\n2,398\n"
        now = "id,rt,note\n1,412,ok\n2,401,late\n"
        out = history.table_diff(then, now)
        assert out["cols_added"] == ["note"] and out["headers"] == ["id", "rt", "note"]
        assert out["changes"] == [{"row": 3, "column": "rt", "then": "398", "now": "401"}]

    def test_row_numbers_are_file_lines_past_a_blank_line(self):
        then = "id,rt\n1,412\n\n2,398\n"
        now = "id,rt\n1,412\n\n2,401\n"
        out = history.table_diff(then, now)
        assert out["changes"] == [{"row": 4, "column": "rt", "then": "398", "now": "401"}]

    def test_tsv_and_caps(self):
        out = history.table_diff("a\tb\n1\t2\n", "a\tb\n1\t3\n", "\t")
        assert out["changes"][0]["now"] == "3"
        rows = "\n".join(f"{i},x" for i in range(history.TABLE_CHANGES_CAP + 5))
        then = "id,v\n" + rows
        now = "id,v\n" + rows.replace(",x", ",y")
        out = history.table_diff(then, now)
        assert len(out["changes"]) == history.TABLE_CHANGES_CAP and out["truncated"]


class TestVersionDiff:
    def test_text_lines_and_same(self):
        doc = _file(ProjectFactory(), "notes.md", b"# T\nline one\nline two\n")
        _replace(doc, b"# T\nline one changed\nline two\nline three\n", note="edit")
        v1 = doc.versions.get(number=1)
        out = history.version_diff(doc, v1)
        assert out["is_text"] and not out["same"] and not out["too_large"]
        assert out["added"] == 2 and out["removed"] == 1 and out["table"] is None
        assert out["diff"].startswith("--- v1\n+++ v2 (now)\n") and "+line three" in out["diff"]
        assert out["version"] == 2 and out["number"] == 1 and out["note"] == "edit"
        _replace(doc, b"# T\nline one\nline two\n")  # back to the v1 bytes
        out = history.version_diff(doc, v1)
        assert out["same"] and out["diff"] == "" and out["added"] == 0

    def test_csv_gets_the_table_and_binary_does_not(self):
        project = ProjectFactory()
        csv = _file(project, "rt.csv", b"id,rt\n1,412\n", "text/csv")
        _replace(csv, b"id,rt\n1,415\n")
        out = history.version_diff(csv, csv.versions.get(number=1))
        assert out["table"]["changes"] == [{"row": 2, "column": "rt", "then": "412", "now": "415"}]
        png = _file(project, "fig.png", b"\x89PNG\x00\xff\xfe", "image/png")
        _replace(png, b"\x89PNG\x00\xff\xfd")
        out = history.version_diff(png, png.versions.get(number=1))
        assert out["is_text"] is False and out["diff"] == "" and out["table"] is None

    def test_too_large_is_not_diffed(self, monkeypatch):
        monkeypatch.setattr(history, "DIFF_CAP", 10)
        doc = _file(ProjectFactory(), "big.txt", b"x" * 20)
        _replace(doc, b"y" * 20)
        out = history.version_diff(doc, doc.versions.get(number=1))
        assert out["is_text"] and out["too_large"] and out["diff"] == ""

    def test_too_large_is_decided_from_the_stored_sizes_without_a_read(self, monkeypatch):
        monkeypatch.setattr(history, "DIFF_CAP", 10)
        doc = _file(ProjectFactory(), "big.txt", b"x" * 20)
        _replace(doc, b"y" * 20)
        monkeypatch.setattr(history, "current_text", lambda d: pytest.fail("read despite size"))
        out = history.version_diff(doc, doc.versions.get(number=1))
        assert out["too_large"] and out["is_text"]


class TestApi:
    def test_endpoint(self, client):
        doc = _file(ProjectFactory(), "rt.csv", b"id,rt\n1,412\n2,398\n", "text/csv")
        _replace(doc, b"id,rt\n1,412\n", note="dropped 2")
        resp = client.get(f"/api/v1/documents/{doc.id}/versions/1/diff/", **HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == doc.id and body["table"]["rows_removed"] == 1
        assert body["removed"] == 1 and body["note"] == "dropped 2" and body["version"] == 2
        assert (
            client.get(f"/api/v1/documents/{doc.id}/versions/9/diff/", **HEADERS).status_code == 404
        )
        assert (
            client.get(f"/api/v1/documents/{doc.id}/versions/0/diff/", **HEADERS).status_code == 404
        )
        assert client.get(f"/api/v1/documents/{doc.id}/versions/1/diff/").status_code == 401


def test_mcp_client_reads_the_diff(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mcp_client, "_request", lambda method, path, **kw: seen.update(kw, path=path) or {}
    )
    mcp_client.read_project_file(4, version=2, diff=True)
    assert seen["path"] == "/documents/4/versions/2/diff/" and "params" not in seen
    seen.clear()
    mcp_client.read_project_file(4, diff=True)  # no version: nothing to compare, plain read
    assert seen["path"] == "/documents/4/content/" and seen["params"] is None
    server = (BASE / "mcp_server" / "server.py").read_text()
    assert "def read_project_file(document_id: int, version: int = 0, diff: bool = False)" in server


def test_history_panel_compares_in_place():
    files = (BASE / "frontend" / "src" / "app" / "pages" / "Files.tsx").read_text()
    assert "function VersionDiff({ file, number }" in files
    assert (
        'queryKey: ["file-diff", file.id, number, file.version]' in files
    )  # a restore refreshes it
    assert (
        'data-testid="diff-version"' in files
        and '{compare === v.number ? "Hide" : "Compare"}' in files
    )
    assert (
        "(v.is_text || file.is_text) &&" in files
    )  # a .md uploaded as octet-stream still compares
    assert 'data-testid="version-diff"' in files and 'data-testid="cell-changes"' in files
    assert 'data-testid="line-diff"' in files
    assert "const [compare, setCompare] = useState<number | null>(null);" in files
    # the hooks sit above the panel's early returns
    panel = files.split("function HistoryPanel(", 1)[1]
    assert panel.index("useState<number | null>") < panel.index("if (isLoading)")
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "diff-version" in chunks and "cell-changes" in chunks
