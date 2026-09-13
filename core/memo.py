"""A request-scoped memo on a model instance (#484).

The project overview calls the same helpers from several places — the current phase, the
milestone roll-up, the roadmap, the whole timeline — and each call re-ran its queries. A
view that knows it will ask repeatedly calls ``enable_memo(project)`` once; helpers wrap
their body in ``memo(project, key, compute)`` and reuse the first answer for the life of
that instance. Instances that never opted in behave exactly as before (every call is
fresh), so tests that mutate and re-ask see live data.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ATTR = "_atlas_memo"


def enable_memo(obj: Any) -> None:
    """Opt this instance into memoised helper results (for one request)."""
    obj.__dict__[ATTR] = {}


def memo(obj: Any, key: Any, compute: Callable[[], Any]) -> Any:
    cache = obj.__dict__.get(ATTR) if hasattr(obj, "__dict__") else None
    if cache is None:
        return compute()
    if key not in cache:
        cache[key] = compute()
    return cache[key]
