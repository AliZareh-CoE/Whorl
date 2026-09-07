"""A process-wide data version for conditional GETs (2026-09-07, #384).

Every list/detail ETag folds this number in. It moves on any save, delete or M2M change of an
Atlas model (core/signals.py), so a write that leaves `updated_at` alone — a tag added to a
paper, a link set on a note, a rename that changes what *other* rows serialise — can no
longer leave a client reading the old answer back out of its cache (#381, #383).

The value lives in Django's cache: exact within one process (the desktop), best-effort across
processes (a worker's write is still caught by `updated_at`, which stays the primary signal).
"""

from __future__ import annotations

import time

from django.core.cache import cache

CACHE_KEY = "atlas-data-version"


def data_version() -> int:
    value = cache.get(CACHE_KEY)
    return int(value) if isinstance(value, int) else 0


def bump_data_version() -> int:
    """Monotonic even across restarts: nanoseconds since the epoch."""
    value = time.time_ns()
    cache.set(CACHE_KEY, value, None)
    return value
