from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView

from core.modals import ModalFormMixin
from projects.models import Project
from projects.views import ProjectScopedMixin

from . import selectors
from .forms import DocumentForm, FolderForm, TagForm
from .models import Document, Folder, Tag


def documents_table_props(project, documents, next_url=""):
    """Props for the React documents table — used by the page island AND the SPA API."""
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Count
    from django.template.defaultfilters import filesizeformat

    from core.models import Comment

    comment_counts = dict(
        Comment.objects.filter(
            content_type=ContentType.objects.get_for_model(Document),
            object_id__in=[doc.pk for doc in documents],
        )
        .values_list("object_id")
        .annotate(n=Count("id"))
    )
    return {
        "documents": [
            {
                "id": doc.pk,
                "title": doc.title,
                "description": doc.description[:80],
                "folder": doc.folder.name if doc.folder else "",
                "folderId": doc.folder_id,
                "tags": [tag.name for tag in doc.tags.all()],
                "size": doc.file_size,
                "sizeDisplay": filesizeformat(doc.file_size),
                "added": doc.created_at.strftime("%Y-%m-%d"),
                "comments": comment_counts.get(doc.pk, 0),
                "downloadUrl": reverse("documents:download", args=[project.slug, doc.pk]),
                "editUrl": reverse("documents:document_edit", args=[project.slug, doc.pk]),
            }
            for doc in documents
        ],
        "folders": [{"id": f.pk, "name": f.name} for f in project.folders.all()],
        "tags": [{"id": t.pk, "name": t.name} for t in project.tags.all()],
        "bulkUrl": reverse("documents:bulk", args=[project.slug]),
        "nextUrl": next_url,
    }


def documents_index(request, slug):
    project = get_object_or_404(Project, slug=slug)
    current_folder = None
    if request.GET.get("folder"):
        current_folder = get_object_or_404(project.folders, pk=request.GET["folder"])

    documents = project.documents.general().select_related("folder").prefetch_related("tags")
    if current_folder:
        documents = documents.filter(folder=current_folder)
    elif "all" not in request.GET:
        documents = documents.filter(folder__isnull=True)

    current_tag = None
    if request.GET.get("tag"):
        current_tag = get_object_or_404(project.tags, pk=request.GET["tag"])
        documents = documents.filter(tags=current_tag)

    tags = project.tags.all()
    island_props = documents_table_props(project, documents, request.get_full_path())
    return render(
        request,
        "documents/index.html",
        {
            "project": project,
            "tree": selectors.folder_tree(project),
            "documents": documents,
            "current_folder": current_folder,
            "current_tag": current_tag,
            "show_all": "all" in request.GET,
            "tags": tags,
            "island_props": island_props,
        },
    )


def document_download(request, slug, pk):
    document = get_object_or_404(Document, pk=pk, project__slug=slug)
    response = FileResponse(document.file.open("rb"), as_attachment=True)
    # files are immutable once uploaded (edits create new files) — let browsers cache
    response["Cache-Control"] = "private, max-age=86400"
    return response


def _index_url(project):
    return reverse("documents:index", kwargs={"slug": project.slug})


class ProjectFormKwargsMixin(ProjectScopedMixin):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def get_success_url(self):
        return _index_url(self.project)


