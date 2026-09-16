"""#554 (backlog 353): tags and the description in the Files explorer — tree rows carry
both (one prefetch), the serializer refuses another project's tags and returns names next
to ids, `?tag=` narrows the list, `list_documents(tag)` passes it on, and the explorer's
pane / filter row / quick-open read them."""

from pathlib import Path

import pytest
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

from documents.models import Document, Folder, Tag
from documents.selectors import workspace_tree
from mcp_server import client as mcp_client
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db

BASE = Path(settings.BASE_DIR)
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _doc(project, name, folder=None, description="", tags=()):
    doc = Document.objects.create(
        project=project,
        folder=folder,
        title=name,
        rel_path=f"{folder.name}/{name}" if folder else name,
        kind="other",
        description=description,
    )
    doc.tags.set(tags)
    return doc


class TestTree:
    def test_rows_carry_description_and_tags(self):
        project = ProjectFactory()
        red = Tag.objects.create(project=project, name="key-paper", color="#dc2626")
        plain = Tag.objects.create(project=project, name="figure")
        _doc(project, "lavie.md", description="The anchor paper.", tags=[red, plain])
        _doc(project, "bare.md")
        rows = {f["name"]: f for f in workspace_tree(project)["files"]}
        assert rows["lavie.md"]["description"] == "The anchor paper."
        assert rows["lavie.md"]["tags"] == [
            {"id": plain.id, "name": "figure", "color": ""},
            {"id": red.id, "name": "key-paper", "color": "#dc2626"},
        ]
        assert rows["bare.md"]["tags"] == [] and rows["bare.md"]["description"] == ""

    def test_tags_do_not_cost_a_query_per_file(self):
        project = ProjectFactory()
        tag = Tag.objects.create(project=project, name="t")
        folder = Folder.objects.create(project=project, name="Data")
        for i in range(2):
            _doc(project, f"a{i}.md", folder, tags=[tag])
        with CaptureQueriesContext(connection) as small:
            workspace_tree(project)
        for i in range(10):
            _doc(project, f"b{i}.md", folder, tags=[tag])
        with CaptureQueriesContext(connection) as big:
            workspace_tree(project)
        assert len(big) == len(small)


class TestApi:
    def test_patch_by_id_returns_names_and_refuses_foreign_tags(self, client):
        project, other = ProjectFactory(), ProjectFactory()
        mine = Tag.objects.create(project=project, name="protocol", color="#2563eb")
        theirs = Tag.objects.create(project=other, name="protocol")
        doc = _doc(project, "p.md")
        resp = client.patch(
            f"/api/v1/documents/{doc.id}/",
            {"tags": [theirs.id]},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 400 and "protocol" in resp.json()["tags"][0]
        assert doc.tags.count() == 0
        resp = client.patch(
            f"/api/v1/documents/{doc.id}/",
            {"tags": [mine.id], "description": "Frozen after pilot feedback."},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["tags"] == [mine.id] and body["tag_names"] == ["protocol"]
        assert body["description"] == "Frozen after pilot feedback."
        # the tree reads the same
        row = next(f for f in workspace_tree(project)["files"] if f["name"] == "p.md")
        assert row["tags"][0]["name"] == "protocol" and row["tags"][0]["color"] == "#2563eb"

    def test_create_with_foreign_tag_is_refused(self, client):
        project, other = ProjectFactory(), ProjectFactory()
        theirs = Tag.objects.create(project=other, name="x")
        resp = client.post(
            "/api/v1/documents/",
            {"project": project.slug, "title": "n", "tags": [theirs.id]},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 400 and "tags" in resp.json()

    def test_tag_filter_on_the_list(self, client):
        project = ProjectFactory()
        tag = Tag.objects.create(project=project, name="key-paper")
        _doc(project, "a.md", tags=[tag])
        _doc(project, "b.md")
        resp = client.get(f"/api/v1/documents/?project={project.slug}&tag=key-paper", **HEADERS)
        assert resp.status_code == 200
        rows = resp.json()["results"]
        assert [r["title"] for r in rows] == ["a.md"] and rows[0]["tag_names"] == ["key-paper"]
        resp = client.get(f"/api/v1/documents/?project={project.slug}&tag=nothing", **HEADERS)
        assert resp.json()["count"] == 0
        resp = client.get(f"/api/v1/documents/?project={project.slug}", **HEADERS)
        assert resp.json()["count"] == 2

    def test_list_reads_tags_without_a_query_per_row(self, client):
        project = ProjectFactory()
        tag = Tag.objects.create(project=project, name="t")
        for i in range(2):
            _doc(project, f"a{i}.md", tags=[tag])
        with CaptureQueriesContext(connection) as small:
            client.get(f"/api/v1/documents/?project={project.slug}", **HEADERS)
        for i in range(10):
            _doc(project, f"b{i}.md", tags=[tag])
        with CaptureQueriesContext(connection) as big:
            client.get(f"/api/v1/documents/?project={project.slug}", **HEADERS)
        assert len(big) == len(small)


def test_mcp_client_passes_the_tag(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mcp_client, "_request", lambda method, path, **kw: seen.update(kw, path=path) or {}
    )
    mcp_client.list_documents("p")
    assert seen["params"] == {"project": "p"}
    mcp_client.list_documents("p", tag="key-paper")
    assert seen["params"] == {"project": "p", "tag": "key-paper"}
    server = (BASE / "mcp_server" / "server.py").read_text()
    assert 'def list_documents(project: str, tag: str = "") -> dict:' in server


def test_explorer_reads_and_edits_tags_and_description():
    files = (BASE / "frontend" / "src" / "app" / "pages" / "Files.tsx").read_text()
    # the node shape
    assert "description: string;" in files and "tags: Tag[];" in files
    # the pane: description with an edit, chips with a remove, + Tag with a menu of the rest
    assert 'data-testid="file-description"' in files and 'data-testid="edit-description"' in files
    assert "multiline: true" in files.split("const editDescription", 1)[1].split("\n", 3)[1]
    assert 'data-testid="file-tag"' in files and "aria-label={`Remove tag ${t.name}`}" in files
    assert "onClick={(e) => menu.open(e, tagItems(selected))}" in files
    assert '{ label: "New tag…"' in files
    # a new tag reuses a same-name tag (any case) and gets a colour from its name
    assert "t.name.toLowerCase() === wanted.toLowerCase()" in files
    assert "color: tagColor(wanted)" in files and "const TAG_PALETTE = [" in files
    # the pane's edits PATCH ids and refresh the tree
    assert "body: { tags: tags.map((t) => t.id) }" in files
    # the filter row: tags in use with counts; folders keep only matching descendants; open
    assert 'data-testid="tag-filter"' in files and 'data-testid="tag-filter-count"' in files
    assert "const isOpen = (id: number) => expanded[id] ?? !!tagFilter;" in files
    assert "if (tagFilter && !keep.has(f.id)) continue;" in files
    # rows and quick-open
    assert 'data-testid="tag-dots"' in files
    assert "fuzzy(q, f.rel_path) || f.tags.some((t) => fuzzy(q, t.name))" in files
    # manuscript sources are not editable here (the API refuses them too)
    pane = files.split('data-testid="file-meta"', 1)[0][-200:]
    assert 'selected.role !== "manuscript_source"' in pane
    chunks = " ".join(p.read_text(errors="ignore") for p in (BASE / "static" / "js").rglob("*.js"))
    assert "tag-filter" in chunks and "file-tags" in chunks and "add-tag" in chunks
