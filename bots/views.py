from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import Bot
from .registry import BOTS, run_bot


def _history_bars(runs):
    """Chart data for a bot's run history: oldest→newest bars scaled to the max count."""
    ordered = list(reversed(runs))  # runs arrive newest-first
    top = max((run.count or 0 for run in ordered), default=0) or 1
    return [{"run": run, "pct": max(8, round((run.count or 0) * 100 / top))} for run in ordered]


def automations(request):
    from django.db.models import Prefetch

    from .models import BotRun

    states = {
        bot.slug: bot
        for bot in Bot.objects.filter(slug__in=BOTS).prefetch_related(
            Prefetch("runs", queryset=BotRun.objects.all()[:20], to_attr="recent_runs")
        )
    }
    rows = []
    for slug, spec in BOTS.items():
        state = states.get(slug)
        rows.append(
            {
                "slug": slug,
                "spec": spec,
                "state": state,
                "bars": _history_bars(state.recent_runs) if state else [],
            }
        )
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
