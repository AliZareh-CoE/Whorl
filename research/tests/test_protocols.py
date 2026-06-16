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


class TestLineage:
    def test_lineage_walks_parents_newest_first(self):
        project = ProjectFactory()
        v1 = Protocol.objects.create(project=project, title="P")
        v2 = v1.new_version()
        v3 = v2.new_version()
        assert [p.version for p in v3.lineage] == [2, 1]
        assert v1.lineage == []


class TestProtocolClassicViews:
    def test_list_shows_only_current_with_new_version_link(self, client_logged_in):
        from django.urls import reverse

        project = ProjectFactory()
        v1 = Protocol.objects.create(project=project, title="Cell prep", body="step one")
        v2 = v1.new_version(body="step one\nstep two")  # supersedes v1
        body = client_logged_in.get(
            reverse("research:protocols", args=[project.slug])
        ).content.decode()
        assert "Cell prep" in body
        assert "v2" in body  # the current head
        assert "step two" in body  # current body rendered
        # the new-version link points at the current head (v2), not the superseded v1
        assert reverse("research:protocol_new_version", args=[project.slug, v2.pk]) in body
        assert reverse("research:protocol_new_version", args=[project.slug, v1.pk]) not in body

    def test_list_has_no_n_plus_one(self, client_logged_in, django_assert_max_num_queries):
        # AUDIT #24: neither the current-head filter (is_current exists()) nor the history
        # disclosure (parent walk) may run a query per row — both are derived in memory.
        from django.urls import reverse

        project = ProjectFactory()
        for i in range(3):
            Protocol.objects.create(project=project, title=f"P{i}").new_version()
        url = reverse("research:protocols", args=[project.slug])
        client_logged_in.get(url)  # warm caches
        with django_assert_max_num_queries(12) as ctx:
            client_logged_in.get(url)
        baseline = len(ctx.captured_queries)
        for i in range(3, 9):
            Protocol.objects.create(project=project, title=f"P{i}").new_version()
        with django_assert_max_num_queries(baseline):
            client_logged_in.get(url)  # 9 protocols cost no more queries than 3 did

    def test_create_makes_version_one(self, client_logged_in):
        from django.urls import reverse

        project = ProjectFactory()
        resp = client_logged_in.post(
            reverse("research:protocol_create", args=[project.slug]),
            {"title": "Staining", "body": "fix, wash, image"},
        )
        assert resp.status_code == 302
        p = Protocol.objects.get(title="Staining")
        assert p.version == 1 and p.parent is None

    def test_new_version_view_creates_next_version(self, client_logged_in):
        from django.urls import reverse

        project = ProjectFactory()
        v1 = Protocol.objects.create(project=project, title="PCR", body="35 cycles")
        # GET prefills with the current version
        get = client_logged_in.get(
            reverse("research:protocol_new_version", args=[project.slug, v1.pk])
        )
        assert b"35 cycles" in get.content
        # POST creates v2
        resp = client_logged_in.post(
            reverse("research:protocol_new_version", args=[project.slug, v1.pk]),
            {"title": "PCR", "body": "40 cycles"},
        )
        assert resp.status_code == 302
        v2 = Protocol.objects.get(project=project, version=2)
        assert v2.parent == v1 and v2.body == "40 cycles"


class TestExperimentProvenance:
    def test_experiment_links_to_a_protocol_version(self):
        from research.models import ExperimentEntry

        project = ProjectFactory()
        v1 = Protocol.objects.create(project=project, title="Stain", body="a")
        v2 = v1.new_version(body="b")
        entry = ExperimentEntry.objects.create(project=project, title="Run A", protocol=v2)
        assert entry.protocol == v2
        assert list(v2.experiments.all()) == [entry]

    def test_deleting_a_protocol_keeps_the_experiment(self):
        from research.models import ExperimentEntry

        project = ProjectFactory()
        p = Protocol.objects.create(project=project, title="Wash")
        entry = ExperimentEntry.objects.create(project=project, title="Run", protocol=p)
        p.delete()
        entry.refresh_from_db()
        assert entry.protocol is None  # SET_NULL: the entry survives

    def test_form_scopes_protocol_to_project(self):
        from research.forms import ExperimentEntryForm

        project = ProjectFactory()
        other = ProjectFactory()
        mine = Protocol.objects.create(project=project, title="Mine")
        Protocol.objects.create(project=other, title="Theirs")
        form = ExperimentEntryForm(project=project)
        assert list(form.fields["protocol"].queryset) == [mine]

    def test_experiment_log_shows_protocol_link(self, client_logged_in):
        from django.urls import reverse

        from research.models import ExperimentEntry

        project = ProjectFactory()
        p = Protocol.objects.create(project=project, title="Lysis", body="x")
        ExperimentEntry.objects.create(project=project, title="Did it", protocol=p)
        body = client_logged_in.get(
            reverse("research:experiments", args=[project.slug])
        ).content.decode()
        assert "Lysis v1" in body
        assert f"#protocol-{p.pk}" in body

    def test_api_exposes_protocol_and_label(self, client):
        from research.models import ExperimentEntry

        project = ProjectFactory()
        p = Protocol.objects.create(project=project, title="PCR", body="x")
        ExperimentEntry.objects.create(project=project, title="Ran PCR", protocol=p)
        data = client.get(f"/api/v1/experiments/?project={project.slug}", **HEADERS).json()
        row = data["results"][0]
        assert row["protocol"] == p.pk
        assert row["protocol_label"] == "PCR v1"
