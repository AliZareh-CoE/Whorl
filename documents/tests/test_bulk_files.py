"""#556: act on a selection — move / tag / delete many files at once (one service behind the
explorer's action bar, the API and the classic Documents page), and a zip of a selection
or of a whole folder. Found first: the classic bulk move never recomputed `rel_path`."""

import io
import zipfile
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile

from documents import bulk
from documents.models import Document, Folder, Tag
from projects.tests.factories import ProjectFactory
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db

BASE = Path(settings.BASE_DIR)
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _doc(project, name, folder=None, body=b"x", content=""):
    return Document.objects.create(
        project=project,
        folder=folder,
        title=name,
        rel_path=f"{bulk.folder_path(folder)}/{name}" if folder else name,
        kind="other",
        file=ContentFile(body, name=name) if body is not None else None,
        content=content,
        content_type="text/plain",
    )


class TestIds:
    def test_clean_ids(self):
        assert bulk.clean_ids("3,1,3,,0,-2") == [3, 1]
        assert bulk.clean_ids([2, "5"]) == [2, 5]
        assert bulk.clean_ids("") == []
        with pytest.raises(bulk.BulkError):
            bulk.clean_ids("a,b")
        with pytest.raises(bulk.BulkError):
            bulk.clean_ids({"x": 1})
        with pytest.raises(bulk.BulkError):
            bulk.clean_ids(list(range(1, bulk.MAX_IDS + 2)))


class TestService:
    def test_move_recomputes_rel_path_and_skips_manuscript_sources(self):
        project = ProjectFactory()
        data = Folder.objects.create(project=project, name="Data")
        pilot = Folder.objects.create(project=project, name="Pilot", parent=data)
        a = _doc(project, "a.csv")
        b = _doc(project, "b.csv", data)
        m = ManuscriptFactory(project=project)
        m.files.create(path="main.tex", content="x", kind="tex", is_main=True)
        source = project.documents.get(role="manuscript_source")
        out = bulk.bulk_documents(project, [a.pk, b.pk, source.pk], "move", folder=pilot)
        assert out == {"action": "move", "count": 2, "skipped": [source.pk]}
        a.refresh_from_db()
        b.refresh_from_db()
        assert a.rel_path == "Data/Pilot/a.csv" and b.rel_path == "Data/Pilot/b.csv"
        source.refresh_from_db()
        assert source.rel_path.startswith("manuscript-")
        bulk.bulk_documents(project, [a.pk], "move", folder=None)
        a.refresh_from_db()
        assert a.rel_path == "a.csv" and a.folder_id is None

    def test_tag_and_delete(self):
        project = ProjectFactory()
        tag = Tag.objects.create(project=project, name="key")
        a, b = _doc(project, "a.md"), _doc(project, "b.md")
        out = bulk.bulk_documents(project, [a.pk, b.pk], "tag", tag=tag)
        assert out["count"] == 2 and list(a.tags.all()) == [tag]
        bulk.bulk_documents(project, [a.pk], "tag", tag=tag)  # idempotent
        assert a.tags.count() == 1
        out = bulk.bulk_documents(project, [a.pk, b.pk, 999_999], "delete")
        assert out["count"] == 2 and not project.documents.exists()

    def test_foreign_folder_tag_and_unknown_action(self):
        project, other = ProjectFactory(), ProjectFactory()
        a = _doc(project, "a.md")
        with pytest.raises(bulk.BulkError):
            bulk.bulk_documents(
                project, [a.pk], "move", folder=Folder.objects.create(project=other, name="X")
            )
        with pytest.raises(bulk.BulkError):
            bulk.bulk_documents(
                project, [a.pk], "tag", tag=Tag.objects.create(project=other, name="t")
            )
        with pytest.raises(bulk.BulkError):
            bulk.bulk_documents(project, [a.pk], "tag")
        with pytest.raises(bulk.BulkError):
            bulk.bulk_documents(project, [a.pk], "rename")


