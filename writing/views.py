from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, UpdateView

from projects.models import Project
from projects.views import ProjectScopedMixin

from . import services
from .forms import CiteCheckForm, ManuscriptForm, ManuscriptReferenceForm, SubmissionEventForm
from .models import Manuscript, ManuscriptReference, SubmissionEvent

STATUS_ORDER = [status.value for status in Manuscript.Status]


def writing_home(request):
    """Global writing board: every manuscript across projects, grouped by status."""
    manuscripts = Manuscript.objects.select_related("project")
    columns = _status_columns(manuscripts)
    return render(request, "writing/home.html", {"columns": columns})


def _status_columns(manuscripts):
    by_status: dict[str, list] = {}
    for manuscript in manuscripts:
        by_status.setdefault(manuscript.status, []).append(manuscript)
    return [
        {"status": status, "label": Manuscript.Status(status).label, "items": by_status[status]}
        for status in STATUS_ORDER
        if status in by_status
    ]


def project_writing(request, slug):
    project = get_object_or_404(Project, slug=slug)
    columns = _status_columns(project.manuscripts.all())
    return render(request, "writing/project_writing.html", {"project": project, "columns": columns})


def manuscript_detail(request, slug, pk):
    from core.comments import comments_for

    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    cite_form = CiteCheckForm()
    cite_result = None
    if request.method == "POST":
        cite_form = CiteCheckForm(request.POST, request.FILES)
        if cite_form.is_valid():
            cite_result = services.check_citations(manuscript, cite_form.cleaned_data["tex"])
    return render(
        request,
        "writing/manuscript_detail.html",
        {
            "project": project,
            "manuscript": manuscript,
            "bibliography": manuscript.manuscriptreference_set.select_related("reference"),
            "events": manuscript.events.all(),
            "event_form": SubmissionEventForm(),
            "cite_form": cite_form,
            "cite_result": cite_result,
            "bib_report": services.manuscript_bib_report(manuscript),
            "comments": comments_for(manuscript),
        },
    )


class ManuscriptFormMixin(ProjectScopedMixin):
    model = Manuscript
    form_class = ManuscriptForm
    template_name = "writing/manuscript_form.html"


class ManuscriptCreateView(ManuscriptFormMixin, CreateView):
    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class ManuscriptUpdateView(ManuscriptFormMixin, UpdateView):
    def get_queryset(self):
        return self.project.manuscripts.all()


class ManuscriptDeleteView(ProjectScopedMixin, DeleteView):
    model = Manuscript
    template_name = "writing/manuscript_confirm_delete.html"

    def get_queryset(self):
        return self.project.manuscripts.all()

    def get_success_url(self):
        return reverse("writing:project", kwargs={"slug": self.project.slug})


def latex_editor(request, slug, pk):
    """In-browser LaTeX editor with cite-key autocomplete (Owner idea #9, slice 1)."""
    import json

    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    cite_result = None
    if request.method == "POST":
        manuscript.latex_source = request.POST.get("latex_source", "")
        manuscript.save(update_fields=["latex_source", "updated_at"])
        messages.success(request, "Source saved.")
        if manuscript.latex_source.strip():
            cite_result = services.check_citations(manuscript, manuscript.latex_source)
    cite_keys = [
        link.cite_key for link in manuscript.manuscriptreference_set.select_related("reference")
    ]
    return render(
        request,
        "writing/latex_editor.html",
        {
            "project": project,
            "manuscript": manuscript,
            "cite_keys_json": json.dumps(sorted(cite_keys)),
            "cite_result": cite_result,
        },
    )


def add_reference(request, slug, pk):
    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    form = ManuscriptReferenceForm(request.POST or None, manuscript=manuscript)
    if request.method == "POST" and form.is_valid():
        link = form.save(commit=False)
        link.manuscript = manuscript
        link.save()
        messages.success(request, f"Added {link.cite_key} to the bibliography.")
        return redirect(manuscript.get_absolute_url())
    return render(
        request,
        "writing/add_reference.html",
        {"project": project, "manuscript": manuscript, "form": form},
    )


def remove_reference(request, slug, pk, link_pk):
    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    link = get_object_or_404(ManuscriptReference, pk=link_pk, manuscript=manuscript)
    if request.method == "POST":
        link.delete()
        messages.success(request, "Removed from bibliography.")
    return redirect(manuscript.get_absolute_url())


def export_bib(request, slug, pk):
    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    response = HttpResponse(
        services.export_manuscript_bib(manuscript), content_type="application/x-bibtex"
    )
    response["Content-Disposition"] = f'attachment; filename="manuscript-{manuscript.pk}.bib"'
    return response


def add_event(request, slug, pk):
    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    if request.method == "POST":
        form = SubmissionEventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.manuscript = manuscript
            event.save()
            messages.success(request, "Event logged.")
        else:
            messages.error(request, "Could not log event — check the fields.")
    return redirect(manuscript.get_absolute_url())


def delete_event(request, slug, pk, event_pk):
    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    event = get_object_or_404(SubmissionEvent, pk=event_pk, manuscript=manuscript)
    if request.method == "POST":
        event.delete()
        messages.success(request, "Event removed.")
    return redirect(manuscript.get_absolute_url())
