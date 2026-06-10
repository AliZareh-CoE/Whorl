from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from projects.views import ProjectScopedMixin

from . import selectors
from .forms import MilestoneForm, PhaseForm, ResearchQuestionForm, TaskForm
from .models import Milestone, Phase, ResearchQuestion, Task


def plan(request, slug):
    from projects.models import Project

    project = get_object_or_404(Project, slug=slug)
    done, total, percent = selectors.project_progress(project)
    return render(
        request,
        "plans/plan.html",
        {
            "project": project,
            "phases": selectors.plan_phases(project),
            "done": done,
            "total": total,
            "percent": percent,
        },
    )


def _plan_url(project):
    return reverse("plans:plan", kwargs={"slug": project.slug})


class PhaseFormMixin(ProjectScopedMixin):
    model = Phase
    form_class = PhaseForm
    template_name = "plans/phase_form.html"

    def get_success_url(self):
        return _plan_url(self.project)


class PhaseCreateView(PhaseFormMixin, CreateView):
    def get_initial(self):
        return {"order": self.project.phases.count() + 1}

    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class PhaseUpdateView(PhaseFormMixin, UpdateView):
    def get_queryset(self):
        return self.project.phases.all()


class PhaseDeleteView(ProjectScopedMixin, DeleteView):
    model = Phase
    template_name = "plans/confirm_delete.html"

    def get_queryset(self):
        return self.project.phases.all()

    def get_success_url(self):
        return _plan_url(self.project)


class MilestoneFormMixin(ProjectScopedMixin):
    model = Milestone
    form_class = MilestoneForm
    template_name = "plans/milestone_form.html"

    def get_success_url(self):
        return _plan_url(self.project)


class MilestoneCreateView(MilestoneFormMixin, CreateView):
    def get_phase(self):
        return get_object_or_404(self.project.phases, pk=self.kwargs["phase_pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["phase"] = self.get_phase()
        return ctx

    def form_valid(self, form):
        form.instance.phase = self.get_phase()
        return super().form_valid(form)


class MilestoneUpdateView(MilestoneFormMixin, UpdateView):
    def get_queryset(self):
        return Milestone.objects.filter(phase__project=self.project)


class MilestoneDeleteView(ProjectScopedMixin, DeleteView):
    model = Milestone
    template_name = "plans/confirm_delete.html"

    def get_queryset(self):
        return Milestone.objects.filter(phase__project=self.project)

    def get_success_url(self):
        return _plan_url(self.project)


class TaskFormMixin(ProjectScopedMixin):
    model = Task
    form_class = TaskForm
    template_name = "plans/task_form.html"

    def get_success_url(self):
        return _plan_url(self.project)


class TaskCreateView(TaskFormMixin, CreateView):
    def get_milestone(self):
        return get_object_or_404(
            Milestone, pk=self.kwargs["milestone_pk"], phase__project=self.project
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["milestone"] = self.get_milestone()
        return ctx

    def form_valid(self, form):
        form.instance.milestone = self.get_milestone()
        return super().form_valid(form)


class TaskUpdateView(TaskFormMixin, UpdateView):
    def get_queryset(self):
        return Task.objects.filter(milestone__phase__project=self.project)


class TaskDeleteView(ProjectScopedMixin, DeleteView):
    model = Task
    template_name = "plans/confirm_delete.html"

    def get_queryset(self):
        return Task.objects.filter(milestone__phase__project=self.project)

    def get_success_url(self):
        return _plan_url(self.project)


def _phase_card_response(request, phase):
    """HTMX partial: the updated phase card plus an OOB project progress bar."""
    project = phase.project
    done, total, percent = selectors.project_progress(project)
    return render(
        request,
        "plans/_phase_card_oob.html",
        {
            "project": project,
            "phase": phase,
            "done": done,
            "total": total,
            "percent": percent,
        },
    )


@require_POST
def milestone_toggle(request, slug, pk):
    milestone = get_object_or_404(
        Milestone.objects.select_related("phase__project"),
        pk=pk,
        phase__project__slug=slug,
    )
    milestone.toggle_completed()
    return _phase_card_response(request, milestone.phase)


@require_POST
def task_toggle(request, slug, pk):
    task = get_object_or_404(
        Task.objects.select_related("milestone__phase__project"),
        pk=pk,
        milestone__phase__project__slug=slug,
    )
    task.done = not task.done
    task.save(update_fields=["done", "updated_at"])
    return _phase_card_response(request, task.milestone.phase)


class QuestionListView(ProjectScopedMixin, ListView):
    model = ResearchQuestion
    context_object_name = "questions"
    template_name = "plans/question_list.html"

    def get_queryset(self):
        return self.project.questions.prefetch_related("phases")


class QuestionFormMixin(ProjectScopedMixin):
    model = ResearchQuestion
    form_class = ResearchQuestionForm
    template_name = "plans/question_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def get_success_url(self):
        return reverse("plans:questions", kwargs={"slug": self.project.slug})


class QuestionCreateView(QuestionFormMixin, CreateView):
    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class QuestionUpdateView(QuestionFormMixin, UpdateView):
    def get_queryset(self):
        return self.project.questions.all()


class QuestionDeleteView(ProjectScopedMixin, DeleteView):
    model = ResearchQuestion
    template_name = "plans/confirm_delete.html"

    def get_queryset(self):
        return self.project.questions.all()

    def get_success_url(self):
        return reverse("plans:questions", kwargs={"slug": self.project.slug})
