from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView

from projects.models import Project
from projects.views import ProjectScopedMixin

from . import services
from .forms import AddByIdentifierForm, BibtexImportForm, LinkReferenceForm, ReferenceForm
from .models import ProjectReference, Reference, ReviewMark, ReviewTheme


def library_index(request):
    references = Reference.objects.prefetch_related("project_links__project")
    query = request.GET.get("q", "").strip()
    if query:
        references = references.filter(
            Q(title__icontains=query)
            | Q(bibtex_key__icontains=query)
            | Q(venue__icontains=query)
            | Q(doi__icontains=query)
            | Q(authors__icontains=query)
        )
    return render(
        request,
        "literature/index.html",
        {
            "references": references[:200],
            "query": query,
            "total": Reference.objects.count(),
            "add_form": AddByIdentifierForm(),
        },
    )


def add_by_identifier(request):
    from django.conf import settings

    form = AddByIdentifierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reference, created = services.add_reference_by_identifier(
                form.cleaned_data["identifier"]
            )
        except services.MetadataError as exc:
            form.add_error("identifier", str(exc))
        else:
            if created and settings.ATLAS_AUTO_FETCH_PDF and not reference.pdf:
                from .tasks import fetch_oa_pdf_task

                fetch_oa_pdf_task(reference.pk)
                messages.info(request, "Looking for an open-access PDF in the background…")
            messages.success(
                request,
                f"{'Added' if created else 'Already in library'}: {reference.bibtex_key}",
            )
            return redirect(reference.get_absolute_url())
    return render(request, "literature/add_by_identifier.html", {"form": form})


def import_bibtex(request):
    form = BibtexImportForm(request.POST or None)
    imported = None
    if request.method == "POST" and form.is_valid():
        results = services.import_bibtex(form.cleaned_data["bibtex"])
        if not results:
            form.add_error("bibtex", "No BibTeX entries found in the pasted text.")
        else:
            imported = results
            created = sum(1 for _, c in results if c)
            messages.success(
                request,
                f"Imported {created} new reference(s); {len(results) - created} already existed.",
            )
    return render(request, "literature/import_bibtex.html", {"form": form, "imported": imported})


def reference_detail(request, pk):
    from core.comments import comments_for
    from core.keywords import extract_keywords

    from .related import related_references

    reference = get_object_or_404(Reference, pk=pk)
    return render(
        request,
        "literature/detail.html",
        {
            "reference": reference,
            "project_links": reference.project_links.select_related("project"),
            "bibtex": services.render_bibtex(reference),
            "available_projects": Project.objects.exclude(project_references__reference=reference),
            "related": related_references(reference),
            "keywords": extract_keywords(f"{reference.title}. {reference.abstract}", 6),
            "comments": comments_for(reference),
        },
    )


class ReferenceCreateView(CreateView):
    model = Reference
    form_class = ReferenceForm
    template_name = "literature/reference_form.html"


class ReferenceUpdateView(UpdateView):
    model = Reference
    form_class = ReferenceForm
    template_name = "literature/reference_form.html"


class ReferenceDeleteView(DeleteView):
    model = Reference
    template_name = "literature/confirm_delete.html"
    success_url = reverse_lazy("literature:index")


@require_POST
def link_to_project(request, pk):
    """Quick-link a reference to a project from the reference detail page."""
    reference = get_object_or_404(Reference, pk=pk)
    project = get_object_or_404(Project, slug=request.POST.get("project"))
    _, created = ProjectReference.objects.get_or_create(project=project, reference=reference)
    messages.success(
        request,
        f"{'Linked' if created else 'Already linked'} to {project.name}.",
    )
    return redirect(reference.get_absolute_url())


def discover_panel(request, pk):
    """HTMX: related papers from OpenAlex that aren't in the library yet."""
    from . import discover

    reference = get_object_or_404(Reference, pk=pk)
    try:
        results = discover.discover_similar(reference)
    except Exception:
        results = None  # network trouble — render the panel's error state
    return render(
        request,
        "literature/_discover.html",
        {"reference": reference, "results": results},
    )


