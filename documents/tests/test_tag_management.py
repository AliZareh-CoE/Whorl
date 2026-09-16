"""#559 (backlog 354): tag management from the explorer — rename / recolour / merge / delete a
project's file tags over the API with the explorer's rules (a clash any-case names the tag,
a tag stays in its project, a merge moves every file), an AND filter on the documents list
and the tree, `list_project_files(tag)` + `manage_file_tag` in the MCP server."""

import json
from pathlib import Path

import pytest
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

from documents import tags as svc
from documents.models import Document, Tag
from documents.selectors import workspace_tree
from mcp_server import client as mcp_client
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

BASE = Path(settings.BASE_DIR)
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _doc(project, name, tags=()):
    doc = Document.objects.create(project=project, title=name, rel_path=name, kind="other")
    doc.tags.set(tags)
    return doc


def _tags(project):
    a = Tag.objects.create(project=project, name="key-paper", color="#dc2626")
    b = Tag.objects.create(project=project, name="protocol", color="#16a34a")
    return a, b


class TestService:
    def test_rename_refuses_a_clash_in_any_case_and_names_it(self):
        project = ProjectFactory()
        a, b = _tags(project)
        with pytest.raises(svc.TagError, match="“protocol” already exists"):
            svc.rename_tag(a, "Protocol")
        with pytest.raises(svc.TagError, match="Name the tag"):
            svc.rename_tag(a, "   ")
        assert svc.rename_tag(a, "  key   paper ").name == "key paper"
        # renaming to itself in another case is fine (not a clash with itself)
        assert svc.rename_tag(b, "Protocol").name == "Protocol"

    def test_recolour_validates_hex(self):
        project = ProjectFactory()
        a, _ = _tags(project)
        assert svc.recolour_tag(a, "#ABCDEF").color == "#abcdef"
        assert svc.recolour_tag(a, "").color == ""
        with pytest.raises(svc.TagError, match="#rrggbb"):
            svc.recolour_tag(a, "red")

    def test_merge_moves_every_file_and_is_idempotent_for_a_file_with_both(self):
        project = ProjectFactory()
        a, b = _tags(project)
        only_a = _doc(project, "a.md", [a])
        both = _doc(project, "ab.md", [a, b])
        _doc(project, "none.md")
        assert svc.merge_tags(a, b) == 2
        assert not Tag.objects.filter(pk=a.pk).exists()
        assert list(only_a.tags.values_list("name", flat=True)) == ["protocol"]
        assert list(both.tags.values_list("name", flat=True)) == ["protocol"]

    def test_merge_guards(self):
        project = ProjectFactory()
        a, b = _tags(project)
        other = Tag.objects.create(project=ProjectFactory(), name="x")
        with pytest.raises(svc.TagError, match="different tag"):
            svc.merge_tags(a, a)
        with pytest.raises(svc.TagError, match="one project"):
            svc.merge_tags(a, other)
        assert Tag.objects.filter(pk=a.pk).exists() and b.documents.count() == 0

    def test_delete_reports_the_files_it_was_on(self):
        project = ProjectFactory()
        a, b = _tags(project)
        doc = _doc(project, "a.md", [a, b])
        assert svc.delete_tag(a) == 1
        assert list(doc.tags.values_list("name", flat=True)) == ["protocol"]

    def test_tag_names_and_the_and_filter(self):
        project = ProjectFactory()
        a, b = _tags(project)
        _doc(project, "a.md", [a])
        both = _doc(project, "ab.md", [a, b])
        assert svc.tag_names(["", " key-paper ", "key-paper", "x" * 80]) == ["key-paper", "x" * 60]
        assert len(svc.tag_names([str(i) for i in range(20)])) == svc.MAX_FILTER_TAGS
        rows = svc.filter_by_tags(project.documents.all(), ["key-paper", "protocol"])
        assert [d.pk for d in rows] == [both.pk]
        assert svc.filter_by_tags(project.documents.all(), []).count() == 2
        tree = workspace_tree(project, ["key-paper", "protocol"])
        assert [f["name"] for f in tree["files"]] == ["ab.md"]