class TestArchive:
    def test_folder_members_are_relative_and_a_selection_keeps_project_paths(self):
        project = ProjectFactory()
        data = Folder.objects.create(project=project, name="Data")
        pilot = Folder.objects.create(project=project, name="Pilot", parent=data)
        top = _doc(project, "readme.md", body=b"# top")
        _doc(project, "rt.csv", pilot, body=b"a,b")
        note = _doc(project, "note.md", data, body=None, content="inline text")
        spool, name, count = bulk.build_archive(project, folder=data)
        assert name == f"{project.slug}-Data.zip" and count == 2
        with zipfile.ZipFile(spool) as zf:
            assert sorted(zf.namelist()) == ["Pilot/rt.csv", "note.md"]
            assert zf.read("note.md") == b"inline text"
        spool, name, count = bulk.build_archive(project, ids=[top.pk, note.pk])
        assert name == f"{project.slug}-files.zip" and count == 2
        with zipfile.ZipFile(spool) as zf:
            assert sorted(zf.namelist()) == ["Data/note.md", "readme.md"]

    def test_unsafe_and_duplicate_member_names(self):
        project = ProjectFactory()
        a = _doc(project, "same.txt", body=b"1")
        b = _doc(project, "same.txt", body=b"2")
        c = Document.objects.create(
            project=project, title="../../etc/passwd", rel_path="", kind="other", content="x"
        )
        spool, _, count = bulk.build_archive(project, ids=[a.pk, b.pk, c.pk])
        with zipfile.ZipFile(spool) as zf:
            names = zf.namelist()
        assert count == 3 and "same.txt" in names and "same (2).txt" in names
        assert all(".." not in n and not n.startswith("/") for n in names)

    def test_size_cap(self, monkeypatch):
        project = ProjectFactory()
        a = _doc(project, "big.bin", body=b"x" * 100)
        monkeypatch.setattr(bulk, "ARCHIVE_CAP", 50)
        with pytest.raises(bulk.BulkError, match="MB"):
            bulk.build_archive(project, ids=[a.pk])


