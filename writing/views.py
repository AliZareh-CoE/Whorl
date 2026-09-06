from django.contrib import messages
from django.contrib.staticfiles.storage import staticfiles_storage
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
        starter = form.cleaned_data.get("starter")
        if starter:
            from .templates_gallery import template_body

            form.instance.latex_source = template_body(starter)
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
                "pdfjsBase": staticfiles_storage.url("vendor/pdfjs/"),  # vendored, no CDN
                "compileRunning": manuscript.compile_status == "running",
                # workbench (slice 6)
                "filesUrl": reverse("writing:files", args=[slug, manuscript.pk]),
                "fileUrlBase": reverse("writing:files", args=[slug, manuscript.pk]),
                "wordCountUrl": reverse("writing:word_count", args=[slug, manuscript.pk]),
                "citeLibraryUrl": reverse("writing:cite_library", args=[slug, manuscript.pk]),
                "projectSlug": slug,
                "contextUrl": reverse("writing:writing_context", args=[slug, manuscript.pk]),
                "revisionsUrl": reverse("writing:revisions", args=[slug, manuscript.pk]),
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


def export_submission_zip(request, slug, pk):
    """Beyond-Overleaf B7: a flattened arXiv-ready submission .zip of the manuscript's
    source tree + the generated references.bib. The thing every researcher zips by hand."""
    import io
    import zipfile

    from django.http import HttpResponse

    from .services import export_manuscript_bib

    manuscript, _ = _workbench_objects(slug, pk)

    def _safe(path: str) -> bool:
        # AUDIT #12: zip entries derive from validated paths, but defend in depth against
        # a row injected past validation — never emit a traversal/absolute archive name.
        return not (path.startswith("/") or path.startswith("\\") or ".." in path.split("/"))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        files = [f for f in manuscript.files.all() if _safe(f.path)]
        if files:
            for f in files:
                if f.kind == "asset" and f.asset:
                    with f.asset.open("rb") as src:
                        zf.writestr(f.path, src.read())
                else:
                    zf.writestr(f.path, f.content)
            has_bib = any(f.path == "references.bib" for f in files)
        else:
            zf.writestr("main.tex", manuscript.latex_source)
            has_bib = False
        # add the generated bibliography unless the user already ships one
        if not has_bib:
            bib = export_manuscript_bib(manuscript)
            if bib:
                zf.writestr("references.bib", bib)
    buffer.seek(0)
    slug_name = "".join(c if c.isalnum() else "-" for c in manuscript.title.lower())[:60].strip("-")
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{slug_name or "submission"}.zip"'
    return response


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
    manuscript.ensure_main_file()  # the studio lists files before anything else: bootstrap
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


def manuscript_revisions(request, slug, pk):
    """GET: list revisions. POST: snapshot the current tree with a label."""
    from django.http import JsonResponse

    from .models import snapshot_manuscript

    manuscript, _ = _workbench_objects(slug, pk)
    if request.method == "POST":
        label = request.POST.get("label", "").strip()[:200] or "Labeled version"
        rev = snapshot_manuscript(manuscript, label=label)
        return JsonResponse({"id": rev.pk, "label": rev.label}, status=201)
    revisions = [
        {
            "id": r.pk,
            "label": r.label,
            "labeled": r.is_labeled,
            "created_at": r.created_at.isoformat(),
            "files": sorted(r.files.keys()),
        }
        for r in manuscript.revisions.all()[:200]
    ]
    return JsonResponse({"revisions": revisions})


def revision_diff(request, slug, pk, rev_pk):
    """Unified diff of a revision against the manuscript's current text files."""
    import difflib

    from django.http import JsonResponse

    manuscript, _ = _workbench_objects(slug, pk)
    revision = get_object_or_404(manuscript.revisions, pk=rev_pk)
    current = {f.path: f.content for f in manuscript.files.filter(kind__in=["tex", "bib"])} or {
        "main.tex": manuscript.latex_source
    }
    diffs = []
    for path in sorted(set(revision.files) | set(current)):
        old = revision.files.get(path, "").splitlines()
        new = current.get(path, "").splitlines()
        if old == new:
            continue
        diff = list(
            difflib.unified_diff(
                old, new, fromfile=f"{path} (revision)", tofile=f"{path} (now)", lineterm=""
            )
        )
        diffs.append({"path": path, "diff": "\n".join(diff)})
    return JsonResponse({"diffs": diffs, "unchanged": not diffs})


