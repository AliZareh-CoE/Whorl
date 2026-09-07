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
        "samples": samples,
    }
