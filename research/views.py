from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, UpdateView

from projects.models import Project
from projects.views import ProjectScopedMixin

from .forms import (
    DatasetForm,
    EvidenceForm,
    ExperimentEntryForm,
    HypothesisForm,
    ProtocolForm,
)
from .models import Dataset, Evidence, ExperimentEntry, Hypothesis, Protocol


def hypothesis_ledger(request, slug):
    project = get_object_or_404(Project, slug=slug)
    return render(
        request,
        "research/ledger.html",
        {
            "project": project,
            "hypotheses": project.hypotheses.prefetch_related(
                "evidence__reference", "evidence__note", "evidence__document"
            ),
        },
    )


def experiment_log(request, slug):
    project = get_object_or_404(Project, slug=slug)
    return render(
        request,
        "research/experiments.html",
        {
            "project": project,
            "entries": project.experiment_entries.select_related("protocol").prefetch_related(
                "hypotheses"
            ),
        },
    )


def dataset_list(request, slug):
    project = get_object_or_404(Project, slug=slug)
    return render(
        request, "research/datasets.html", {"project": project, "datasets": project.datasets.all()}
    )


def _ledger_url(project):
    return reverse("research:ledger", kwargs={"slug": project.slug})


class HypothesisFormMixin(ProjectScopedMixin):
    model = Hypothesis
    form_class = HypothesisForm
    template_name = "research/form.html"
    extra_context = {"heading": "Hypothesis"}

    def get_success_url(self):
        return _ledger_url(self.project)


class HypothesisCreateView(HypothesisFormMixin, CreateView):
    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class HypothesisUpdateView(HypothesisFormMixin, UpdateView):
    def get_queryset(self):
        return self.project.hypotheses.all()


class HypothesisDeleteView(ProjectScopedMixin, DeleteView):
    model = Hypothesis
    template_name = "research/confirm_delete.html"

    def get_queryset(self):
        return self.project.hypotheses.all()

    def get_success_url(self):
        return _ledger_url(self.project)


def evidence_create(request, slug, hypothesis_pk):
    project = get_object_or_404(Project, slug=slug)
    hypothesis = get_object_or_404(project.hypotheses, pk=hypothesis_pk)
    form = EvidenceForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        evidence = form.save(commit=False)
        evidence.hypothesis = hypothesis
        evidence.save()
        suggestion = hypothesis.suggested_status
        if suggestion and suggestion != hypothesis.status:
            messages.info(
                request,
                f"Evidence balance now suggests “{Hypothesis.Status(suggestion).label}” — "
                "set it on the hypothesis if you agree.",
            )
        return redirect(_ledger_url(project))
    return render(
        request,
        "research/form.html",
        {"project": project, "form": form, "heading": f"Evidence for: {hypothesis}"},
    )


def evidence_delete(request, slug, pk):
    project = get_object_or_404(Project, slug=slug)
    evidence = get_object_or_404(Evidence, pk=pk, hypothesis__project=project)
    if request.method == "POST":
        evidence.delete()
    return redirect(_ledger_url(project))


class ExperimentFormMixin(ProjectScopedMixin):
    model = ExperimentEntry
    form_class = ExperimentEntryForm
    template_name = "research/form.html"
    extra_context = {"heading": "Experiment entry"}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def get_success_url(self):
        return reverse("research:experiments", kwargs={"slug": self.project.slug})


class ExperimentCreateView(ExperimentFormMixin, CreateView):
    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class ExperimentUpdateView(ExperimentFormMixin, UpdateView):
    def get_queryset(self):
        return self.project.experiment_entries.all()


class ExperimentDeleteView(ProjectScopedMixin, DeleteView):
    model = ExperimentEntry
    template_name = "research/confirm_delete.html"

    def get_queryset(self):
        return self.project.experiment_entries.all()

    def get_success_url(self):
        return reverse("research:experiments", kwargs={"slug": self.project.slug})


class DatasetFormMixin(ProjectScopedMixin):
    model = Dataset
    form_class = DatasetForm
    template_name = "research/form.html"
    extra_context = {"heading": "Dataset"}

    def get_success_url(self):
        return reverse("research:datasets", kwargs={"slug": self.project.slug})


class DatasetCreateView(DatasetFormMixin, CreateView):
    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class DatasetUpdateView(DatasetFormMixin, UpdateView):
    def get_queryset(self):
        return self.project.datasets.all()


class DatasetDeleteView(ProjectScopedMixin, DeleteView):
    model = Dataset
    template_name = "research/confirm_delete.html"

    def get_queryset(self):
        return self.project.datasets.all()

    def get_success_url(self):
        return reverse("research:datasets", kwargs={"slug": self.project.slug})


def _protocols_url(project):
    return reverse("research:protocols", kwargs={"slug": project.slug})


def protocol_list(request, slug):
    """Current protocols (the head of each version chain) with their version history.

    All of a project's protocols load in one query; the "current" heads (no later version
    names them as parent) and each head's version history are derived in memory — no per-row
    is_current exists() or parent-walk queries (AUDIT #24).
    """
    project = get_object_or_404(Project, slug=slug)
    all_protocols = list(project.protocols.all())
    by_pk = {p.pk: p for p in all_protocols}
    superseded = {p.parent_id for p in all_protocols if p.parent_id}
    current = [p for p in all_protocols if p.pk not in superseded]
    for protocol in current:
        chain, node_id = [], protocol.parent_id
        while node_id is not None and node_id in by_pk:
            node = by_pk[node_id]
            chain.append(node)
            node_id = node.parent_id
        protocol.lineage_cached = chain  # template uses this — zero extra queries
    return render(request, "research/protocols.html", {"project": project, "protocols": current})


class ProtocolCreateView(ProjectScopedMixin, CreateView):
    model = Protocol
    form_class = ProtocolForm
    template_name = "research/form.html"
    extra_context = {"heading": "Protocol"}

    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)

    def get_success_url(self):
        return _protocols_url(self.project)


def protocol_new_version(request, slug, pk):
    """Revise a protocol: GET shows a form prefilled with the current version, POST creates
    the next version (append-only history)."""
    project = get_object_or_404(Project, slug=slug)
    current = get_object_or_404(project.protocols, pk=pk)
    if request.method == "POST":
        form = ProtocolForm(request.POST)
        if form.is_valid():
            current.new_version(title=form.cleaned_data["title"], body=form.cleaned_data["body"])
            return redirect(_protocols_url(project))
    else:
        form = ProtocolForm(initial={"title": current.title, "body": current.body})
    return render(
        request,
        "research/form.html",
        {"project": project, "form": form, "heading": f"New version of: {current.title}"},
    )
