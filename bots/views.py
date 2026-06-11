from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import Bot
from .registry import BOTS, run_bot


def automations(request):
    from django.db.models import Prefetch

    from .models import BotRun

    states = {
        bot.slug: bot
        for bot in Bot.objects.filter(slug__in=BOTS).prefetch_related(
            Prefetch("runs", queryset=BotRun.objects.all()[:5], to_attr="recent_runs")
        )
    }
    rows = [{"slug": slug, "spec": spec, "state": states.get(slug)} for slug, spec in BOTS.items()]
    return render(request, "bots/automations.html", {"rows": rows})


@require_POST
def toggle(request, slug):
    if slug not in BOTS:
        messages.error(request, "Unknown bot.")
        return redirect("bots:automations")
    state, _ = Bot.objects.get_or_create(slug=slug)
    state.enabled = not state.enabled
    state.save(update_fields=["enabled", "updated_at"])
    messages.success(
        request,
        f"{BOTS[slug]['name']} {'enabled — runs daily at 06:00' if state.enabled else 'disabled'}.",
    )
    return redirect("bots:automations")


@require_POST
def run_now(request, slug):
    if slug not in BOTS:
        messages.error(request, "Unknown bot.")
        return redirect("bots:automations")
    result = run_bot(slug)
    messages.success(request, f"{BOTS[slug]['name']}: {result}")
    return redirect("bots:automations")
