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
    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    main = manuscript.ensure_main_file()  # workbench: bootstrap main.tex lazily
    cite_result = None
    if request.method == "POST":
        manuscript.latex_source = request.POST.get("latex_source", "")
        manuscript.save(update_fields=["latex_source", "updated_at"])
        if manuscript.latex_source.strip():
            cite_result = services.check_citations(manuscript, manuscript.latex_source)
        if request.headers.get("X-SPA"):  # epic slice 2: autosave without a page reload
            from django.http import JsonResponse

            return JsonResponse(
                {
                    "saved": True,
                    "cite": {
                        "missing_from_bib": len(cite_result["missing_from_bib"])
                        if cite_result
                        else 0,
                        "uncited_in_bib": len(cite_result["uncited_in_bib"]) if cite_result else 0,
                    },
                }
            )
        messages.success(request, "Source saved.")
    cite_keys = [
        link.cite_key for link in manuscript.manuscriptreference_set.select_related("reference")
    ]
    from django.urls import reverse

    return render(
        request,
        "writing/latex_editor.html",
        {
            "project": project,
            "manuscript": manuscript,
            "cite_keys": sorted(cite_keys),
            "cite_result": cite_result,
            "editor_config": {
                "editorUrl": reverse("writing:editor", args=[slug, manuscript.pk]),
                "compileUrl": reverse("writing:compile", args=[slug, manuscript.pk]),
                "statusUrl": reverse("writing:compile_status", args=[slug, manuscript.pk]),
                "hasPdf": bool(manuscript.compiled_pdf),
                "pdfUrl": manuscript.compiled_pdf.url if manuscript.compiled_pdf else "",
                "compileRunning": manuscript.compile_status == "running",
                # workbench (slice 6)
                "filesUrl": reverse("writing:files", args=[slug, manuscript.pk]),
                "fileUrlBase": reverse("writing:files", args=[slug, manuscript.pk]),
                "wordCountUrl": reverse("writing:word_count", args=[slug, manuscript.pk]),
                "files": [_file_dict(f) for f in manuscript.files.all()],
                "mainFileId": main.pk,
            },
        },
    )


def compile_manuscript_view(request, slug, pk):
    """Save the latest source, then queue a background compile."""
    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    if request.method != "POST":
        return redirect("writing:editor", slug=slug, pk=pk)
    source = request.POST.get("latex_source")
    if source is not None:
        manuscript.latex_source = source
    manuscript.compile_generation += 1
    manuscript.compile_status = manuscript.CompileStatus.RUNNING
    manuscript.save()
    from .tasks import compile_manuscript_task

    compile_manuscript_task(manuscript.pk, manuscript.compile_generation)
    if request.headers.get("X-SPA"):  # epic slice 2: compile without a page reload
        from django.http import JsonResponse

        return JsonResponse({"status": "running"})
    messages.info(request, "Compiling in the background — refresh in a few seconds.")
    return redirect("writing:editor", slug=slug, pk=pk)


