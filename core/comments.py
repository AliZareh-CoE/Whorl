"""Comment threads on Atlas objects (Owner idea #10). Plain forms, no JS."""

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Comment


def _allowed_kinds() -> dict:
    from literature.models import Reference
    from notes.models import Note
    from writing.models import Manuscript

    return {"note": Note, "reference": Reference, "manuscript": Manuscript}


def comments_for(target):
    return Comment.objects.filter(
        content_type=ContentType.objects.get_for_model(type(target)), object_id=target.pk
    )


def _target_url(target):
    return target.get_absolute_url() if hasattr(target, "get_absolute_url") else "/"


@require_POST
def add_comment(request, kind, object_id):
    model = _allowed_kinds().get(kind)
    if model is None:
        from django.http import Http404

        raise Http404("Unknown comment target.")
    target = get_object_or_404(model, pk=object_id)
    body = request.POST.get("body", "").strip()[:5000]
    page = request.POST.get("page")
    page = int(page) if page and page.isdigit() else None
    if body:
        Comment.objects.create(target=target, body=body, page=page)
        messages.success(request, "Comment added.")
    next_url = request.POST.get("next", "")
    if not (next_url.startswith("/") and not next_url.startswith("//")):
        next_url = _target_url(target)  # local paths only — no open redirects
    return redirect(next_url)


@require_POST
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    target = comment.target
    comment.delete()
    messages.success(request, "Comment deleted.")
    return redirect(_target_url(target) if target else "/")
