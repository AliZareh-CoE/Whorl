from django.shortcuts import render


def dashboard(request):
    return render(request, "core/dashboard.html")


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
