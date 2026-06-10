from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import DecisionRecordForm, ProjectForm
from .models import DecisionRecord, Project


class ProjectListView(ListView):
    model = Project
    context_object_name = "projects"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_projects"] = [p for p in ctx["projects"] if p.status != Project.Status.ARCHIVED]
        ctx["archived_projects"] = [
            p for p in ctx["projects"] if p.status == Project.Status.ARCHIVED
        ]
        return ctx


class ProjectCreateView(CreateView):
    model = Project
    form_class = ProjectForm


class ProjectUpdateView(UpdateView):
    model = Project
    form_class = ProjectForm
    slug_url_kwarg = "slug"


class ProjectDeleteView(DeleteView):
    model = Project
    slug_url_kwarg = "slug"
    success_url = reverse_lazy("projects:list")


@require_POST
def project_archive(request, slug):
    project = get_object_or_404(Project, slug=slug)
    project.status = Project.Status.ARCHIVED
    project.save()
    messages.success(request, f"Archived “{project.name}”.")
    return redirect("projects:list")


def project_overview(request, slug):
    from plans import selectors as plan_selectors

    project = get_object_or_404(Project, slug=slug)
    done, total, percent = plan_selectors.project_progress(project)
    return render(
        request,
        "projects/overview.html",
        {
            "project": project,
            "current_phase": plan_selectors.current_phase(project),
            "upcoming_milestones": plan_selectors.upcoming_milestones(project),
            "done": done,
            "total": total,
            "percent": percent,
            "recent_decisions": project.decisions.all()[:5],
            "decision_count": project.decisions.count(),
            "question_count": project.questions.count(),
            "phase_count": project.phases.count(),
            "recent_documents": project.documents.all()[:5],
            "document_count": project.documents.count(),
        },
    )


class ProjectScopedMixin:
    """Mixin for views that operate on objects belonging to one project."""

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(Project, slug=kwargs["slug"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        return ctx


class DecisionListView(ProjectScopedMixin, ListView):
    model = DecisionRecord
    context_object_name = "decisions"
    template_name = "projects/decision_list.html"

    def get_queryset(self):
        return self.project.decisions.all()


class DecisionFormMixin(ProjectScopedMixin):
    model = DecisionRecord
    form_class = DecisionRecordForm
    template_name = "projects/decision_form.html"

    def get_success_url(self):
        return reverse("projects:decisions", kwargs={"slug": self.project.slug})


class DecisionCreateView(DecisionFormMixin, CreateView):
    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class DecisionUpdateView(DecisionFormMixin, UpdateView):
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return self.project.decisions.all()


class DecisionDeleteView(ProjectScopedMixin, DeleteView):
    model = DecisionRecord
    template_name = "projects/decision_confirm_delete.html"

    def get_queryset(self):
        return self.project.decisions.all()

    def get_success_url(self):
        return reverse("projects:decisions", kwargs={"slug": self.project.slug})
