"""#561: a document that arrives without a `kind` (the classic upload form, the demo seed, an
import) is derived from its name on save — so the explorer previews it and draws the right
icon — and a migration backfills the rows that already exist."""

import pytest
from django.apps import apps
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from documents.models import Document
from documents.selectors import workspace_tree
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def test_save_derives_the_kind_from_the_file_name_before_the_title():
    project = ProjectFactory()
    txt = Document.objects.create(
        project=project, title="Dual-task protocol v3", file=ContentFile(b"x", name="dual.txt")
    )
    png = Document.objects.create(
        project=project, title="pilot figure", file=ContentFile(b"\x89PNG", name="pilot.png")
    )
    inline = Document.objects.create(project=project, title="scratch", content="# notes")
    kept = Document.objects.create(
        project=project, title="a.txt", kind="asset", file=ContentFile(b"x", name="a.txt")
    )
    assert txt.kind == "other" and png.kind == "asset" and inline.kind == "other"
    assert kept.kind == "asset"  # an explicit kind is never second-guessed
    rows = {r["id"]: r for r in workspace_tree(project)["files"]}
    assert rows[txt.pk]["is_text"] is True and rows[png.pk]["is_text"] is False


def test_classic_upload_previews_as_text(client, owner):
    project = ProjectFactory()
    client.force_login(owner)
    url = reverse("documents:bulk_upload", kwargs={"slug": project.slug})
    r = client.post(
        url,
        {
            "files": [
                SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain"),
                SimpleUploadedFile("fig.png", b"\x89PNG", content_type="image/png"),
            ]
        },
    )
    assert r.status_code == 201
    notes = project.documents.get(title="notes")
    fig = project.documents.get(title="fig")
    assert notes.kind == "other" and fig.kind == "asset"


def test_migration_backfills_blank_kinds():
    from importlib import import_module

    project = ProjectFactory()
    a = Document.objects.create(
        project=project, title="Proto", file=ContentFile(b"x", name="p.txt")
    )
    b = Document.objects.create(project=project, title="Fig", file=ContentFile(b"x", name="f.png"))
    c = Document.objects.create(project=project, title="Scratch", content="hi")
    Document.objects.filter(pk__in=[a.pk, b.pk, c.pk]).update(kind="")
    mod = import_module("documents.migrations.0006_derive_kinds")
    mod.derive_kinds(apps, None)
    assert [Document.objects.get(pk=x.pk).kind for x in (a, b, c)] == ["other", "asset", "other"]
