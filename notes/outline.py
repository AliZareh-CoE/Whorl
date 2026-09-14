"""#507: the shape and size of a note.

``outline`` lists the ATX headings of a markdown body (level, text, 1-based line) skipping
fenced code; ``measure`` counts what the note is made of — words (the same whitespace rule
the history uses), characters, a reading time at 200 words a minute, headings, [[links]],
@citations and task boxes. Both are pure so the editor mirrors them live and the API/MCP
serve the same numbers.
"""

from __future__ import annotations

import math
import re

WORDS_PER_MINUTE = 200
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
FENCE_RE = re.compile(r"^ {0,3}(```|~~~)")
LINK_RE = re.compile(r"\[\[([^\[\]|\n]+)(?:\|[^\[\]\n]*)?\]\]")  # linear (Audit #29)
CITE_RE = re.compile(r"(?<![\w@])@([A-Za-z][\w:-]*\w)")
TASK_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]\s")


def _prose_lines(body: str) -> list[tuple[int, str, bool]]:
    """(line number, text, in_code) for every line — fences toggle the flag."""
    rows, in_code = [], False
    for number, line in enumerate((body or "").splitlines(), start=1):
        if FENCE_RE.match(line):
            in_code = not in_code
            rows.append((number, line, True))
            continue
        rows.append((number, line, in_code))
    return rows


def outline(body: str) -> list[dict]:
    """Headings in reading order: {level, text, line}; inline code and fences excluded."""
    items = []
    for number, line, in_code in _prose_lines(body):
        if in_code:
            continue
        m = HEADING_RE.match(line)
        if m and m.group(2).strip():
            items.append({"level": len(m.group(1)), "text": m.group(2).strip(), "line": number})
    return items


def measure(body: str) -> dict:
    """What the note is made of; ``minutes`` is 0 for an empty note, else at least 1."""
    lines = _prose_lines(body)
    prose = "\n".join(line for _, line, in_code in lines if not in_code)
    words = len((body or "").split())
    done = total = 0
    for _, line, in_code in lines:
        if in_code:
            continue
        m = TASK_RE.match(line)
        if m:
            total += 1
            done += m.group(1) != " "
    return {
        "words": words,
        "characters": len(body or ""),
        "minutes": math.ceil(words / WORDS_PER_MINUTE) if words else 0,
        "headings": len(outline(body)),
        "links": len(set(LINK_RE.findall(prose))),
        "citations": len(set(CITE_RE.findall(prose))),
        "tasks": {"done": done, "total": total},
    }


def note_outline(note) -> dict:
    return {"outline": outline(note.body), "measure": measure(note.body)}
