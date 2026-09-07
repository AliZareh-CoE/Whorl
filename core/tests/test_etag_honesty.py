"""ETag honesty (#384): a write that leaves updated_at alone must still move the ETag.

The same stale-304 bug shipped twice (#381 tags, #383 reorder). Three guards: the data
version moves on any save/delete/M2M change, an M2M change stamps updated_at on the rows
involved, and no app code may call queryset.update() without updated_at unless the line says
why (`# etag: ok`).
"""

import ast
import re
from pathlib import Path

import pytest
from django.conf import settings

from core import versioning
from literature.models import Reference
from notes.models import Note
from projects.models import Project

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
BASE = Path(settings.BASE_DIR)
APPS = (
    "core",
    "projects",
    "plans",
    "documents",
    "literature",
    "notes",
    "writing",
    "research",
    "prompts",
    "bots",
    "api",
)


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


def test_data_version_moves_on_save_delete_and_m2m(db):
    before = versioning.data_version()
    project = Project.objects.create(name="P", slug="p")
    after_save = versioning.data_version()
    assert after_save > before
    note = Note.objects.create(project=project, title="N")
    ref = Reference.objects.create(title="R", bibtex_key="r")
    v = versioning.data_version()
    note.references.add(ref)
    assert versioning.data_version() > v
    v = versioning.data_version()
    ref.delete()
    assert versioning.data_version() > v


def test_m2m_change_touches_updated_at_on_both_sides(db):
    project = Project.objects.create(name="P", slug="p")
    note = Note.objects.create(project=project, title="N")
    ref = Reference.objects.create(title="R", bibtex_key="r")
    note_at, ref_at = note.updated_at, ref.updated_at
    note.references.add(ref)
    note.refresh_from_db()
    ref.refresh_from_db()
    assert note.updated_at > note_at and ref.updated_at > ref_at
    note_at = note.updated_at
    ref.notes.remove(note) if hasattr(ref, "notes") else note.references.remove(ref)
    note.refresh_from_db()
    assert note.updated_at > note_at


def test_list_etag_moves_after_a_bare_m2m_write(client, django_user_model):
    django_user_model.objects.create_superuser("owner", password="pw")
    project = Project.objects.create(name="P", slug="p")
    note = Note.objects.create(project=project, title="N")
    ref = Reference.objects.create(title="R", bibtex_key="r")
    etag = client.get("/api/v1/notes/?project=p", **HEADERS)["ETag"]
    assert (
        client.get("/api/v1/notes/?project=p", HTTP_IF_NONE_MATCH=etag, **HEADERS).status_code
        == 304
    )
    note.references.add(ref)  # no save() on the note
    fresh = client.get("/api/v1/notes/?project=p", HTTP_IF_NONE_MATCH=etag, **HEADERS)
    assert fresh.status_code == 200 and fresh["ETag"] != etag
    detail_etag = client.get(f"/api/v1/references/{ref.pk}/", **HEADERS)["ETag"]
    note.references.remove(ref)
    assert (
        client.get(
            f"/api/v1/references/{ref.pk}/", HTTP_IF_NONE_MATCH=detail_etag, **HEADERS
        ).status_code
        == 200
    )


QUERYSET_SHAPE = re.compile(
    r"objects|\.filter\(|\.exclude\(|\.all\(|\.select_related\(|queryset|qs"
)


def _queryset_names(tree) -> set[str]:
    """Bare names assigned from a queryset expression in this file (`docs = X.objects...`)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and QUERYSET_SHAPE.search(ast.unparse(node.value)):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _update_calls(path: Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    lines = path.read_text().splitlines()
    qs_names = _queryset_names(tree)
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "update"
        ):
            continue
        if node.args or not node.keywords:  # dict.update(other) / .update(**mapping) styles
            continue
        if any(k.arg is None for k in node.keywords):
            continue
        receiver = node.func.value
        source = ast.unparse(receiver)
        looks_like_queryset = bool(QUERYSET_SHAPE.search(source)) or (
            isinstance(receiver, ast.Name) and receiver.id in qs_names
        )
        if not looks_like_queryset:  # a dict being updated with keywords (hit.update(meta=…))
            continue
        keys = {k.arg for k in node.keywords}
        span = " ".join(lines[node.lineno - 1 : node.end_lineno])
        if "updated_at" in keys or "etag: ok" in span:
            continue
        yield f"{path.relative_to(BASE)}:{node.lineno}: .update({', '.join(sorted(keys))})"


def test_no_bare_queryset_update_in_app_code():
    offenders = []
    for app in APPS:
        for path in (BASE / app).rglob("*.py"):
            parts = path.relative_to(BASE).parts
            if "tests" in parts or "migrations" in parts:
                continue
            offenders.extend(_update_calls(path))
    assert not offenders, (
        "queryset.update() without updated_at leaves the ETag stale (a client keeps its old "
        "answer); add updated_at=timezone.now() or mark the line `# etag: ok` with a reason:\n"
        + "\n".join(offenders)
    )