def compile_status(request, slug, pk):
    """JSON status for the editor's compile polling."""
    from django.http import JsonResponse

    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    return JsonResponse(
        {
            "status": manuscript.compile_status,
            "compiled_at": manuscript.compiled_at.isoformat() if manuscript.compiled_at else None,
            "pdf_url": manuscript.compiled_pdf.url if manuscript.compiled_pdf else None,
            "log": manuscript.compile_log[-3000:] if manuscript.compile_status == "failed" else "",
            "diagnostics": manuscript.compile_diagnostics,
        }
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


# --- multi-file workbench endpoints (Owner idea #24 slice 6) ---


def _file_dict(f):
    data = {"id": f.pk, "path": f.path, "kind": f.kind, "is_main": f.is_main}
    if f.kind == "asset" and f.asset:
        data["url"] = f.asset.url
        data["size"] = f.asset.size
    return data


def _workbench_objects(slug, pk, file_pk=None):
    project = get_object_or_404(Project, slug=slug)
    manuscript = get_object_or_404(project.manuscripts, pk=pk)
    if file_pk is None:
        return manuscript, None
    return manuscript, get_object_or_404(manuscript.files, pk=file_pk)


def manuscript_files(request, slug, pk):
    """GET: list files. POST: create an empty text file."""
    from django.core.exceptions import ValidationError
    from django.http import JsonResponse

    from .models import ManuscriptFile, kind_for_path, validate_manuscript_path

    manuscript, _ = _workbench_objects(slug, pk)
    if request.method == "POST":
        path = request.POST.get("path", "").strip()
        try:
            validate_manuscript_path(path)
        except ValidationError as exc:
            return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
        if kind_for_path(path) == ManuscriptFile.Kind.ASSET:
            return JsonResponse({"error": "Binary files go through upload."}, status=400)
        if manuscript.files.filter(path=path).exists():
            return JsonResponse({"error": "That path already exists."}, status=400)
        f = ManuscriptFile.objects.create(manuscript=manuscript, path=path)
        return JsonResponse(_file_dict(f), status=201)
    return JsonResponse({"files": [_file_dict(f) for f in manuscript.files.all()]})


def file_upload(request, slug, pk):
    """POST multipart: upload an asset (or a text file, which lands as content)."""
    from django.core.exceptions import ValidationError
    from django.http import JsonResponse

    from core.security import validate_upload_size

    from .models import ManuscriptFile, kind_for_path, validate_manuscript_path

    manuscript, _ = _workbench_objects(slug, pk)
    upload = request.FILES.get("file")
    if request.method != "POST" or upload is None:
        return JsonResponse({"error": "POST a file."}, status=400)
    path = (request.POST.get("path") or upload.name).strip().replace(" ", "_")
    try:
        validate_manuscript_path(path)
        validate_upload_size(upload)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    if manuscript.files.filter(path=path).exists():
        return JsonResponse({"error": "That path already exists."}, status=400)
    kind = kind_for_path(path)
    if kind == ManuscriptFile.Kind.ASSET:
        suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if suffix not in {"png", "jpg", "jpeg", "pdf", "eps", "svg", "csv", "txt"}:
            return JsonResponse({"error": f"File type .{suffix} not allowed."}, status=400)
        f = ManuscriptFile.objects.create(manuscript=manuscript, path=path, asset=upload)
    else:
        try:
            content = upload.read().decode("utf-8")
        except UnicodeDecodeError:
            return JsonResponse({"error": "Text file must be UTF-8."}, status=400)
        f = ManuscriptFile.objects.create(manuscript=manuscript, path=path, content=content)
    return JsonResponse(_file_dict(f), status=201)


def file_content(request, slug, pk, file_pk):
    from django.http import JsonResponse

    _, f = _workbench_objects(slug, pk, file_pk)
    data = _file_dict(f)
    if f.kind != "asset":
        data["content"] = f.content
    return JsonResponse(data)


def file_save(request, slug, pk, file_pk):
    from django.http import JsonResponse
    from django.views.decorators.http import require_POST  # noqa: F401  (parity w/ siblings)

    manuscript, f = _workbench_objects(slug, pk, file_pk)
    if request.method != "POST":
        return JsonResponse({"error": "POST only."}, status=405)
    if f.kind == "asset":
        return JsonResponse({"error": "Assets are not editable."}, status=400)
    f.content = request.POST.get("content", "")
    f.save()
    payload = {"saved": True}
    if f.kind == "tex":
        result = services.check_citations(manuscript, f.content)
        payload["cite"] = {
            "missing_from_bib": len(result["missing_from_bib"]),
            "uncited_in_bib": len(result["uncited_in_bib"]),
        }
    return JsonResponse(payload)


def file_rename(request, slug, pk, file_pk):
    from django.core.exceptions import ValidationError
    from django.http import JsonResponse

    from .models import kind_for_path, validate_manuscript_path

    manuscript, f = _workbench_objects(slug, pk, file_pk)
    if request.method != "POST":
        return JsonResponse({"error": "POST only."}, status=405)
    path = request.POST.get("path", "").strip()
    try:
        validate_manuscript_path(path)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    if manuscript.files.filter(path=path).exclude(pk=f.pk).exists():
        return JsonResponse({"error": "That path already exists."}, status=400)
    if kind_for_path(path) != f.kind:
        return JsonResponse({"error": "Rename must keep the file type."}, status=400)
    f.path = path
    f.save()
    return JsonResponse(_file_dict(f))


def word_count_view(request, slug, pk):
    """Approximate word count across all text files of the manuscript (slice 8)."""
    from django.http import JsonResponse

    from .wordcount import word_count

    manuscript, _ = _workbench_objects(slug, pk)
    files = manuscript.files.filter(kind__in=["tex"])
    if files.exists():
        source = "\n".join(f.content for f in files)
    else:
        source = manuscript.latex_source
    return JsonResponse(word_count(source))


def file_delete(request, slug, pk, file_pk):
    from django.http import JsonResponse

    _, f = _workbench_objects(slug, pk, file_pk)
    if request.method != "POST":
        return JsonResponse({"error": "POST only."}, status=405)
    if f.is_main:
        return JsonResponse(
            {"error": "The main file can't be deleted — rename it instead."}, status=400
        )
    if f.asset:
        f.asset.delete(save=False)
    f.delete()
    return JsonResponse({"deleted": True})
