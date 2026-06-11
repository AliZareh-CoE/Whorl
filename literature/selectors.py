"""Selectors for literature pages."""

from django.core.cache import cache

from projects.models import Project

READ_STATUSES = ("read", "annotated")


def theme_read_counts(project: Project) -> dict[int, int]:
    """Per-theme count of READ/ANNOTATED papers — fewer read means a bigger gap."""
    from django.db.models import Count, Q

    return {
        theme.pk: theme.read_count
        for theme in project.review_themes.annotate(
            read_count=Count(
                "marks",
                filter=Q(marks__project_reference__reading_status__in=READ_STATUSES),
            )
        )
    }


def annotate_gap_scores(project: Project, links: list) -> None:
    """Attach gap_score/gap_theme to queued links: the least-read theme each paper covers.

    Papers marked with an under-read theme get a low score (read them first);
    papers with no theme marks sort last.
    """
    read_counts = theme_read_counts(project)
    names = dict(project.review_themes.values_list("pk", "name"))
    for link in links:
        theme_ids = [mark.theme_id for mark in link.review_marks.all()]
        if theme_ids:
            gap_theme_id = min(theme_ids, key=lambda pk: read_counts.get(pk, 0))
            link.gap_score = read_counts.get(gap_theme_id, 0)
            link.gap_theme = names.get(gap_theme_id, "")
        else:
            link.gap_score = None  # sorts after every marked paper
            link.gap_theme = ""


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
