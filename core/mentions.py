"""Resolve [[Note Title]] and @cite-key mentions into markdown links (Backlog #20).

Since #407 this is a thin alias over ``core.rendering.resolve_mentions`` (project-less
scope: a wiki-link resolves only when exactly one note carries that title).
"""

from core.rendering import resolve_mentions as _resolve


def resolve_mentions(body: str) -> str:
    return _resolve(body, None)
