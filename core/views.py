from django.shortcuts import render
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
