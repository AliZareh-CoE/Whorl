import pytest
from django.urls import reverse

from notes.tests.factories import NoteFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def endpoint(client, path):
    return client.get(reverse("core:assistant_context"), {"path": path})


class TestAssistantEndpoint:
    def test_requires_login(self, client):
        response = client.get(reverse("core:assistant_context"))
        assert response.status_code == 302
        assert reverse("login") in response["Location"]

    def test_generic_path(self, client_logged_in):
        response = endpoint(client_logged_in, "/")
        assert response.status_code == 200
        data = response.json()
        assert set(data) == {"context", "actions", "commands", "claude_prompt", "recent"}
        assert data["context"]["page"] == "core:spa_home"  # / is the SPA front door post-cutover
        assert "project" not in data["context"]
        labels = [action["label"] for action in data["actions"]]
        assert labels[:3] == ["New project", "Quick capture", "Search"]
        assert all(action["method"] == "get" for action in data["actions"])
        titles = [command["title"] for command in data["commands"]]
        assert "Dashboard" in titles
        assert "list_projects" in data["claude_prompt"]

    def test_unresolvable_path_is_best_effort(self, client_logged_in):
        data = endpoint(client_logged_in, "/no/such/page/").json()
        assert data["context"] == {"page": None}
        assert data["actions"]

    def test_project_path(self, client_logged_in):
        project = ProjectFactory(name="Coral Reef Mapping")
        plan_url = reverse("plans:plan", kwargs={"slug": project.slug})
        data = endpoint(client_logged_in, plan_url).json()

        assert data["context"]["page"] == "plans:plan"
        assert data["context"]["project"] == {
            "name": "Coral Reef Mapping",
            "slug": project.slug,
            "url": project.get_absolute_url(),
        }
        labels = [action["label"] for action in data["actions"]]
        for label in [
            "Open plan",
            "Literature",
            "Reading queue",
            "Bib report",
            "Figures",
            "New note",
        ]:
            assert label in labels
        # Figures is an SPA-only route; the action points at the in-app gallery path (#256-fu)
        figures = next(a for a in data["actions"] if a["label"] == "Figures")
        assert figures["url"] == f"/projects/{project.slug}/figures/"
        assert project.slug in data["claude_prompt"]
        assert len(data["claude_prompt"]) <= 600

    def test_commands_include_projects_and_notes(self, client_logged_in):
        project = ProjectFactory(name="Deep Sea Vents")
        notes = NoteFactory.create_batch(5, project=project)
        data = endpoint(client_logged_in, "/").json()
        commands = data["commands"]
        assert len(commands) <= 400
        titles = {command["title"] for command in commands}
        assert "Deep Sea Vents" in titles
        assert {note.title for note in notes} <= titles
        note_commands = [c for c in commands if c["type"] == "note"]
        assert note_commands[0]["url"] == reverse(
            "notes:detail", kwargs={"slug": project.slug, "pk": notes[-1].pk}
        )

    def test_recent_includes_project_note(self, client_logged_in):
        project = ProjectFactory()
        note = NoteFactory(project=project, title="Recent finding")
        overview_url = reverse("projects:overview", kwargs={"slug": project.slug})
        data = endpoint(client_logged_in, overview_url).json()
        match = [item for item in data["recent"] if item["title"] == "Recent finding"]
        assert match
        assert match[0]["type"] == "note"
        assert match[0]["url"] == note.get_absolute_url()
        assert match[0]["when"] == note.updated_at.date().isoformat()


def test_context_cacheable_repeat_calls_are_consistent(client_logged_in):
    """The SPA caches this per path (SWR); repeat calls must return stable shape."""
    a = endpoint(client_logged_in, "/").json()
    b = endpoint(client_logged_in, "/").json()
    assert set(a) == set(b) == {"context", "actions", "commands", "claude_prompt", "recent"}
