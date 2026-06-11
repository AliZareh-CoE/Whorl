from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, UpdateView

from .forms import PromptForm
from .models import Prompt


def gallery(request):
    prompts = Prompt.objects.all()
    query = request.GET.get("q", "").strip()
    tag = request.GET.get("tag", "").strip()
    if query:
        prompts = prompts.filter(Q(title__icontains=query) | Q(body__icontains=query))
    if tag:
        prompts = prompts.filter(tags__icontains=tag)
    all_tags = sorted({t for prompt in Prompt.objects.all() for t in prompt.tag_list})
    return render(
        request,
        "prompts/gallery.html",
        {"prompts": prompts, "query": query, "tag": tag, "all_tags": all_tags},
    )


class PromptCreateView(CreateView):
    model = Prompt
    form_class = PromptForm
    template_name = "prompts/form.html"
    success_url = reverse_lazy("prompts:gallery")


class PromptUpdateView(UpdateView):
    model = Prompt
    form_class = PromptForm
    template_name = "prompts/form.html"
    success_url = reverse_lazy("prompts:gallery")


class PromptDeleteView(DeleteView):
    model = Prompt
    template_name = "prompts/confirm_delete.html"
    success_url = reverse_lazy("prompts:gallery")
