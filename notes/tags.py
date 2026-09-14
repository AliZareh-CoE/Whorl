"""#504: #tags in notes.

A tag is written where the thought is — ``#method``, ``#pilot/v2``, ``#to-discuss`` — and
collected on save. Headings (``# Title``) and anchors in URLs are not tags; a tag starts with a
letter and may carry ``/``, ``-`` and ``_``. Tags are stored lower-cased on the note (a JSON
list, sorted) so the list rail can filter and count them without re-reading every body.
"""

from __future__ import annotations

import re
from collections import Counter

TAG_RE = re.compile(r"(?<![\w#&/.:])#([A-Za-z][\w/-]*[\w])")
CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)


def parse_tags(body: str) -> list[str]:
    """Distinct, lower-cased tags in reading order; code spans and blocks are skipped."""
    text = CODE_RE.sub(" ", body or "")
    seen: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s{0,3}#{1,6}\s", line):
            continue  # a markdown heading, not a tag
        for m in TAG_RE.finditer(line):
            tag = m.group(1).lower().rstrip("/-")
            if tag and tag not in seen:
                seen.append(tag)
    return seen


def sync_note_tags(note, save: bool = True) -> list[str]:
    """Store the body's tags on the note (sorted); returns them."""
    tags = sorted(parse_tags(note.body))
    if tags != (note.tags or []):
        note.tags = tags
        if save:
            note.save(update_fields=["tags", "updated_at"])
    return tags


def project_tags(project) -> list[dict]:
    """[{tag, count}] for the project, most used first then alphabetical."""
    counts: Counter[str] = Counter()
    for tags in project.notes.values_list("tags", flat=True):
        counts.update(tags or [])
    return [
        {"tag": tag, "count": n}
        for tag, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
