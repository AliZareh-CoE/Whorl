from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST


def dashboard(request):
    from .dashboard import dashboard_context

    return render(request, "core/dashboard.html", dashboard_context())


@require_POST
def read_aloud(request):
    from django.http import HttpResponse, JsonResponse

    from . import tts

    text = request.POST.get("text", "").strip()
    if not text:
        return JsonResponse({"error": "Nothing to read."}, status=400)
    try:
        audio = tts.synthesize_wav(text)
    except tts.TTSUnavailable as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    response = HttpResponse(audio, content_type="audio/wav")
    response["Cache-Control"] = "no-store"
    return response


def search(request):
    from .search import search_all

    query = request.GET.get("q", "").strip()
    results = search_all(query) if query else []
    grouped: dict[str, list] = {}
    for result in results:
        grouped.setdefault(result["type"], []).append(result)
    return render(
        request,
        "core/search.html",
        {"query": query, "grouped": grouped, "total": len(results)},
    )


def search_suggest(request):
    """As-you-type results for the sidebar box (HTMX)."""
    from .search import search_all

    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        from django.http import HttpResponse

        return HttpResponse("")
    results = search_all(query)[:8]
    return render(request, "core/_suggest.html", {"results": results, "query": query})


@require_POST
def summarize_view(request):
    """HTMX tl;dr: POST text, get back the key sentences."""
    from .summarize import summarize

    text = request.POST.get("text", "")[:50000]
    sentences = summarize(text)
    return render(request, "core/_summary.html", {"sentences": sentences})


def assistant_context_view(request):
    """JSON backend for the Assistant panel: context, actions, commands, prompt."""
    from django.http import JsonResponse

    from .assistant import assistant_context

    return JsonResponse(assistant_context(request.GET.get("path", "/")))


def pet_page(request):
    from django.core.cache import cache
    from django.shortcuts import redirect

    from .models import Pet
    from .pet import pet_state

    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:40]
        if name:
            pet, _ = Pet.objects.get_or_create(pk=1)
            pet.name = name
            pet.save()
            cache.delete("atlas-pet-state")
        return redirect("core:pet")
    return render(request, "core/pet.html", {"pet": pet_state()})


def spa_redirect(request, rest=""):
    """Old /app/* bookmarks land on the same route at the new front door.

    rest can start with a slash (e.g. //evil.com), which would become a
    protocol-relative open redirect — collapse leading slashes to keep it local.
    """
    from django.shortcuts import redirect

    target = "/" + rest.lstrip("/")
    return redirect(target)


@ensure_csrf_cookie
def spa_shell(request, rest=""):
    """Serve the React SPA shell (Owner idea #20) — the router takes it from here.

    ensure_csrf_cookie: the shell has no form, but the SPA's writes need the token.
    """
    return render(request, "spa.html")
