"""#416 — a project as a Markdown vault."""

import io
import json
import zipfile

import pytest
from django.core.files.base import ContentFile

from documents.models import Document, Folder
from literature.models import ProjectReference, Reference
from notes.models import Note
from plans.models import Milestone, Phase
from projects.models import DecisionRecord, Project
from projects.vault import build_vault, vault_bytes
from research.models import Evidence, ExperimentEntry, Hypothesis, Protocol
from writing.models import Manuscript, ManuscriptFile

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings, django_user_model, tmp_path):
    settings.ATLAS_API_KEY = KEY
    settings.MEDIA_ROOT = str(tmp_path / "media")
    django_user_model.objects.create_superuser("owner", password="pw")
    project = Project.objects.create(name="Attention & Memory", description="Why load hurts.")
    phase = Phase.objects.create(project=project, name="Pilot", order=1)
    Milestone.objects.create(phase=phase, title="Run 10 participants")
    ref = Reference.objects.create(title="Load theory", bibtex_key="lavie2010attention", year=2010)
    ProjectReference.objects.create(project=project, reference=ref, notes="Key paper.")
    note = Note.objects.create(
        project=project,
        title="Load theory / overview",
        body="See [[Pilot plan]] and @lavie2010attention.",
    )
    note.references.add(ref)
    Note.objects.create(project=project, title="Pilot plan", body="n = 10")
    DecisionRecord.objects.create(
        project=project, title="Dual task", decision="Yes", context="Because"
    )
    hyp = Hypothesis.objects.create(project=project, statement="Load is strategic")
    Evidence.objects.create(hypothesis=hyp, direction="supports", summary="pilot", reference=ref)
    ExperimentEntry.objects.create(project=project, title="Block order", body="fine")
    Protocol.objects.create(project=project, title="Procedure", body="1. brief")
    ms = Manuscript.objects.create(project=project, title="Paper one", abstract="We show.")
    ManuscriptFile.objects.create(
        manuscript=ms, path="main.tex", content="\\documentclass{article}", is_main=True
    )
    ManuscriptFile.objects.create(
        manuscript=ms, path="sections/method.tex", content="\\section{Method}"
    )
    folder = Folder.objects.create(project=project, name="Data")
    sub = Folder.objects.create(project=project, name="Pilot", parent=folder)
    Document.objects.create(
        project=project, folder=sub, title="readme", file=ContentFile(b"hello", name="readme.txt")
    )
    return project


def test_vault_layout_and_contents(world):
    data, manifest = vault_bytes(world)
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()
    root = "Attention Memory/"  # the ampersand is dropped, the name stays readable
    assert all(n.startswith(root) for n in names)
    rel = {n[len(root) :] for n in names}
    for expected in (
        "README.md",
        "plan.md",
        "notes/Load theory overview.md",
        "notes/Pilot plan.md",
        "references.bib",
        "literature.md",
        "research/hypotheses.md",
        "protocols/Procedure v1.md",
        "manuscripts/Paper one/README.md",
        "manuscripts/Paper one/main.tex",
        "manuscripts/Paper one/sections/method.tex",
        "documents/Data/Pilot/readme.txt",
        "atlas-vault.json",
    ):
        assert expected in rel, expected
    assert any(n.startswith("decisions/") and n.endswith("Dual task.md") for n in rel)
    assert any(n.startswith("research/experiments/") and n.endswith("Block order.md") for n in rel)
    note = zf.read(root + "notes/Load theory overview.md").decode()
    assert note.startswith("---\n") and '"lavie2010attention"' in note
    assert "[[Pilot plan]] and @lavie2010attention" in note  # links kept as written
    assert (
        "@article{lavie2010attention" in zf.read(root + "references.bib").decode()
        or "lavie2010attention" in zf.read(root + "references.bib").decode()
    )
    lit = zf.read(root + "literature.md").decode()
    assert "| @lavie2010attention |" in lit and "Key paper." in lit
    assert "Run 10 participants" in zf.read(root + "plan.md").decode()
    hyp = zf.read(root + "research/hypotheses.md").decode()
    assert "## Load is strategic" in hyp and "**supports** — pilot (@lavie2010attention)" in hyp
    assert zf.read(root + "documents/Data/Pilot/readme.txt") == b"hello"
    inner = json.loads(zf.read(root + "atlas-vault.json"))
    assert inner["counts"] == manifest["counts"]
    assert manifest["counts"] == {
        "phases": 1,
        "questions": 0,
        "notes": 2,
        "decisions": 1,
        "references": 1,
        "hypotheses": 1,
        "experiments": 1,
        "datasets": 0,
        "protocols": 1,
        "manuscripts": 1,
        "documents": 1,
    }
    assert manifest["files"] == len(names) - 1  # the manifest itself is not counted


def test_vault_api_and_ui(client, world):
    r = client.get(f"/api/v1/projects/{world.slug}/vault/", **HEADERS)
    assert r.status_code == 200 and r["Content-Type"] == "application/zip"
    assert r["Content-Disposition"].endswith(f'"{world.slug}-vault.zip"')
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert any(n.endswith("documents/Data/Pilot/readme.txt") for n in names)
    slim = client.get(f"/api/v1/projects/{world.slug}/vault/?documents=0", **HEADERS)
    assert not any("documents/" in n for n in zipfile.ZipFile(io.BytesIO(slim.content)).namelist())
    assert "/vault/" in open("frontend/src/app/pages/ProjectOverview.tsx").read()
    assert "Markdown vault" in open("frontend/src/app/CommandBar.tsx").read()


def test_duplicate_titles_do_not_overwrite(world):
    Note.objects.create(project=world, title="Pilot plan!", body="second")  # same slug
    buffer = io.BytesIO()
    build_vault(world, buffer, include_documents=False)
    names = zipfile.ZipFile(buffer).namelist()
    assert sum(1 for n in names if "/notes/Pilot plan" in n) == 2
