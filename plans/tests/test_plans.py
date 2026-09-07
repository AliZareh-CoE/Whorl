import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from plans import selectors
from plans.models import Phase
from projects.tests.factories import ProjectFactory

from .factories import MilestoneFactory, PhaseFactory, ResearchQuestionFactory, TaskFactory

pytestmark = pytest.mark.django_db


class TestProgressRollup:
    def test_phase_progress_from_milestones(self):
        phase = PhaseFactory()
        MilestoneFactory(phase=phase, completed_at=timezone.now())
        MilestoneFactory(phase=phase)
        MilestoneFactory(phase=phase)
        assert phase.milestone_counts == (1, 3)
        assert phase.progress == 33

    def test_phase_progress_empty(self):
        phase = PhaseFactory()
        assert phase.progress == 0

    def test_project_progress_rolls_up_across_phases(self):
        project = ProjectFactory()
        p1 = PhaseFactory(project=project, order=1)
        p2 = PhaseFactory(project=project, order=2)
        MilestoneFactory(phase=p1, completed_at=timezone.now())
        MilestoneFactory(phase=p1, completed_at=timezone.now())
        MilestoneFactory(phase=p2)
        MilestoneFactory(phase=p2)
        assert selectors.project_progress(project) == (2, 4, 50)

    def test_milestone_overdue(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        overdue = MilestoneFactory(due_date=yesterday)
        completed = MilestoneFactory(due_date=yesterday, completed_at=timezone.now())
        assert overdue.is_overdue
        assert not completed.is_overdue


class TestCurrentPhase:
    def test_prefers_in_progress(self):
        project = ProjectFactory()
        PhaseFactory(project=project, order=1, status=Phase.Status.DONE)
        active = PhaseFactory(project=project, order=2, status=Phase.Status.IN_PROGRESS)
        PhaseFactory(project=project, order=3)
        assert selectors.current_phase(project) == active

    def test_falls_back_to_first_unfinished(self):
        project = ProjectFactory()
        PhaseFactory(project=project, order=1, status=Phase.Status.DONE)
        nxt = PhaseFactory(project=project, order=2)
        assert selectors.current_phase(project) == nxt

    def test_all_done_returns_last(self):
        project = ProjectFactory()
        PhaseFactory(project=project, order=1, status=Phase.Status.DONE)
        last = PhaseFactory(project=project, order=2, status=Phase.Status.DONE)
        assert selectors.current_phase(project) == last

    def test_no_phases_returns_none(self):
        assert selectors.current_phase(ProjectFactory()) is None


class TestPlanPage:
    def test_plan_renders_phases_and_progress(self, client_logged_in):
        phase = PhaseFactory(name="Pilot study")
        MilestoneFactory(phase=phase, title="Collect data")
        response = client_logged_in.get(reverse("plans:plan", args=[phase.project.slug]))
        assert response.status_code == 200
        assert b"Pilot study" in response.content
        assert b"Collect data" in response.content
        assert b"0/1 milestones" in response.content

    def test_milestone_toggle_completes_and_uncompletes(self, client_logged_in):
        milestone = MilestoneFactory()
        url = reverse("plans:milestone_toggle", args=[milestone.phase.project.slug, milestone.pk])
        response = client_logged_in.post(url)
        milestone.refresh_from_db()
        assert response.status_code == 200
        assert milestone.completed_at is not None
        assert b"1/1 milestones" in response.content
        # completion fires the pet-hop event; un-checking stays quiet
        assert response.headers.get("HX-Trigger") == "atlas:milestone-completed"
        response = client_logged_in.post(url)
        milestone.refresh_from_db()
        assert milestone.completed_at is None
        assert "HX-Trigger" not in response.headers

    def test_pet_hop_listener_wired_in_base_template(self, client_logged_in):
        response = client_logged_in.get(reverse("core:dashboard"))
        content = response.content.decode()
        assert 'id="atlas-pet-emoji"' in content
        assert "atlas:milestone-completed" in content

    def test_milestone_toggle_scoped_to_project(self, client_logged_in):
        milestone = MilestoneFactory()
        other = ProjectFactory()
        url = reverse("plans:milestone_toggle", args=[other.slug, milestone.pk])
        assert client_logged_in.post(url).status_code == 404

    def test_task_toggle(self, client_logged_in):
        task = TaskFactory()
        slug = task.milestone.phase.project.slug
        response = client_logged_in.post(reverse("plans:task_toggle", args=[slug, task.pk]))
        task.refresh_from_db()
        assert response.status_code == 200
        assert task.done

    def test_create_phase(self, client_logged_in):
        project = ProjectFactory()
        response = client_logged_in.post(
            reverse("plans:phase_create", args=[project.slug]),
            {"name": "Phase one", "order": 1, "status": "not_started", "objective": ""},
        )
        assert response.status_code == 302
        assert project.phases.count() == 1

    def test_create_milestone(self, client_logged_in):
        phase = PhaseFactory()
        response = client_logged_in.post(
            reverse("plans:milestone_create", args=[phase.project.slug, phase.pk]),
            {"title": "Ship it", "notes": ""},
        )
        assert response.status_code == 302
        assert phase.milestones.count() == 1


class TestResearchQuestions:
    def test_question_list_renders(self, client_logged_in):
        question = ResearchQuestionFactory()
        response = client_logged_in.get(reverse("plans:questions", args=[question.project.slug]))
        assert response.status_code == 200
        assert question.question.encode() in response.content

    def test_question_list_shows_count(self, client_logged_in):
        project = ProjectFactory()
        ResearchQuestionFactory.create_batch(3, project=project)
        response = client_logged_in.get(reverse("plans:questions", args=[project.slug]))
        assert b"3 research questions." in response.content

    def test_create_question_linked_to_phase(self, client_logged_in):
        phase = PhaseFactory()
        project = phase.project
        response = client_logged_in.post(
            reverse("plans:question_create", args=[project.slug]),
            {"question": "Does X cause Y?", "status": "open", "phases": [phase.pk]},
        )
        assert response.status_code == 302
        question = project.questions.get()
        assert list(question.phases.all()) == [phase]

    def test_question_form_limits_phases_to_project(self, client_logged_in):
        phase = PhaseFactory()
        other_phase = PhaseFactory()
        response = client_logged_in.get(reverse("plans:question_create", args=[phase.project.slug]))
        form = response.context["form"]
        assert phase in form.fields["phases"].queryset
        assert other_phase not in form.fields["phases"].queryset


class TestOverviewIntegration:
    def test_overview_shows_current_phase_and_milestones(self, client_logged_in):
        project = ProjectFactory()
        phase = PhaseFactory(project=project, name="Analysis", status=Phase.Status.IN_PROGRESS)
        MilestoneFactory(phase=phase, title="Run regressions")
        response = client_logged_in.get(project.get_absolute_url())
        assert response.status_code == 200
        assert b"Analysis" in response.content
        assert b"Run regressions" in response.content
        assert b"0/1 milestones" in response.content


class TestModalForms:
    """Owner idea #18: form views render in the shared modal for HTMX requests."""

    def test_htmx_get_returns_modal_partial(self, client_logged_in):
        phase = PhaseFactory()
        url = reverse("plans:milestone_create", args=[phase.project.slug, phase.pk])
        response = client_logged_in.get(url, HTTP_HX_REQUEST="true")
        content = response.content.decode()
        assert 'role="dialog"' in content
        assert "<html" not in content  # partial, not a full page
        assert "Add milestone" in content

    def test_plain_get_still_returns_full_page(self, client_logged_in):
        phase = PhaseFactory()
        url = reverse("plans:milestone_create", args=[phase.project.slug, phase.pk])
        content = client_logged_in.get(url).content.decode()
        assert "<html" in content  # no-JS fallback unchanged
        assert 'role="dialog"' not in content

    def test_htmx_post_valid_redirects_via_header(self, client_logged_in):
        phase = PhaseFactory()
        url = reverse("plans:milestone_create", args=[phase.project.slug, phase.pk])
        response = client_logged_in.post(url, {"title": "From modal"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert response.headers["HX-Redirect"].endswith("/plan/")
        assert phase.milestones.filter(title="From modal").exists()

    def test_htmx_post_invalid_rerenders_modal_with_errors(self, client_logged_in):
        phase = PhaseFactory()
        url = reverse("plans:milestone_create", args=[phase.project.slug, phase.pk])
        response = client_logged_in.post(url, {"title": ""}, HTTP_HX_REQUEST="true")
        content = response.content.decode()
        assert response.status_code == 200
        assert 'role="dialog"' in content
        assert "required" in content.lower()

    def test_plan_links_open_in_modal(self, client_logged_in):
        phase = PhaseFactory()
        response = client_logged_in.get(reverse("plans:plan", args=[phase.project.slug]))
        content = response.content.decode()
        assert content.count('hx-target="#modal-slot"') >= 3
        assert 'id="modal-slot"' in content


def test_phase_reorder_and_milestone_move(client, settings, django_user_model):
    """#429: drag a phase to reorder it; drag a milestone onto another phase to move it."""
    from plans.models import Milestone, Phase
    from projects.tests.factories import ProjectFactory

    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    headers = {"HTTP_X_API_KEY": "k"}
    project = ProjectFactory(slug="deep")
    a, b, c = (
        Phase.objects.create(project=project, name=n, order=i) for i, n in enumerate("ABC", 1)
    )
    other = Phase.objects.create(project=ProjectFactory(slug="other"), name="X", order=1)
    r = client.post(
        f"/api/v1/projects/{project.slug}/phases/reorder/",
        {"ids": [c.pk, a.pk]},
        content_type="application/json",
        **headers,
    )
    assert r.status_code == 200 and r.json() == {"ordered": 2}
    assert list(project.phases.order_by("order").values_list("name", flat=True)) == ["C", "A", "B"]
    bad = client.post(
        f"/api/v1/projects/{project.slug}/phases/reorder/",
        {"ids": [other.pk]},
        content_type="application/json",
        **headers,
    )
    assert bad.status_code == 400
    m = Milestone.objects.create(phase=a, title="Pilot")
    moved = client.patch(
        f"/api/v1/milestones/{m.pk}/", {"phase": c.pk}, content_type="application/json", **headers
    )
    assert moved.status_code == 200 and Milestone.objects.get(pk=m.pk).phase_id == c.pk
    src = open("frontend/src/app/pages/Plan.tsx").read()
    assert "application/x-atlas-phase" in src and "application/x-atlas-milestone" in src
    assert "/phases/reorder/" in src