@require_POST
def discover_add(request, pk):
    """Add one discovered DOI to the library (background PDF fetch applies as usual)."""
    from django.conf import settings
    from django.http import JsonResponse

    get_object_or_404(Reference, pk=pk)  # anchor must exist
    doi = request.POST.get("doi", "").strip()
    if not doi:
        return JsonResponse({"error": "Missing DOI."}, status=400)
    try:
        new_ref, created = services.add_reference_by_identifier(doi)
    except services.MetadataError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    if created and settings.ATLAS_AUTO_FETCH_PDF and not new_ref.pdf:
        from .tasks import fetch_oa_pdf_task

        fetch_oa_pdf_task(new_ref.pk)
    return JsonResponse(
        {"url": new_ref.get_absolute_url(), "bibtex_key": new_ref.bibtex_key, "created": created}
    )


@require_POST
def fetch_pdf(request, pk):
    """Manual 'Fetch open-access PDF' from the reference detail page (synchronous)."""
    from .oa import fetch_and_attach_pdf

    reference = get_object_or_404(Reference, pk=pk)
    outcome = fetch_and_attach_pdf(reference)
    (messages.success if "attached" in outcome else messages.info)(request, outcome)
    return redirect(reference.get_absolute_url())


def read_pdf(request, pk):
    from core.comments import comments_for

    reference = get_object_or_404(Reference, pk=pk)
    if not reference.pdf:
        messages.error(request, "No PDF attached to this reference yet.")
        return redirect(reference.get_absolute_url())
    return render(
        request,
        "literature/read.html",
        {
            "reference": reference,
            "linked_projects": Project.objects.filter(project_references__reference=reference),
            "page_comments": comments_for(reference).filter(page__isnull=False),
        },
    )


@require_POST
def save_highlight(request, pk):
    from django.http import JsonResponse

    from notes.services import add_highlight_note

    reference = get_object_or_404(Reference, pk=pk)
    project = get_object_or_404(
        Project, slug=request.POST.get("project"), project_references__reference=reference
    )
    text = request.POST.get("text", "").strip()
    if not text:
        return JsonResponse({"error": "Empty selection."}, status=400)
    if len(text) > 2000:
        return JsonResponse(
            {"error": "Selection too long — highlight at most 2000 characters."}, status=400
        )
    page = request.POST.get("page")
    note = add_highlight_note(reference, project, text, int(page) if page else None)
    return JsonResponse({"note_id": note.pk, "note_url": note.get_absolute_url()})


def project_literature(request, slug):
    from django.db.models import Q as DQ

    from .selectors import project_keyword_cloud

    project = get_object_or_404(Project, slug=slug)
    links = project.project_references.select_related("reference")
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    keyword = request.GET.get("kw", "").strip()[:80]
    if status:
        links = links.filter(reading_status=status)
    if priority:
        links = links.filter(priority=priority)
    if keyword:
        links = links.filter(
            DQ(reference__title__icontains=keyword) | DQ(reference__abstract__icontains=keyword)
        )
    return render(
        request,
        "literature/project_literature.html",
        {
            "project": project,
            "links": links,
            "status": status,
            "priority": priority,
            "keyword": keyword,
            "cloud": project_keyword_cloud(project),
            "statuses": ProjectReference.ReadingStatus.choices,
            "priorities": ProjectReference.Priority.choices,
        },
    )


PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


