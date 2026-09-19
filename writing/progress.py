"""Writing progress (#413): words per day, the delta since yesterday, the streak.

`record_words` stores today's total for a manuscript (the last save of the day wins);
`progress` turns the samples into what the Studio status bar and the Writing board show.
Counting uses the same LaTeX detex as the word-count endpoint, so the numbers agree.
"""

from __future__ import annotations

import datetime as dt

from django.utils import timezone


def manuscript_words(manuscript) -> int:
    from writing.wordcount import word_count

    files = list(manuscript.files.filter(kind="tex").values_list("content", flat=True))
    source = "\n".join(files) if files else manuscript.latex_source
    return int(word_count(source)["words"])


def record_words(manuscript, words: int | None = None, day: dt.date | None = None):
    """Upsert today's sample. Returns the sample (unchanged when the count did not move)."""
    from writing.models import WordCountSample

    day = day or timezone.localdate()
    words = manuscript_words(manuscript) if words is None else int(words)
    sample, created = WordCountSample.objects.get_or_create(
        manuscript=manuscript, date=day, defaults={"words": words}
    )
    if not created and sample.words != words:
        sample.words = words
        sample.save(update_fields=["words"])
    return sample


def progress(manuscript, days: int = 30) -> dict:
    """Samples for the last ``days`` days with per-day deltas, today's delta, the streak of
    consecutive writing days ending today (or yesterday), the best day and this week's total."""
    from writing.models import WordCountSample

    today = timezone.localdate()
    since = today - dt.timedelta(days=days - 1)
    # Audit #36: read the prefetch when the list view loaded the samples (one query for the
    # whole page instead of one per row); the ordering is the same either way
    if "word_samples" in getattr(manuscript, "_prefetched_objects_cache", {}):
        rows = sorted(manuscript.word_samples.all(), key=lambda r: r.date)
    else:
        rows = list(WordCountSample.objects.filter(manuscript=manuscript).order_by("date"))
    by_date = {r.date: r.words for r in rows}
    baseline = None  # last count before the window
    for r in rows:
        if r.date < since:
            baseline = r.words
    samples = []
    prev = baseline
    for i in range(days):
        day = since + dt.timedelta(days=i)
        words = by_date.get(day)
        if words is None:
            samples.append({"date": day.isoformat(), "words": prev, "delta": 0})
            continue
        delta = 0 if prev is None else words - prev
        samples.append({"date": day.isoformat(), "words": words, "delta": delta})
        prev = words
    deltas = {s["date"]: s["delta"] for s in samples}
    today_delta = deltas.get(today.isoformat(), 0)
    streak = 0
    cursor = today if today_delta > 0 else today - dt.timedelta(days=1)
    while deltas.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= dt.timedelta(days=1)
    week_start = today - dt.timedelta(days=6)
    week_delta = sum(
        s["delta"] for s in samples if s["date"] >= week_start.isoformat() and s["delta"] > 0
    )
    best = max(samples, key=lambda s: s["delta"], default=None)
    return {
        "words": rows[-1].words if rows else 0,
        "today_delta": today_delta,
        "week_delta": week_delta,
        "streak": streak,
        "best_day": best if best and best["delta"] > 0 else None,
        "days_with_writing": sum(1 for s in samples if s["delta"] > 0),
        "compiles": compile_rhythm(manuscript, 14),  # #460
        "samples": samples,
    }


def compile_rhythm(manuscript, days: int = 14) -> dict:
    """#460 (backlog #129): compiles per day over the last ``days`` days, from the revision
    snapshots every successful compile leaves behind (labeled ones included — they are
    compiles too). Trimmed automatic snapshots beyond the manuscript's cap fall out of the
    window naturally, which is why the window is two weeks."""
    from writing.models import ManuscriptRevision

    today = timezone.localdate()
    since = today - dt.timedelta(days=days - 1)
    counts: dict[str, int] = {}
    if "revisions" in getattr(manuscript, "_prefetched_objects_cache", {}):
        # Audit #36: the list view prefetches the window's revisions; filter in Python
        stamps = [
            r.created_at
            for r in manuscript.revisions.all()
            if timezone.localtime(r.created_at).date() >= since
        ]
    else:
        stamps = ManuscriptRevision.objects.filter(
            manuscript=manuscript, created_at__date__gte=since
        ).values_list("created_at", flat=True)
    for stamp in stamps:
        key = timezone.localtime(stamp).date().isoformat()
        counts[key] = counts.get(key, 0) + 1
    per_day = [
        {"date": (since + dt.timedelta(days=i)).isoformat(), "compiles": 0} for i in range(days)
    ]
    for row in per_day:
        row["compiles"] = counts.get(row["date"], 0)
    week_start = today - dt.timedelta(days=6)
    return {
        "per_day": per_day,
        "today": counts.get(today.isoformat(), 0),
        "week": sum(r["compiles"] for r in per_day if r["date"] >= week_start.isoformat()),
        "total": sum(counts.values()),
    }


def compiles_since(start: dt.date) -> int:
    """Successful compiles across every manuscript since ``start`` (for the pet's line)."""
    from writing.models import ManuscriptRevision

    return ManuscriptRevision.objects.filter(created_at__date__gte=start).count()
