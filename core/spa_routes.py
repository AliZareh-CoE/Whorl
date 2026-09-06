"""Classic-page → SPA-route mapping (Owner report 2026-09-06: "it suddenly jumps back to the
older UI"). Keep in sync with ``frontend/src/app/links.ts``; ``test_front_door`` pins both."""

from __future__ import annotations

import re

SPA_PAGES = "plan|documents|figures|literature|research|decisions|graph|timeline|files"

_MAPS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^/projects/$"), "/projects"),
    (re.compile(r"^/projects/new/$"), "/projects/new"),
    (re.compile(r"^/projects/(?P<slug>[^/]+)/$"), "/projects/{slug}"),
    (re.compile(rf"^/projects/(?P<slug>[^/]+)/(?P<page>{SPA_PAGES})/$"), "/projects/{slug}/{page}"),
    (re.compile(r"^/projects/(?P<slug>[^/]+)/literature/queue/$"), "/projects/{slug}/queue"),
    (re.compile(r"^/projects/(?P<slug>[^/]+)/notes/$"), "/projects/{slug}/notes"),
    (re.compile(r"^/projects/(?P<slug>[^/]+)/notes/(?P<pk>\d+)/$"), "/projects/{slug}/notes/{pk}"),
    (re.compile(r"^/projects/(?P<slug>[^/]+)/writing/$"), "/writing"),
    (re.compile(r"^/projects/(?P<slug>[^/]+)/writing/(?P<pk>\d+)/$"), "/manuscripts/{pk}"),
    (re.compile(r"^/library/(?P<pk>\d+)/$"), "/references/{pk}"),
    (re.compile(r"^/library/$"), "/library"),
    (re.compile(r"^/writing/$"), "/writing"),
    (re.compile(r"^/inbox/$"), "/inbox"),
    (re.compile(r"^/today/$"), "/today"),
    (re.compile(r"^/prompts/$"), "/prompts"),
    (re.compile(r"^/search/$"), "/search"),
    (re.compile(r"^/automations/$"), "/automations"),
]


def spa_equivalent(path: str) -> str | None:
    """The SPA route that renders the same thing as classic ``path``, or None."""
    for pattern, template in _MAPS:
        match = pattern.match(path)
        if match:
            return template.format(**match.groupdict())
    return None