class DocumentCreateView(ProjectFormKwargsMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = "documents/document_form.html"

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("folder"):
            initial["folder"] = self.request.GET["folder"]
        return initial

    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class DocumentUpdateView(ProjectFormKwargsMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = "documents/document_form.html"

    def get_queryset(self):
        return self.project.documents.all()

    def get_context_data(self, **kwargs):
        from core.keywords import extract_keywords

        ctx = super().get_context_data(**kwargs)
        doc = self.object
        existing = {tag.name.lower() for tag in doc.tags.all()}
        text = f"{doc.title}. {doc.description}. {doc.file.name.rsplit('/', 1)[-1]}"
        ctx["suggested_tags"] = [
            kw for kw in extract_keywords(text, 8) if kw.lower() not in existing
        ][:5]
        return ctx


@require_POST
def add_suggested_tag(request, slug, pk):
    """Create (if needed) and attach a suggested tag, then return to the edit page."""
    project = get_object_or_404(Project, slug=slug)
    document = get_object_or_404(project.documents, pk=pk)
    name = request.POST.get("name", "").strip()[:60]
    if name:
        tag, _ = Tag.objects.get_or_create(project=project, name=name)
        document.tags.add(tag)
        messages.success(request, f"Tagged with “{name}”.")
    return redirect("documents:document_edit", slug=project.slug, pk=document.pk)


class DocumentDeleteView(ProjectScopedMixin, DeleteView):
    model = Document
    template_name = "documents/confirm_delete.html"

    def get_queryset(self):
        return self.project.documents.all()

    def get_success_url(self):
        return _index_url(self.project)


class FolderCreateView(ModalFormMixin, ProjectFormKwargsMixin, CreateView):
    model = Folder
    form_class = FolderForm
    template_name = "documents/folder_form.html"

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("parent"):
            initial["parent"] = self.request.GET["parent"]
        return initial

    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)


class FolderUpdateView(ModalFormMixin, ProjectFormKwargsMixin, UpdateView):
    model = Folder
    form_class = FolderForm
    template_name = "documents/folder_form.html"

    def get_queryset(self):
        return self.project.folders.all()


class FolderDeleteView(ProjectScopedMixin, DeleteView):
    model = Folder
    template_name = "documents/confirm_delete.html"

    def get_queryset(self):
        return self.project.folders.all()

    def get_success_url(self):
        return _index_url(self.project)


def tag_list(request, slug):
    project = get_object_or_404(Project, slug=slug)
    return render(
        request, "documents/tag_list.html", {"project": project, "tags": project.tags.all()}
    )


class TagCreateView(ProjectFormKwargsMixin, CreateView):
    model = Tag
    form_class = TagForm
    template_name = "documents/tag_form.html"

    def form_valid(self, form):
        form.instance.project = self.project
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("documents:tags", kwargs={"slug": self.project.slug})


class TagUpdateView(ProjectFormKwargsMixin, UpdateView):
    model = Tag
    form_class = TagForm
    template_name = "documents/tag_form.html"

    def get_queryset(self):
        return self.project.tags.all()

    def get_success_url(self):
        return reverse("documents:tags", kwargs={"slug": self.project.slug})


class TagDeleteView(ProjectScopedMixin, DeleteView):
    model = Tag
    template_name = "documents/confirm_delete.html"

    def get_queryset(self):
        return self.project.tags.all()

    def get_success_url(self):
        return reverse("documents:tags", kwargs={"slug": self.project.slug})


@require_POST
def bulk_upload(request, slug):
    """Drag-and-drop / multi-file upload into the current folder. Returns JSON."""
    from django.core.exceptions import ValidationError
    from django.http import JsonResponse

    from core.security import validate_upload_size

    project = get_object_or_404(Project, slug=slug)
    folder = None
    if request.POST.get("folder"):
        folder = get_object_or_404(project.folders, pk=request.POST["folder"])
    created, errors = [], []
    for file in request.FILES.getlist("files"):
        try:
            validate_upload_size(file)
        except ValidationError as exc:
            errors.append(f"{file.name}: {exc.messages[0]}")
            continue
        title = file.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip() or file.name
        document = Document.objects.create(
            project=project, folder=folder, file=file, title=title[:300]
        )
        created.append(document.title)
    return JsonResponse({"created": created, "errors": errors}, status=201 if created else 400)


def document_rename(request, slug, pk):
    """HTMX inline rename: GET returns the edit form, POST saves and returns the row."""
    project = get_object_or_404(Project, slug=slug)
    document = get_object_or_404(project.documents, pk=pk)
    if request.method == "POST":
        title = request.POST.get("title", "").strip()[:300]
        if title:
            document.title = title
            document.save(update_fields=["title", "updated_at"])
        return render(request, "documents/_doc_row.html", {"project": project, "doc": document})
    return render(request, "documents/_doc_rename_form.html", {"project": project, "doc": document})


@require_POST
def document_move(request, slug, pk):
    """HTMX quick-move to another folder (or the project root)."""
    project = get_object_or_404(Project, slug=slug)
    document = get_object_or_404(project.documents, pk=pk)
    folder = None
    if request.POST.get("folder"):
        folder = get_object_or_404(project.folders, pk=request.POST["folder"])
    document.folder = folder
    document.save(update_fields=["folder", "updated_at"])
    return render(request, "documents/_doc_row.html", {"project": project, "doc": document})


@require_POST
def bulk_action(request, slug):
    """Act on many documents at once: move, tag, or delete (Owner idea #18)."""
    project = get_object_or_404(Project, slug=slug)
    documents = project.documents.filter(pk__in=request.POST.getlist("ids"))
    count = documents.count()
    action = request.POST.get("action", "")
    if not count:
        messages.error(request, "Nothing selected.")
    elif action == "delete":
        documents.delete()
        messages.success(request, f"Deleted {count} document(s).")
    elif action == "move":
        folder = None
        if request.POST.get("folder"):
            folder = get_object_or_404(project.folders, pk=request.POST["folder"])
        documents.update(folder=folder)
        messages.success(
            request, f"Moved {count} document(s) to {folder.name if folder else 'the root'}."
        )
    elif action == "tag":
        tag = get_object_or_404(project.tags, pk=request.POST.get("tag"))
        for document in documents:
            document.tags.add(tag)
        messages.success(request, f"Tagged {count} document(s) with “{tag.name}”.")
    else:
        messages.error(request, "Unknown bulk action.")
    if request.headers.get("X-SPA") == "1":
        from django.contrib.messages import get_messages
        from django.http import JsonResponse

        summary = [m.message for m in get_messages(request)]  # consume — SPA shows its own state
        return JsonResponse({"detail": summary[-1] if summary else "ok"})
    next_url = request.POST.get("next", "")
    if not (next_url.startswith("/") and not next_url.startswith("//")):
        next_url = reverse("documents:index", kwargs={"slug": slug})
    return redirect(next_url)
