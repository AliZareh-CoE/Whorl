from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from projects.models import Project

from .models import QuickCapture


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
            "captures": QuickCapture.objects.filter(processed=False),
            "processed_recent": QuickCapture.objects.filter(processed=True)[:10],
            "projects": Project.objects.exclude(status="archived"),
        },
    )


@require_POST
def triage(request, pk):
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
    return redirect("notes:inbox")
