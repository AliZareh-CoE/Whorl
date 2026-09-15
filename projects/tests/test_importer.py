"""#535 — bulk import of a projects folder."""

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from documents.models import Document, Folder
from literature.models import ProjectReference, Reference
from notes.models import Note
from projects import importer
from projects.models import Project

pytestmark = pytest.mark.django_db

MINI_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)
BIB = b"""@article{smith2020load,
  title={Perceptual load and the cost of distraction},
  author={Smith, Ana},
  journal={Journal of Vision},
  year={2020},
}
"""


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the importer must not call the network in tests")

    monkeypatch.setattr("literature.importers.fetch_metadata_by_doi", boom)
    monkeypatch.setattr("literature.importers.fetch_metadata_by_arxiv", boom)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "Projects"
    a = root / "Attention_and_memory"
    (a / "notes").mkdir(parents=True)
    (a / "data").mkdir()
    (a / "papers").mkdir()
    (a / ".git").mkdir()
    (a / "node_modules").mkdir()
    (a / "README.md").write_text("# Attention & Memory\n\nLoad theory pilot.\n\nSecond paragraph.")
    (a / "notes" / "ideas.md").write_text("See [[Reading list]] — #pilot idea")
    (a / "notes" / "Reading list.md").write_text("- Lavie 2010")
    (a / "data" / "results (2019).csv").write_text("a,b\n1,2\n")
    (a / "papers" / "Lavie – load theory.pdf").write_bytes(MINI_PDF)
    (a / "refs.bib").write_bytes(BIB)
    (a / ".git" / "config").write_text("x")
    (a / "node_modules" / "x.js").write_text("x")
    (a / ".DS_Store").write_bytes(b"\x00")
    deep = a / "d1" / "d2" / "d3" / "d4" / "d5" / "d6" / "d7" / "d8"
    deep.mkdir(parents=True)
    (deep / "deep.txt").write_text("too deep")
    (a / "huge.bin").write_bytes(b"x" * 3000)
    monkeypatch.setattr(importer, "MAX_UPLOAD_BYTES", 2000)
    b = root / "second-project"
    b.mkdir()
    (b / "plan.txt").write_text("phase one")
    (root / ".hidden").mkdir()
    (root / "loose.txt").write_text("not a project")
    return root


def test_plan_reads_the_folder_without_touching_anything(tree, no_network):
    rows = [p.as_dict() for p in importer.plan(tree)]
    assert [r["folder"] for r in rows] == ["Attention_and_memory", "second-project"]
    first, second = rows
    assert first["name"] == "Attention & Memory" and first["slug"] == "attention-memory"
    assert first["exists"] is False and first["has_readme"] is True
    assert (first["pdfs"], first["notes"], first["bibs"], first["files"]) == (1, 2, 1, 1)
    assert {s["path"]: s["reason"] for s in first["skipped"]} == {
        "d1/d2/d3/d4/d5/d6/d7/d8/deep.txt": "nested too deep",
        "huge.bin": "larger than 2000 bytes",
    }
    assert second["name"] == "second project" and second["files"] == 1
    assert Project.objects.count() == 0 and Document.objects.count() == 0


def test_names_become_safe_tree_paths():
    assert importer.safe_segment("results (2019).csv") == "results-2019.csv"
    assert importer.safe_segment("Résumé – final.PDF") == "Resume-final.PDF"
    assert importer.safe_segment(".env") == "env"
    assert importer.safe_segment("???") == "file"
    assert importer.safe_segment("a" * 100 + ".txt").endswith(".txt")
    assert len(importer.safe_segment("a" * 100 + ".txt")) <= 80
    used: set[str] = set()
    assert importer._unique("x/a.pdf", used) == "x/a.pdf"
    assert importer._unique("x/A.pdf", used) == "x/A-2.pdf"
    assert importer.humanize("attention_and-memory  2019") == "attention and memory 2019"


def test_import_brings_everything_in_and_is_idempotent(tree, no_network):
    rows = importer.import_folder(tree)
    first = rows[0]
    project = Project.objects.get(slug="attention-memory")
    assert first["created"] and first["description_set"]
    assert project.description == "Load theory pilot.\n\nSecond paragraph."
    assert (first["documents"], first["notes"], first["references"]) == (2, 2, 2)
    # documents keep the folder structure with safe names and the original title
    csv = Document.objects.get(project=project, rel_path="data/results-2019.csv")
    assert csv.title == "results (2019).csv" and csv.folder.name == "data"
    assert csv.content_type == "text/csv" and csv.file_size == 8 and csv.kind == "other"
    assert csv.file.read() == b"a,b\n1,2\n"
    assert Document.objects.get(project=project, rel_path="refs.bib").kind == "bib"
    assert set(Folder.objects.filter(project=project).values_list("name", flat=True)) == {"data"}
    # notes, with links, tags and unique titles
    ideas = Note.objects.get(project=project, title="ideas")
    assert ideas.tags == ["pilot"]
    assert list(ideas.outgoing_links.values_list("target__title", flat=True)) == ["Reading list"]
    # the PDF became a stub paper linked to the project; the .bib entry too
    refs = Reference.objects.order_by("pk")
    assert {r.title for r in refs} == {
        "Perceptual load and the cost of distraction",
        "Lavie – load theory",
    }
    assert ProjectReference.objects.filter(project=project).count() == 2
    stub = Reference.objects.get(title="Lavie – load theory")
    assert stub.extra["imported_from"] == "attention-memory:papers/Lavie-load-theory.pdf"
    assert stub.pdf and first["needs_metadata"] == 1
    assert Project.objects.get(slug="second-project").documents.count() == 1

    # second run: nothing new, and nothing the owner edited is touched
    project.description = "edited by hand"
    project.save()
    ideas.body = "changed"
    ideas.save()
    again = importer.import_folder(tree)[0]
    assert not again["created"] and not again["description_set"]
    assert (again["documents"], again["notes"], again["references"]) == (0, 0, 0)
    assert {s["reason"] for s in again["skipped"]} >= {
        "already imported",
        "a note with this title exists",
        "already in the library",
    }
    assert Project.objects.count() == 2 and Reference.objects.count() == 2
    assert Project.objects.get(slug="attention-memory").description == "edited by hand"
    assert Note.objects.get(pk=ideas.pk).body == "changed"