def reading_queue(request, slug):
    from django.db.models import Count

    project = get_object_or_404(Project, slug=slug)
    keyword = request.GET.get("kw", "").strip()[:80]
    queue = project.project_references.filter(
        reading_status__in=[
            ProjectReference.ReadingStatus.TO_READ,
            ProjectReference.ReadingStatus.SKIMMED,
        ]
    )
    if keyword:
        from django.db.models import Q as DQ

        queue = queue.filter(
            DQ(reference__title__icontains=keyword) | DQ(reference__abstract__icontains=keyword)
        )
    order = request.GET.get("order", "")
    links = list(
        queue.select_related("reference")
        .prefetch_related("review_marks")
        .annotate(theme_coverage=Count("review_marks"))
    )
    if order == "gaps":
        from .selectors import annotate_gap_scores

        annotate_gap_scores(project, links)
        links.sort(
            key=lambda link: (
                link.gap_score is None,  # unmarked papers last
                link.gap_score or 0,
                PRIORITY_ORDER[link.priority],
                link.created_at,
            )
        )
    else:
        links.sort(key=lambda link: (PRIORITY_ORDER[link.priority], link.created_at))
    return render(
        request,
        "literature/reading_queue.html",
        {
            "project": project,
            "links": links,
            "keyword": keyword,
            "order": order,
            "statuses": ProjectReference.ReadingStatus.choices,
            "theme_count": project.review_themes.count(),
        },
    )


@require_POST
def set_reading_status(request, slug, pk):
    """HTMX inline status change from the queue/literature rows."""
    link = get_object_or_404(ProjectReference, pk=pk, project__slug=slug)
    status = request.POST.get("reading_status")
    if status in ProjectReference.ReadingStatus.values:
        link.reading_status = status
        link.save(update_fields=["reading_status", "updated_at"])
    return render(
        request,
        "literature/_link_row.html",
        {
            "link": link,
            "project": link.project,
            "statuses": ProjectReference.ReadingStatus.choices,
        },
    )


class ProjectReferenceCreateView(ProjectScopedMixin, CreateView):
    model = ProjectReference
    form_class = LinkReferenceForm
    template_name = "literature/link_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("literature:project", kwargs={"slug": self.project.slug})


class ProjectReferenceUpdateView(ProjectScopedMixin, UpdateView):
    model = ProjectReference
    form_class = LinkReferenceForm
    template_name = "literature/link_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def get_queryset(self):
        return self.project.project_references.all()

    def get_success_url(self):
        return reverse("literature:project", kwargs={"slug": self.project.slug})


class ProjectReferenceDeleteView(ProjectScopedMixin, DeleteView):
    model = ProjectReference
    template_name = "literature/link_confirm_delete.html"

    def get_queryset(self):
        return self.project.project_references.all()

    def get_success_url(self):
        return reverse("literature:project", kwargs={"slug": self.project.slug})


def review_matrix(request, slug):
    project = get_object_or_404(Project, slug=slug)
    themes = list(project.review_themes.all())
    links = list(project.project_references.select_related("reference"))
    marks = {
        (mark.theme_id, mark.project_reference_id): mark
        for mark in ReviewMark.objects.filter(theme__project=project)
    }
    rows = [
        {
            "link": link,
            "cells": [{"theme": theme, "mark": marks.get((theme.pk, link.pk))} for theme in themes],
        }
        for link in links
    ]
    return render(
        request,
        "literature/matrix.html",
        {"project": project, "themes": themes, "rows": rows},
    )


@require_POST
def toggle_mark(request, slug, theme_pk, link_pk):
    """HTMX: toggle one matrix cell on/off; returns the cell partial."""
    project = get_object_or_404(Project, slug=slug)
    theme = get_object_or_404(project.review_themes, pk=theme_pk)
    link = get_object_or_404(project.project_references, pk=link_pk)
    mark = ReviewMark.objects.filter(theme=theme, project_reference=link).first()
    if mark:
        mark.delete()
        mark = None
    else:
        mark = ReviewMark.objects.create(theme=theme, project_reference=link)
    return render(
        request,
        "literature/_matrix_cell.html",
        {"project": project, "cell": {"theme": theme, "mark": mark}, "link": link},
    )


def edit_mark_note(request, slug, pk):
    project = get_object_or_404(Project, slug=slug)
    mark = get_object_or_404(ReviewMark, pk=pk, theme__project=project)
    if request.method == "POST":
        mark.note = request.POST.get("note", "")[:300]
        mark.save(update_fields=["note", "updated_at"])
        return redirect("literature:matrix", slug=project.slug)
    return render(request, "literature/mark_note_form.html", {"project": project, "mark": mark})


