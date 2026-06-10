import pytest
from django.urls import reverse

from projects.models import Project

from .factories import DecisionRecordFactory, ProjectFactory

pytestmark = pytest.mark.django_db


class TestProjectModel:
    def test_slug_generated_from_name(self):
        project = Project.objects.create(name="Deep Learning Survey")
        assert project.slug == "deep-learning-survey"

    def test_slug_collision_gets_suffix(self):
        Project.objects.create(name="Atlas")
        second = Project.objects.create(name="Atlas")
        assert second.slug == "atlas-2"

    def test_ordering_by_position_then_name(self):
        b = ProjectFactory(name="B", position=0)
        a = ProjectFactory(name="A", position=1)
        c = ProjectFactory(name="C", position=0)
        assert list(Project.objects.all()) == [b, c, a]


class TestProjectViews:
    def test_list_shows_projects_and_splits_archived(self, client_logged_in):
        active = ProjectFactory(name="Active One")
        archived = ProjectFactory(name="Old One", status=Project.Status.ARCHIVED)
        response = client_logged_in.get(reverse("projects:list"))
        assert response.status_code == 200
        assert active.name.encode() in response.content
        assert archived.name.encode() in response.content
        assert b"Archived" in response.content

    def test_create_project(self, client_logged_in):
        response = client_logged_in.post(
            reverse("projects:create"),
            {
                "name": "New Project",
                "description": "About things.",
                "status": "active",
                "color": "#4f46e5",
                "position": 0,
            },
        )
        project = Project.objects.get(name="New Project")
        assert response.status_code == 302
        assert response.url == project.get_absolute_url()

    def test_overview_renders(self, client_logged_in):
        project = ProjectFactory(description="**bold** plan")
        response = client_logged_in.get(project.get_absolute_url())
        assert response.status_code == 200
        assert b"<strong>bold</strong>" in response.content

    def test_archive_action(self, client_logged_in):
        project = ProjectFactory()
        response = client_logged_in.post(reverse("projects:archive", args=[project.slug]))
        project.refresh_from_db()
        assert response.status_code == 302
        assert project.status == Project.Status.ARCHIVED

    def test_delete_project(self, client_logged_in):
        project = ProjectFactory()
        client_logged_in.post(reverse("projects:delete", args=[project.slug]))
        assert not Project.objects.filter(pk=project.pk).exists()


class TestDecisionViews:
    def test_decision_list_renders(self, client_logged_in):
        decision = DecisionRecordFactory(title="Use Postgres")
        url = reverse("projects:decisions", args=[decision.project.slug])
        response = client_logged_in.get(url)
        assert response.status_code == 200
        assert b"Use Postgres" in response.content

    def test_create_decision(self, client_logged_in):
        project = ProjectFactory()
        response = client_logged_in.post(
            reverse("projects:decision_create", args=[project.slug]),
            {
                "title": "Pick framework",
                "context": "",
                "decision": "Django.",
                "alternatives": "Flask",
                "decided_on": "2026-06-10",
            },
        )
        assert response.status_code == 302
        assert project.decisions.count() == 1

    def test_decision_scoped_to_project(self, client_logged_in):
        decision = DecisionRecordFactory()
        other = ProjectFactory()
        url = reverse("projects:decision_edit", args=[other.slug, decision.pk])
        assert client_logged_in.get(url).status_code == 404
