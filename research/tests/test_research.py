import pytest
from django.urls import reverse

from projects.tests.factories import ProjectFactory
from research.models import Evidence, Hypothesis

pytestmark = pytest.mark.django_db


def make_hypothesis(**kwargs):
    return Hypothesis.objects.create(project=ProjectFactory(), statement="X causes Y", **kwargs)


class TestSuggestedStatus:
    def test_no_evidence_no_suggestion(self):
        assert make_hypothesis().suggested_status is None

    def test_all_supporting_suggests_supported(self):
        hypothesis = make_hypothesis()
        Evidence.objects.create(hypothesis=hypothesis, direction="supports", summary="a")
        Evidence.objects.create(hypothesis=hypothesis, direction="supports", summary="b")
        assert hypothesis.suggested_status == Hypothesis.Status.SUPPORTED

    def test_all_contradicting_suggests_contradicted(self):
        hypothesis = make_hypothesis()
        Evidence.objects.create(hypothesis=hypothesis, direction="contradicts", summary="a")
        assert hypothesis.suggested_status == Hypothesis.Status.CONTRADICTED

    def test_conflicting_or_mixed_suggests_inconclusive(self):
        hypothesis = make_hypothesis()
        Evidence.objects.create(hypothesis=hypothesis, direction="supports", summary="a")
        Evidence.objects.create(hypothesis=hypothesis, direction="contradicts", summary="b")
        assert hypothesis.suggested_status == Hypothesis.Status.INCONCLUSIVE
        other = make_hypothesis()
        Evidence.objects.create(hypothesis=other, direction="mixed", summary="c")
        assert other.suggested_status == Hypothesis.Status.INCONCLUSIVE

    def test_manual_status_not_overridden(self):
        hypothesis = make_hypothesis(status=Hypothesis.Status.ABANDONED)
        Evidence.objects.create(hypothesis=hypothesis, direction="supports", summary="a")
        hypothesis.refresh_from_db()
        assert hypothesis.status == Hypothesis.Status.ABANDONED


class TestResearchViews:
    def test_ledger_shows_balance_and_suggestion(self, client_logged_in):
        hypothesis = make_hypothesis()
        Evidence.objects.create(hypothesis=hypothesis, direction="supports", summary="strong pilot")
        response = client_logged_in.get(reverse("research:ledger", args=[hypothesis.project.slug]))
        content = response.content.decode()
        assert "1 supports" in content
        assert "balance suggests" in content
        assert "strong pilot" in content

    def test_add_evidence_via_view(self, client_logged_in):
        hypothesis = make_hypothesis()
        response = client_logged_in.post(
            reverse("research:evidence_create", args=[hypothesis.project.slug, hypothesis.pk]),
            {"direction": "supports", "summary": "from the view"},
        )
        assert response.status_code == 302
        assert hypothesis.evidence.count() == 1

    def test_experiment_log_renders(self, client_logged_in):
        from research.models import ExperimentEntry

        project = ProjectFactory()
        ExperimentEntry.objects.create(project=project, title="Run 1", body="**bold** outcome")
        response = client_logged_in.get(reverse("research:experiments", args=[project.slug]))
        assert b"Run 1" in response.content
        assert b"<strong>bold</strong>" in response.content

    def test_dataset_crud(self, client_logged_in):
        project = ProjectFactory()
        response = client_logged_in.post(
            reverse("research:dataset_create", args=[project.slug]),
            {
                "name": "eeg-v2",
                "location": "/data/eeg/v2",
                "version": "2",
                "checksum": "",
                "description": "",
            },
        )
        assert response.status_code == 302
        assert project.datasets.filter(name="eeg-v2").exists()


class TestDashboard:
    def test_dashboard_answers_today_everywhere(self, client_logged_in):
        import datetime

        from django.utils import timezone

        from plans.tests.factories import MilestoneFactory, PhaseFactory
        from writing.tests.factories import ManuscriptFactory

        project = ProjectFactory(name="Dash Project")
        phase = PhaseFactory(project=project, name="Field work", status="in_progress")
        MilestoneFactory(
            phase=phase,
            title="Dash Milestone",
            due_date=timezone.localdate() + datetime.timedelta(days=3),
        )
        ManuscriptFactory(
            project=project,
            title="Dash Paper",
            deadline=timezone.localdate() + datetime.timedelta(days=5),
        )
        response = client_logged_in.get(reverse("core:dashboard"))
        content = response.content.decode()
        assert "Dash Project" in content
        assert "Field work" in content
        assert "Dash Milestone" in content
        assert "Dash Paper" in content
        assert "papers read this month" in content
        assert "Activity" in content

    def test_heatmap_levels(self):
        from core.dashboard import activity_heatmap

        ProjectFactory()  # creates activity today
        weeks = activity_heatmap()
        cells = [cell for week in weeks for cell in week if not cell["future"]]
        assert any(cell["count"] > 0 for cell in cells)
        assert all(0 <= cell["level"] <= 4 for cell in cells)