def test_options_keep_pdfs_and_markdown_as_files(tree, no_network):
    row = importer.import_project(
        tree, "Attention_and_memory", pdfs="documents", markdown="documents"
    )
    project = Project.objects.get(slug="attention-memory")
    assert (row["documents"], row["notes"], row["references"]) == (5, 0, 1)
    assert Document.objects.filter(
        project=project, rel_path="papers/Lavie-load-theory.pdf"
    ).exists()
    assert (
        Document.objects.get(project=project, rel_path="notes/ideas.md").content_type
        == "text/markdown"
    )
    assert Note.objects.count() == 0
    with pytest.raises(ValueError):
        importer.import_project(tree, "Attention_and_memory", pdfs="nope")


def test_only_and_bad_paths(tree, no_network):
    rows = importer.plan(tree, only=["second-project"])
    assert [r.folder for r in rows] == ["second-project"]
    with pytest.raises(ValueError, match="No such folder"):
        importer.plan(tree, only=["missing"])
    with pytest.raises(ValueError, match="not a folder"):
        importer.resolve_root(str(tree / "loose.txt"))
    with pytest.raises(ValueError):
        importer.resolve_root("")
    assert importer.list_folders(tree) == ["Attention_and_memory", "second-project"]


def test_import_folder_api(client_logged_in, tree, no_network):
    r = client_logged_in.post(
        "/api/v1/projects/import-folder/",
        {"path": str(tree)},
        content_type="application/json",
    )
    assert r.status_code == 200 and r.json()["dry_run"] is True
    assert [p["folder"] for p in r.json()["projects"]] == ["Attention_and_memory", "second-project"]
    assert Project.objects.count() == 0
    r = client_logged_in.post(
        "/api/v1/projects/import-folder/",
        {"path": str(tree), "dry_run": False, "only": ["second-project"]},
        content_type="application/json",
    )
    assert r.status_code == 200
    (row,) = r.json()["projects"]
    assert row["created"] and row["documents"] == 1 and Project.objects.count() == 1
    r = client_logged_in.post(
        "/api/v1/projects/import-folder/",
        {"path": str(tree / "nowhere")},
        content_type="application/json",
    )
    assert r.status_code == 400 and "not a folder" in r.json()["detail"]
    r = client_logged_in.post(
        "/api/v1/projects/import-folder/",
        {"path": str(tree), "pdfs": "cloud"},
        content_type="application/json",
    )
    assert r.status_code == 400


def test_import_projects_command(tree, no_network):
    out = StringIO()
    call_command("import_projects", str(tree), stdout=out)
    text = out.getvalue()
    assert "Attention_and_memory" in text and "Dry run — add --apply" in text
    assert "skipped huge.bin" in text and Project.objects.count() == 0
    out = StringIO()
    call_command("import_projects", str(tree), "--apply", "--only", "second-project", stdout=out)
    assert "created" in out.getvalue() and Project.objects.count() == 1


def test_frozen_server_ships_the_skills_folder():
    spec = Path("desktop/server/atlas_server.spec").read_text()
    assert 'os.path.join(ROOT, "mcp_server", "skills")' in spec


def test_import_page_is_wired_in_the_spa():
    """The Projects page offers the import, the page drives one folder per request, and the
    command bar knows the verb."""
    page = Path("frontend/src/app/pages/ImportProjects.tsx").read_text()
    for needle in (
        '"/projects/import-folder/"',
        "dry_run: false, only: [folder]",
        'data-testid="import-run"',
        "pickFolder",
        "already in Atlas",
    ):
        assert needle in page, needle
    projects = Path("frontend/src/app/pages/Projects.tsx").read_text()
    assert 'data-testid="import-folder-link"' in projects and "/projects/import" in projects
    assert 'path="projects/import"' in Path("frontend/src/app/main.tsx").read_text()
    assert "Import a folder of projects" in Path("frontend/src/app/CommandBar.tsx").read_text()