class ThemeFormMixin(ProjectScopedMixin):
    model = ReviewTheme
    template_name = "literature/theme_form.html"

    def get_form_class(self):
        from .forms import ReviewThemeForm

        return ReviewThemeForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def get_success_url(self):
        return reverse("literature:matrix", kwargs={"slug": self.project.slug})


class ThemeCreateView(ThemeFormMixin, CreateView):
    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class ThemeUpdateView(ThemeFormMixin, UpdateView):
    def get_queryset(self):
        return self.project.review_themes.all()


class ThemeDeleteView(ProjectScopedMixin, DeleteView):
    model = ReviewTheme
    template_name = "literature/theme_confirm_delete.html"

    def get_queryset(self):
        return self.project.review_themes.all()

    def get_success_url(self):
        return reverse("literature:matrix", kwargs={"slug": self.project.slug})


def matrix_export_markdown(request, slug):
    """The review matrix as a markdown table — paste-able into anything, including Claude."""
    project = get_object_or_404(Project, slug=slug)
    themes = list(project.review_themes.all())
    marks = {
        (mark.theme_id, mark.project_reference_id): mark
        for mark in ReviewMark.objects.filter(theme__project=project)
    }
    lines = [
        "| Paper | " + " | ".join(t.name for t in themes) + " |",
        "|---" * (len(themes) + 1) + "|",
    ]
    for link in project.project_references.select_related("reference"):
        cells = []
        for theme in themes:
            mark = marks.get((theme.pk, link.pk))
            cells.append((mark.note or "✓") if mark else "")
        lines.append(f"| {link.reference.bibtex_key} | " + " | ".join(cells) + " |")
    response = HttpResponse("\n".join(lines), content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{project.slug}-review-matrix.md"'
    return response


def export_bib(request, slug):
    project = get_object_or_404(Project, slug=slug)
    content = services.export_project_bib(project)
    response = HttpResponse(content, content_type="application/x-bibtex")
    response["Content-Disposition"] = f'attachment; filename="{project.slug}.bib"'
    return response


def bib_report(request, slug):
    project = get_object_or_404(Project, slug=slug)
    references = Reference.objects.filter(project_links__project=project)
    include_network = "offline" not in request.GET
    report = services.run_bib_report(references, include_network_checks=include_network)
    return render(
        request,
        "literature/bib_report.html",
        {
            "project": project,
            "report": report,
            "include_network": include_network,
            "reference_count": references.count(),
        },
    )


@require_POST
def bulk_status(request, slug):
    """Set reading status on many linked papers at once (Owner idea #18)."""
    project = get_object_or_404(Project, slug=slug)
    status = request.POST.get("reading_status", "")
    valid = {value for value, _ in ProjectReference.ReadingStatus.choices}
    links = project.project_references.filter(pk__in=request.POST.getlist("ids"))
    if status not in valid:
        messages.error(request, "Pick a reading status.")
    elif not links:
        messages.error(request, "Nothing selected.")
    else:
        count = 0
        for link in links:  # per-row save keeps updated_at (ETags, pet) honest
            link.reading_status = status
            link.save(update_fields=["reading_status", "updated_at"])
            count += 1
        label = dict(ProjectReference.ReadingStatus.choices)[status]
        messages.success(request, f"Marked {count} paper(s) as {label}.")
    if request.headers.get("X-SPA") == "1":
        from django.contrib.messages import get_messages
        from django.http import JsonResponse

        summary = [m.message for m in get_messages(request)]
        return JsonResponse({"detail": summary[-1] if summary else "ok"})
    next_url = request.POST.get("next", "")
    if not (next_url.startswith("/") and not next_url.startswith("//")):
        next_url = reverse("literature:project", kwargs={"slug": slug})
    return redirect(next_url)