def revision_restore(request, slug, pk, rev_pk):
    """Restore a revision's text files (snapshots current state first)."""
    from django.http import JsonResponse

    from .models import kind_for_path, snapshot_manuscript

    manuscript, _ = _workbench_objects(slug, pk)
    if request.method != "POST":
        return JsonResponse({"error": "POST only."}, status=405)
    revision = get_object_or_404(manuscript.revisions, pk=rev_pk)
    snapshot_manuscript(manuscript, label="Before restore")  # so a restore is itself undoable
    if manuscript.files.exists():
        for path, content in revision.files.items():
            obj, created = manuscript.files.get_or_create(
                path=path, defaults={"kind": kind_for_path(path), "content": content}
            )
            if not created and obj.content != content:
                obj.content = content
                obj.save()
    else:
        manuscript.latex_source = revision.files.get("main.tex", "")
        manuscript.save(update_fields=["latex_source", "updated_at"])
    return JsonResponse({"restored": True})


def writing_context(request, slug, pk):
    """Beyond-Overleaf B3: the writer's research beside the editor — bib, notes, hypotheses."""
    from django.http import JsonResponse

    manuscript, _ = _workbench_objects(slug, pk)
    project = manuscript.project

    bib = []
    for link in manuscript.manuscriptreference_set.select_related("reference"):
        ref = link.reference
        names = [a.get("family") or a.get("given") or "" for a in (ref.authors or [])]
        names = [n for n in names if n]
        head = ", ".join(names[:2]) + (" et al." if len(names) > 2 else "")
        bib.append(
            {
                "key": link.cite_key,
                "title": ref.title[:140],
                "authors": head,
                "year": ref.year,
                "abstract": (ref.abstract or "")[:280],
            }
        )
    bib.sort(key=lambda b: b["key"].lower())

    query = (request.GET.get("q") or "").strip()[:100]
    notes_qs = project.notes.all()
    if query:
        notes_qs = notes_qs.filter(title__icontains=query)
    notes = [{"id": n.pk, "title": n.title, "url": n.get_absolute_url()} for n in notes_qs[:30]]

    hypotheses = [
        {"id": h.pk, "statement": h.statement[:200], "status": h.status}
        for h in project.hypotheses.all()[:30]
    ]
    return JsonResponse({"bib": bib, "notes": notes, "hypotheses": hypotheses})


def cite_library(request, slug, pk):
    """Beyond-Overleaf B1: the whole project library for \cite{} autocomplete.

    GET → every project reference with metadata + whether it's already linked to this
    manuscript. POST {reference} → link an unlinked reference (auto-creates the
    ManuscriptReference so references.bib stays in sync without .bib babysitting).
    """
    from django.http import JsonResponse

    manuscript, _ = _workbench_objects(slug, pk)
    if request.method == "POST":
        ref_id = request.POST.get("reference")
        link = ManuscriptReference.objects.filter(
            manuscript=manuscript, reference_id=ref_id
        ).first()
        if link is None:
            from literature.models import Reference

            reference = get_object_or_404(
                Reference, pk=ref_id, project_links__project=manuscript.project
            )
            link = ManuscriptReference.objects.create(manuscript=manuscript, reference=reference)
        return JsonResponse({"key": link.cite_key, "linked": True}, status=201)

    linked_ids = set(manuscript.manuscriptreference_set.values_list("reference_id", flat=True))

    def author_line(authors):
        names = [a.get("family") or a.get("given") or "" for a in (authors or [])]
        names = [n for n in names if n]
        head = ", ".join(names[:2])
        return f"{head} et al." if len(names) > 2 else head

    candidates = []
    links = manuscript.project.project_references.select_related("reference")
    for pr in links:
        ref = pr.reference
        candidates.append(
            {
                "reference_id": ref.pk,
                "key": ref.bibtex_key,
                "title": ref.title[:120],
                "authors": author_line(ref.authors),
                "year": ref.year,
                "linked": ref.pk in linked_ids,
            }
        )
    candidates.sort(key=lambda c: c["key"].lower())
    return JsonResponse({"candidates": candidates})


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
