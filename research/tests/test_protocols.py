"""Versioned protocol library (Backlog #7)."""

import pytest

from projects.tests.factories import ProjectFactory
from research.models import Protocol

pytestmark = pytest.mark.django_db

KEY = "test-api-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key_setting(settings, owner):
    settings.ATLAS_API_KEY = KEY


class TestVersioning:
    def test_new_version_chains_and_increments(self):
        project = ProjectFactory()
        v1 = Protocol.objects.create(project=project, title="Cell prep", body="step 1")
        v2 = v1.new_version(body="step 1\nstep 2")

        assert v2.version == 2
        assert v2.parent == v1
        assert v2.project == project
        assert v2.title == "Cell prep"  # carried over
        assert v2.body == "step 1\nstep 2"  # overridden

    def test_is_current_tracks_the_head_of_the_chain(self):
        project = ProjectFactory()
        v1 = Protocol.objects.create(project=project, title="Stain", body="a")
        v2 = v1.new_version()
        v1.refresh_from_db()
        assert v1.is_current is False  # superseded
        assert v2.is_current is True

    def test_first_version_defaults(self):
        p = Protocol.objects.create(project=ProjectFactory(), title="Wash")
        assert p.version == 1
        assert p.parent is None
        assert p.is_current is True
        assert str(p) == "Wash v1"


class TestProtocolAPI:
    def test_create_and_list(self, client):
        project = ProjectFactory()
        resp = client.post(
            "/api/v1/protocols/",
            data={"project": project.slug, "title": "RNA extraction", "body": "lyse, bind, wash"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 201, resp.content
        created = resp.json()
        assert created["version"] == 1
        assert created["is_current"] is True

        listed = client.get(f"/api/v1/protocols/?project={project.slug}", **HEADERS).json()
        assert listed["count"] == 1

    def test_new_version_action(self, client):
        project = ProjectFactory()
        v1 = Protocol.objects.create(project=project, title="PCR", body="35 cycles")
        resp = client.post(
            f"/api/v1/protocols/{v1.id}/new-version/",
            data={"body": "40 cycles"},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 201, resp.content
        data = resp.json()
        assert data["version"] == 2
        assert data["parent"] == v1.id
        assert data["body"] == "40 cycles"
        assert data["title"] == "PCR"  # carried over

    def test_requires_api_key(self, client):
        assert client.get("/api/v1/protocols/").status_code == 401

    def test_scoped_to_project(self, client):
        a, b = ProjectFactory(), ProjectFactory()
        Protocol.objects.create(project=a, title="A-only")
        Protocol.objects.create(project=b, title="B-only")
        data = client.get(f"/api/v1/protocols/?project={a.slug}", **HEADERS).json()
        assert [p["title"] for p in data["results"]] == ["A-only"]

    def test_version_and_parent_are_read_only(self, client):
        # the history chain can't be forged through create — version/parent are server-managed
        project = ProjectFactory()
        resp = client.post(
            "/api/v1/protocols/",
            data={"project": project.slug, "title": "X", "version": 99},
            content_type="application/json",
            **HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["version"] == 1
