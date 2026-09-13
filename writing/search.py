"""Find and replace across a manuscript's text files (#476).

Overleaf-style project search: every .tex / .bib file, plain or regular-expression, case
folded unless asked otherwise, one hit per match with the whole line for context. Replace
rewrites the files that match (optionally only some of them) and saves each through
``ManuscriptFile.save()`` like an editor save, so the alias, timestamps and word samples
behave exactly as if the text had been typed.
"""

from __future__ import annotations

import re

MAX_HITS = 500
MAX_PATTERN = 500  # Audit #26: a query longer than this is a mistake, not a search
TEXT_KINDS = ("tex", "bib")


class BadPattern(ValueError):
    pass


def _pattern(q: str, *, regex: bool, case: bool) -> re.Pattern:
    if not q:
        raise BadPattern("Nothing to search for.")
    if len(q) > MAX_PATTERN:
        raise BadPattern(f"The pattern is longer than {MAX_PATTERN} characters.")
    flags = 0 if case else re.IGNORECASE
    try:
        return re.compile(q if regex else re.escape(q), flags)
    except re.error as exc:
        raise BadPattern(f"Bad regular expression: {exc}") from exc


def _text_files(manuscript):
    return list(manuscript.files.filter(kind__in=TEXT_KINDS).order_by("path"))


def search_files(manuscript, q: str, *, regex: bool = False, case: bool = False) -> dict:
    pat = _pattern(q, regex=regex, case=case)
    hits: list[dict] = []
    files_hit: set[str] = set()
    truncated = False
    for f in _text_files(manuscript):
        for n, line in enumerate(f.content.splitlines(), 1):
            for m in pat.finditer(line):
                if m.end() == m.start():  # an empty match (e.g. `a*`) says nothing useful
                    continue
                if len(hits) >= MAX_HITS:
                    truncated = True
                    break
                hits.append(
                    {
                        "file": f.path,
                        "line": n,
                        "col": m.start() + 1,
                        "end": m.end() + 1,
                        "text": line,
                    }
                )
                files_hit.add(f.path)
            if truncated:
                break
        if truncated:
            break
    return {
        "query": q,
        "regex": regex,
        "case": case,
        "count": len(hits),
        "files": sorted(files_hit),
        "truncated": truncated,
        "hits": hits,
    }


def replace_in_files(
    manuscript,
    q: str,
    replacement: str,
    *,
    regex: bool = False,
    case: bool = False,
    files: list[str] | None = None,
) -> dict:
    """Replace every match (in the chosen files, or all) and save the changed files.
    In regex mode the replacement may use \\1 / \\g<name> groups; in plain mode it is
    literal."""
    pat = _pattern(q, regex=regex, case=case)
    repl = replacement if regex else replacement.replace("\\", "\\\\")
    wanted = set(files) if files else None
    replaced = 0
    changed: list[str] = []
    for f in _text_files(manuscript):
        if wanted is not None and f.path not in wanted:
            continue
        new_text, n = pat.subn(repl, f.content)
        if n and new_text != f.content:
            f.content = new_text
            f.save()
            replaced += n
            changed.append(f.path)
    return {"query": q, "replacement": replacement, "replaced": replaced, "files": changed}
