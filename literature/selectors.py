"""Selectors for literature pages."""

from django.core.cache import cache

from projects.models import Project


def project_keyword_cloud(project: Project, limit: int = 18) -> list[dict]:
    """Top keywords across the project's linked references, weighted 1-3. Cached 10 min."""
    cache_key = f"kw-cloud:{project.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from collections import Counter

    from core.keywords import extract_keywords

    counts: Counter = Counter()
    for link in project.project_references.select_related("reference"):
        ref = link.reference
        for keyword in extract_keywords(f"{ref.title}. {ref.abstract}", 6):
            counts[keyword] += 1

    most_common = counts.most_common(limit)
    if not most_common:
        cache.set(cache_key, [], 600)
        return []
    top = most_common[0][1]
    cloud = [
        {
            "keyword": kw,
            "count": n,
            "weight": 3 if n >= max(2, top * 0.66) else 2 if n >= 2 else 1,
        }
        for kw, n in most_common
    ]
    cache.set(cache_key, cloud, 600)
    return cloud
