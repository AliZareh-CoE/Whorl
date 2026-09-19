"""Audit #35 (#568): a render value that is an object or a list is refused, never repr-ed
into the text; a Unicode digit ("²") never reaches int(); the admin refuses a chain loop;
Duplicate and the zip stream file bytes; anyio carries the fix for its two advisories."""

import io
import json
import zipfile
from importlib.metadata import version

import pytest
from django.core.files.base import ContentFile

from documents import bulk
from documents.models import Document
from literature.matrix import resolve_theme
from literature.tests.factories import ReferenceFactory
from notes.tests.factories import NoteFactory
from projects.tests.factories import ProjectFactory
from prompts.admin import PromptAdminForm
from prompts.models import Prompt

pytestmark = pytest.mark.django_db
KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}
JSON = {"content_type": "application/json", **HEADERS}


@pytest.fixture(autouse=True)
def _key(settings, owner):
    settings.ATLAS_API_KEY = KEY


def _render(client, prompt, values):
    return client.post(
        f"/api/v1/prompts/{prompt.pk}/render/", json.dumps({"values": values}), **JSON
    )


class TestRenderValues:
    def test_an_object_or_a_list_is_refused_not_repr_ed(self, client):
        prompt = Prompt.objects.create(title="P", body="Read {{paper:reference}} and {{tone}}")
        for values in ({"paper": {"a": 1}}, {"paper": [1, 2]}, {"tone": {"a": 1}}):
            r = _render(client, prompt, values)
            assert r.status_code == 400, values
            assert "must be text or an id" in r.json()["detail"]
            assert not r.json()["detail"].startswith("No ")  # "No …" is the 404 shape
        prompt.refresh_from_db()
        assert prompt.use_count == 0  # a refused render is not a use

    def test_a_unicode_digit_is_text_not_a_crash(self, client):
        prompt = Prompt.objects.create(title="P", body="Read {{paper:reference}}")
        for value in ("²", "①", "٣"):  # isdigit() is True for all three; int() accepts only "٣"
            r = _render(client, prompt, {"paper": value})
            assert r.status_code in (200, 404), value
        r = _render(client, prompt, {"paper": "²"})
        assert r.status_code == 200 and r.json()["text"] == "Read ²"


class TestUnicodeDigitsElsewhere:
    def test_query_parameters_that_feed_int(self, client):
        project = ProjectFactory()
        note = NoteFactory(project=project)
        r = client.get(f"/api/v1/notes/{note.pk}/graph/?depth=²", **HEADERS)
        assert r.status_code == 400
        assert client.get("/api/v1/references/?year=²", **HEADERS).status_code == 200
        assert client.get("/api/v1/references/?year_min=²&year_max=²", **HEADERS).status_code == 200
        assert client.get("/api/v1/quick-capture/?run=²", **HEADERS).status_code == 200
        assert client.get("/api/v1/quick-capture/history/?limit=²", **HEADERS).status_code == 400

    def test_matrix_lookups_by_a_unicode_digit_fall_through(self):
        project = ProjectFactory()
        assert resolve_theme(project, "²") is not None  # created by name, not looked up as a pk
        ReferenceFactory(bibtex_key="two")
        from literature.matrix import set_mark

        with pytest.raises(Exception, match="(?i)reference|found|no "):
            set_mark(project, "²", "T")


class TestAdminLoopGuard:
    def _form(self, prompt, nxt):
        data = {
            "title": prompt.title,
            "body": prompt.body,
            "tags": "",
            "next": nxt.pk if nxt else "",
        }
        return PromptAdminForm(data=data, instance=prompt)

    def test_the_admin_refuses_self_and_a_two_cycle(self):
        a = Prompt.objects.create(title="A", body="x")
        b = Prompt.objects.create(title="B", body="x", next=a)
        form = self._form(a, a)
        assert not form.is_valid() and "loop" in " ".join(form.errors["next"])
        form = self._form(a, b)  # A → B → A
        assert not form.is_valid() and "next" in form.errors

    def test_a_straight_chain_and_no_next_pass(self):
        a = Prompt.objects.create(title="A", body="x")
        b = Prompt.objects.create(title="B", body="x")
        assert self._form(a, b).is_valid()
        assert self._form(a, None).is_valid()
        fresh = PromptAdminForm(data={"title": "C", "body": "x", "tags": "", "next": a.pk})
        assert fresh.is_valid()  # a new prompt has no pk to loop back to


def _doc(project, name, body):
    return Document.objects.create(
        project=project,
        title=name,
        rel_path=name,
        kind="other",
        file=ContentFile(body, name=name),
        content_type="application/octet-stream",
    )


class TestStreamedBytes:
    def test_duplicate_copies_the_bytes_into_a_new_file(self):
        project = ProjectFactory()
        body = bytes(range(256)) * 2000  # 512 KB, past any one chunk
        doc = _doc(project, "data.bin", body)
        copy = bulk.duplicate_document(doc)
        assert copy.file.name != doc.file.name
        with copy.file.open("rb") as handle:
            assert handle.read() == body
        assert copy.file_size == len(body)

    def test_zip_members_carry_the_bytes(self):
        project = ProjectFactory()
        body = bytes(range(256)) * 1000
        a = _doc(project, "a.bin", body)
        spool, name, count = bulk.build_archive(project, [a.pk], None)
        with zipfile.ZipFile(io.BytesIO(spool.read())) as zf:
            assert zf.namelist() == ["a.bin"] and zf.read("a.bin") == body
        assert count == 1 and name == f"{project.slug}-files.zip"


def test_anyio_carries_the_fix_for_its_two_advisories():
    # CVE-2026-63374 / CVE-2026-64847 are fixed in 4.14.2; the lock pins 4.15.1
    major, minor, patch = (int(p) for p in version("anyio").split(".")[:3])
    assert (major, minor, patch) >= (4, 14, 2)