class TestApi:
    def test_list_carries_counts(self, client):
        project = ProjectFactory()
        a, b = _tags(project)
        _doc(project, "a.md", [a])
        _doc(project, "ab.md", [a, b])
        Tag.objects.create(project=project, name="a-first")
        rows = client.get(f"/api/v1/tags/?project={project.slug}", **HEADERS).json()["results"]
        assert {r["name"]: r["count"] for r in rows} == {
            "a-first": 0,
            "key-paper": 2,
            "protocol": 1,
        }
        # the count annotation groups the query; the name order must survive it
        assert [r["name"] for r in rows] == ["a-first", "key-paper", "protocol"]

    def test_rename_clash_is_a_400_that_names_the_tag(self, client):
        project = ProjectFactory()
        a, _ = _tags(project)
        r = client.patch(f"/api/v1/tags/{a.pk}/", json.dumps({"name": "PROTOCOL"}), **JSON)
        assert r.status_code == 400 and "“protocol” already exists" in r.json()["name"][0]
        r = client.patch(f"/api/v1/tags/{a.pk}/", json.dumps({"name": "key-paper"}), **JSON)
        assert r.status_code == 200  # its own name is not a clash
        r = client.post(
            "/api/v1/tags/", json.dumps({"project": project.slug, "name": "Protocol"}), **JSON
        )
        assert r.status_code == 400 and "already exists" in r.json()["name"][0]

    def test_recolour_and_a_bad_colour(self, client):
        project = ProjectFactory()
        a, _ = _tags(project)
        r = client.patch(f"/api/v1/tags/{a.pk}/", json.dumps({"color": "#2563EB"}), **JSON)
        assert r.status_code == 200 and r.json()["color"] == "#2563eb"
        r = client.patch(f"/api/v1/tags/{a.pk}/", json.dumps({"color": "blue"}), **JSON)
        assert r.status_code == 400

    def test_a_tag_stays_in_its_project(self, client):
        project = ProjectFactory()
        a, _ = _tags(project)
        other = ProjectFactory()
        r = client.patch(f"/api/v1/tags/{a.pk}/", json.dumps({"project": other.slug}), **JSON)
        assert r.status_code == 400 and "project" in r.json()
        a.refresh_from_db()
        assert a.project_id == project.pk

    def test_merge_endpoint(self, client):
        project = ProjectFactory()
        a, b = _tags(project)
        doc = _doc(project, "a.md", [a])
        foreign = Tag.objects.create(project=ProjectFactory(), name="x")
        url = f"/api/v1/tags/{a.pk}/merge/"
        assert client.post(url, json.dumps({"into": a.pk}), **JSON).status_code == 400
        assert client.post(url, json.dumps({"into": foreign.pk}), **JSON).status_code == 404
        assert client.post(url, json.dumps({"into": 2**40}), **JSON).status_code == 404
        assert client.post(url, json.dumps({}), **JSON).status_code == 400
        r = client.post(url, json.dumps({"into": b.pk}), **JSON)
        assert r.status_code == 200 and r.json() == {"into": b.pk, "files": 1}
        assert list(doc.tags.values_list("name", flat=True)) == ["protocol"]
        assert client.post(url, json.dumps({"into": b.pk}), **JSON).status_code == 404
        assert client.post(url, "{}", content_type="application/json").status_code == 401

    def test_and_filter_on_the_list_and_the_tree_stays_flat(self, client):
        project = ProjectFactory()
        a, b = _tags(project)
        _doc(project, "a.md", [a])
        both = _doc(project, "ab.md", [a, b])
        base = f"/api/v1/documents/?project={project.slug}"
        assert client.get(f"{base}&tag=key-paper", **HEADERS).json()["count"] == 2
        assert client.get(f"{base}&tag=key-paper&tag=protocol", **HEADERS).json()["count"] == 1
        assert client.get(f"{base}&tag=key-paper&tag=nope", **HEADERS).json()["count"] == 0
        tree = f"/api/v1/projects/{project.slug}/tree/?tag=key-paper&tag=protocol"
        with CaptureQueriesContext(connection) as small:
            rows = client.get(tree, **HEADERS).json()["files"]
        assert [f["id"] for f in rows] == [both.pk]
        for i in range(8):
            _doc(project, f"m{i}.md", [a, b])
        with CaptureQueriesContext(connection) as big:
            assert len(client.get(tree, **HEADERS).json()["files"]) == 9
        assert len(big) == len(small)
        # a tag that exists only in another project never leaks in
        Tag.objects.create(project=ProjectFactory(), name="key-paper")
        assert client.get(f"{base}&tag=key-paper", **HEADERS).json()["count"] == 10


