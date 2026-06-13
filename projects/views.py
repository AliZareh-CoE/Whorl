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
        from plans.selectors import project_progress

        ctx = super().get_context_data(**kwargs)
        active = [p for p in ctx["projects"] if p.status != Project.Status.ARCHIVED]
        for project in active:
            _, _, project.progress_percent = project_progress(project)
        ctx["active_projects"] = active
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
            "recent_documents": project.documents.general()[:5],
            "document_count": project.documents.general().count(),
            "next_deadline_manuscript": project.manuscripts.filter(deadline__isnull=False)
            .exclude(status__in=["published", "shelved"])
            .order_by("deadline")
            .first(),
        },
    )


def project_graph_page(request, slug):
    from literature.models import CitationSyncState

    project = get_object_or_404(Project, slug=slug)
    sync_state = CitationSyncState.objects.filter(project=project).first()
    return render(
        request,
        "projects/graph.html",
        {"project": project, "sync_state": sync_state},
    )


def project_graph_json(request, slug):
    from django.http import JsonResponse

    from core.graph import project_graph

    project = get_object_or_404(Project, slug=slug)
    return JsonResponse(project_graph(project))


@require_POST
def project_graph_sync(request, slug):
    from literature.models import CitationSyncState
    from literature.tasks import sync_citations_task

    project = get_object_or_404(Project, slug=slug)
    state, _ = CitationSyncState.objects.get_or_create(project=project)
    state.status = CitationSyncState.Status.SYNCING
    state.message = "Queued"
    state.save()
    sync_citations_task(project.pk)
    messages.success(request, "Citation sync started.")
    return redirect("projects:graph", slug=project.slug)


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