class TestApi:
    def test_bulk_endpoint(self, client):
        project = ProjectFactory()
        folder = Folder.objects.create(project=project, name="Out")
        tag = Tag.objects.create(project=project, name="t")
        a, b = _doc(project, "a.md"), _doc(project, "b.md")
        url = f"/api/v1/projects/{project.slug}/documents/bulk/"
        resp = client.post(
            url,
            {"ids": [a.pk, b.pk], "action": "move", "folder": folder.pk},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 200 and resp.json() == {
            "action": "move",
            "count": 2,
            "skipped": [],
        }
        a.refresh_from_db()
        assert a.rel_path == "Out/a.md"
        resp = client.post(
            url,
            {"ids": [a.pk], "action": "tag", "tag": tag.pk},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 200 and a.tags.count() == 1
        assert (
            client.post(
                url,
                {"ids": [a.pk], "action": "tag", "tag": 999_999},
                content_type="application/json",
                **HEADERS,
            ).status_code
            == 404
        )
        assert (
            client.post(
                url,
                {"ids": [a.pk], "action": "move", "folder": "junk"},
                content_type="application/json",
                **HEADERS,
            ).status_code
            == 404
        )
        assert (
            client.post(
                url, {"ids": "x", "action": "delete"}, content_type="application/json", **HEADERS
            ).status_code
            == 400
        )
        assert (
            client.post(
                url, {"ids": [a.pk], "action": "nope"}, content_type="application/json", **HEADERS
            ).status_code
            == 400
        )
        resp = client.post(
            url,
            {"ids": [a.pk, b.pk], "action": "delete"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.json()["count"] == 2 and not project.documents.exists()
        assert (
            client.post(
                url, {"ids": [1], "action": "delete"}, content_type="application/json"
            ).status_code
            == 401
        )

    def test_archive_endpoint(self, client):
        project = ProjectFactory()
        data = Folder.objects.create(project=project, name="Data")
        a = _doc(project, "a.csv", data, body=b"1,2")
        b = _doc(project, "b.md", body=b"# b")
        resp = client.get(f"/api/v1/projects/{project.slug}/archive/?folder={data.pk}", **HEADERS)
        assert resp.status_code == 200 and resp["Content-Type"] == "application/zip"
        assert (
            resp["X-Atlas-Archive-Files"] == "1"
            and f"{project.slug}-Data.zip" in resp["Content-Disposition"]
        )
        with zipfile.ZipFile(io.BytesIO(b"".join(resp.streaming_content))) as zf:
            assert zf.namelist() == ["a.csv"]
        resp = client.get(
            f"/api/v1/projects/{project.slug}/archive/?ids={a.pk},{b.pk},999999", **HEADERS
        )
        with zipfile.ZipFile(io.BytesIO(b"".join(resp.streaming_content))) as zf:
            assert sorted(zf.namelist()) == ["Data/a.csv", "b.md"]
        assert client.get(f"/api/v1/projects/{project.slug}/archive/", **HEADERS).status_code == 400
        assert (
            client.get(f"/api/v1/projects/{project.slug}/archive/?ids=abc", **HEADERS).status_code
            == 400
        )
        assert (
            client.get(
                f"/api/v1/projects/{project.slug}/archive/?folder=999999", **HEADERS
            ).status_code
            == 404
        )
        assert client.get(f"/api/v1/projects/{project.slug}/archive/?ids={a.pk}").status_code == 401

    def test_archive_size_cap_is_413(self, client, monkeypatch):
        project = ProjectFactory()
        a = _doc(project, "big.bin", body=b"x" * 100)
        monkeypatch.setattr(bulk, "ARCHIVE_CAP", 50)
        resp = client.get(f"/api/v1/projects/{project.slug}/archive/?ids={a.pk}", **HEADERS)
        assert resp.status_code == 413 and "MB" in resp.json()["detail"]

    def test_classic_bulk_move_now_keeps_rel_path(self, client, owner):
        project = ProjectFactory()
        folder = Folder.objects.create(project=project, name="Out")
        a = _doc(project, "a.md")
        client.force_login(owner)
        resp = client.post(
            f"/projects/{project.slug}/documents/bulk/",
            {"ids": [a.pk], "action": "move", "folder": folder.pk},
            HTTP_X_SPA="1",
        )
        assert resp.status_code == 200
        a.refresh_from_db()
        assert a.folder_id == folder.pk and a.rel_path == "Out/a.md"


def test_explorer_selection_and_action_bar():
    files = (BASE / "frontend" / "src" / "app" / "pages" / "Files.tsx").read_text()
    assert "const [checked, setChecked] = useState<Set<number>>(() => new Set());" in files
    # a checkbox per row (hover-revealed until something is checked; always on a phone)
    assert 'data-testid="file-check"' in files and "toggleCheck(f, e.shiftKey)" in files
    assert "opacity-0 group-hover:opacity-100 focus:opacity-100 pointer-coarse:opacity-100" in files
    # shift-click extends over the visible rows from the anchor; space / ⌘A / Esc on the tree
    assert 'for (const r of flat.slice(a, b + 1)) if (r.kind === "file") n.add(r.id);' in files
    assert (
        'if (e.key === " " && r?.kind === "file") { e.preventDefault(); toggleCheck(r.file, false); return; }'
        in files
    )
    assert '(e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a"' in files
    assert (
        'if (e.key === "Escape" && checked.size) { e.preventDefault(); setChecked(new Set()); return; }'
        in files
    )
    # the selection is pruned to what the tree shows (a tag filter, a refetch)
    assert "const kept = new Set([...c].filter((id) => shownIds.has(id)));" in files
    # the bar and its verbs; one endpoint; manuscript sources reported
    for needle in (
        "bulk-bar",
        "bulk-count",
        "bulk-zip",
        "bulk-move",
        "bulk-tag",
        "bulk-delete",
        "bulk-clear",
    ):
        assert f'data-testid="{needle}"' in files, needle
    assert (
        "`/projects/${slug}/documents/bulk/`" in files
        and "body: JSON.stringify({ ids: [...checked], ...v })" in files
    )
    assert "if (r.skipped.length) void noticeDialog(" in files
    assert '`/api/v1/projects/${slug}/archive/?ids=${[...checked].join(",")}`' in files
    assert (
        '{ label: "Download as zip", icon: <Archive className="h-3.5 w-3.5" />, onSelect: () => downloadUrl(`/api/v1/projects/${slug}/archive/?folder=${f.id}`) }'
        in files
    )
    # the hooks sit above the early return
    main = files.split("export default function Files()", 1)[1]
    assert main.index("const [checked, setChecked]") < main.index("if (isLoading)\n    return (")
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "bulk-bar" in chunks and "file-check" in chunks and "/archive/?folder=" in chunks