class TestMcp:
    def test_list_project_files_takes_tags(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            mcp_client, "_request", lambda method, path, **kw: seen.update(kw, path=path) or {}
        )
        mcp_client.list_project_files("p")
        assert seen["path"] == "/projects/p/tree/" and seen.get("params") is None
        mcp_client.list_project_files("p", tags=["key-paper", "protocol"])
        assert seen["params"] == {"tag": ["key-paper", "protocol"]}
        server = (BASE / "mcp_server" / "server.py").read_text()
        assert 'def list_project_files(project: str, tag: str = "") -> dict:' in server
        assert "def list_documents(" not in server

    def test_manage_file_tag_client(self, monkeypatch):
        calls = []

        def fake(method, path, **kw):
            calls.append((method, path, kw))
            if path == "/tags/":
                return {"results": [{"id": 1, "name": "key-paper", "count": 2}]}
            return {"id": 1, "name": "x"}

        monkeypatch.setattr(mcp_client, "_request", fake)
        out = mcp_client.manage_file_tag("p", "Key-Paper", rename="core")
        assert calls[-1] == ("PATCH", "/tags/1/", {"json": {"name": "core"}})
        assert out["id"] == 1
        mcp_client.manage_file_tag("p", "key-paper", color="#2563eb")
        assert calls[-1] == ("PATCH", "/tags/1/", {"json": {"color": "#2563eb"}})
        with pytest.raises(ValueError, match="one of"):
            mcp_client.manage_file_tag("p", "key-paper")
        with pytest.raises(ValueError, match="one of"):
            mcp_client.manage_file_tag("p", "key-paper", rename="a", delete=True)
        with pytest.raises(ValueError, match="No tag"):
            mcp_client.manage_file_tag("p", "nope", delete=True)
        assert mcp_client.manage_file_tag("p", "key-paper", delete=True) == {
            "deleted": "key-paper",
            "files": 2,
        }
        assert calls[-1][:2] == ("DELETE", "/tags/1/")
        calls.clear()

        def fake_merge(method, path, **kw):
            calls.append((method, path, kw))
            if path == "/tags/":
                return {
                    "results": [
                        {"id": 1, "name": "key-paper", "count": 2},
                        {"id": 2, "name": "core", "count": 1},
                    ]
                }
            return {"into": 2, "files": 2}

        monkeypatch.setattr(mcp_client, "_request", fake_merge)
        assert mcp_client.manage_file_tag("p", "key-paper", merge_into="core") == {
            "into": 2,
            "files": 2,
        }
        assert calls[-1] == ("POST", "/tags/1/merge/", {"json": {"into": 2}})


def test_explorer_manages_tags_from_the_filter_row():
    files = (BASE / "frontend" / "src" / "app" / "pages" / "Files.tsx").read_text()
    body = files.split("export default function Files()", 1)[1]
    # the AND filter: a list of names, every one required
    assert (
        "useState<string[]>([])" in body
        and "tagFilter.every((n) => f.tags.some((t) => t.name === n))" in body
    )
    assert "!!tagFilter" not in body and "tagFilter === " not in body
    # the chip: click toggles, right-click manages, ⋯ on an active chip, a Clear
    for needle in (
        'data-testid="tag-chip"',
        'data-testid="tag-menu"',
        'data-testid="tag-filter-clear"',
        "all ${tagFilter.length} tags",
    ):
        assert needle in body, needle
    # the menu verbs and their flows
    for needle in (
        '"Only this tag"',
        '"Rename…"',
        '"Colour…"',
        '"Merge into…"',
        '"Delete tag…"',
        "already exists",
        "keep their other tags",
        "/merge/",
    ):
        assert needle in body, needle
    # every mutation refreshes both the tree and the tag pool, and the filter follows a rename / merge / delete
    assert body.count("tagTouched();") == 4
    assert 'queryKey: ["doc-tags", slug]' in body.split("const tagTouched", 1)[1].split("\n", 1)[0]
    assert (
        "cur.map((n) => (n === t.name ? wanted : n))" in body
        and "cur.filter((x) => x !== t.name)" in body
    )
    chunk = (BASE / "static" / "js" / "islands" / "Files-chunk.js").read_text()
    assert "Merge into…" in chunk and "tag-menu" in chunk
