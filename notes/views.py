from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView

from projects.models import Project
from projects.views import ProjectScopedMixin

from . import services
from .capture import open_captures, snoozed_captures
from .forms import NoteForm
from .models import Note, QuickCapture


def note_list(request, slug):
    from django.db.models import Count

    project = get_object_or_404(Project, slug=slug)
    # annotate the backlink count so the list doesn't run a .count() per row (N+1)
    notes = project.notes.annotate(backlink_count=Count("incoming_links"))
    query = request.GET.get("q", "").strip()
    if query:
        notes = notes.filter(title__icontains=query)
    return render(
        request,
        "notes/note_list.html",
        {
            "project": project,
            "notes": notes,
            "query": query,
            # [[links]] to notes that don't exist yet — surfaced as one-click stubs (#236-fu)
            "unwritten": services.unwritten_note_titles(project),
        },
    )


def note_detail(request, slug, pk):
    project = get_object_or_404(Project, slug=slug)
    note = get_object_or_404(project.notes, pk=pk)
    from core.comments import comments_for
    from core.keywords import extract_keywords
    from core.templatetags.markdown_extras import markdownify

    return render(
        request,
        "notes/note_detail.html",
        {
            "project": project,
            "note": note,
            "rendered_body": markdownify(services.body_with_resolved_links(note)),
            "backlinks": [link.source for link in note.incoming_links.select_related("source")],
            "outgoing": [link.target for link in note.outgoing_links.select_related("target")],
            "keywords": extract_keywords(f"{note.title}. {note.body}", 6),
            "comments": comments_for(note),
        },
    )


@require_POST
def note_preview(request, slug):
    """HTMX endpoint: render the markdown body as the user writes."""
    project = get_object_or_404(Project, slug=slug)
    from core.templatetags.markdown_extras import markdownify

    body = request.POST.get("body", "")
    fake = Note(project=project, body=body)
    return render(
        request,
        "notes/_preview.html",
        {"rendered": markdownify(services.body_with_resolved_links(fake))},
    )


class NoteFormMixin(ProjectScopedMixin):
    model = Note
    form_class = NoteForm
    template_name = "notes/note_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def form_valid(self, form):
        form.instance.project = self.project
        response = super().form_valid(form)
        unresolved = services.sync_note_links(self.object)
        if unresolved:
            messages.info(
                self.request,
                "Unresolved wiki-links (no note with that title yet): " + ", ".join(unresolved),
            )
        return response


class NoteCreateView(NoteFormMixin, CreateView):
    def get_initial(self):
        # support ?title= so an unresolved [[wiki-link]] opens this form pre-filled.
        initial = super().get_initial()
        title = self.request.GET.get("title", "").strip()[:300]
        if title:
            initial["title"] = title
        return initial


class NoteUpdateView(NoteFormMixin, UpdateView):
    def get_queryset(self):
        return self.project.notes.all()


class NoteDeleteView(ProjectScopedMixin, DeleteView):
    model = Note
    template_name = "notes/note_confirm_delete.html"

    def get_queryset(self):
        return self.project.notes.all()

    def get_success_url(self):
        return reverse("notes:list", kwargs={"slug": self.project.slug})


def inbox(request):
    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        if text:
            QuickCapture.objects.create(text=text)
            messages.success(request, "Captured.")
        return redirect("notes:inbox")
    return render(
        request,
        "notes/inbox.html",
        {
            "captures": open_captures(),
            "snoozed": snoozed_captures(),
            "processed_recent": QuickCapture.objects.filter(processed=True)[:10],
            "projects": Project.objects.exclude(status="archived"),
        },
    )


@require_POST
def triage(request, pk):
    from django.utils.http import url_has_allowed_host_and_scheme

    capture = get_object_or_404(QuickCapture, pk=pk)
    action = request.POST.get("action")
    if action == "assign":
        capture.project = get_object_or_404(Project, slug=request.POST.get("project"))
        capture.processed = True
        capture.save()
        messages.success(request, f"Filed to {capture.project.name}.")
    elif action == "dismiss":
        capture.processed = True
        capture.save(update_fields=["processed", "updated_at"])
        messages.success(request, "Dismissed.")
    # the dashboard's attention lead triages inline (#157) — bounce back to it
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
        return redirect(next_url)
    return redirect("notes:inbox")


@require_POST
def inbox_bulk(request):
    """Triage many captures at once: dismiss or assign to a project (Owner idea #18)."""
    captures = QuickCapture.objects.filter(pk__in=request.POST.getlist("ids"), processed=False)
    action = request.POST.get("action")
    count = captures.count()
    if not count:
        messages.error(request, "Nothing selected.")
    elif action == "dismiss":
        captures.update(processed=True, updated_at=timezone.now())
        messages.success(request, f"Dismissed {count} item(s).")
    elif action == "assign":
        project = get_object_or_404(Project, slug=request.POST.get("project"))
        captures.update(project=project, processed=True, updated_at=timezone.now())
        messages.success(request, f"Filed {count} item(s) to {project.name}.")
    else:
        messages.error(request, "Unknown bulk action.")
    return redirect("notes:inbox")
