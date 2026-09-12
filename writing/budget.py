"""Venue budget (Writing v2 slice 3): what the manuscript uses against the venue's limits.

Limits live on the manuscript (`venue_limits`, a small JSON dict); usage comes from the LaTeX
word count, the abstract, `figure` environments across the .tex files, and the bibliography.
"""

from __future__ import annotations

import re

from .wordcount import word_count

FIGURE_RE = re.compile(r"\\begin\{figure\*?\}")
TABLE_RE = re.compile(r"\\begin\{table\*?\}")

BUDGET_KEYS: list[tuple[str, str]] = [
    ("words", "Words"),
    ("abstract_words", "Abstract words"),
    ("figures", "Figures"),
    ("tables", "Tables"),
    ("references", "References"),
    ("pages", "Pages"),
]


def clean_limits(raw) -> dict:
    """Keep only known keys with positive integers; unknown/blank values are dropped."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for key, _ in BUDGET_KEYS:
        value = raw.get(key)
        if value in (None, "", 0, "0"):
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            out[key] = number
    return out


def usage(manuscript) -> dict:
    files = list(manuscript.files.filter(kind="tex"))
    source = "\n".join(f.content for f in files) if files else manuscript.latex_source or ""
    counts = word_count(source)
    return {
        "words": counts["words"],
        "abstract_words": len(manuscript.abstract.split()),
        "figures": len(FIGURE_RE.findall(source)),
        "tables": len(TABLE_RE.findall(source)),
        "references": manuscript.manuscriptreference_set.count(),
        "pages": None,  # only known after a compile; reported when the PDF exists
    }


def _state(used: int, limit: int) -> str:
    ratio = used / limit if limit else 0
    if ratio > 1:
        return "over"
    if ratio >= 0.9:
        return "near"
    return "ok"


def budget(manuscript) -> dict:
    limits = clean_limits(manuscript.venue_limits)
    used = usage(manuscript)
    if manuscript.compiled_pdf:
        used["pages"] = _pdf_pages(manuscript)
    items = []
    for key, label in BUDGET_KEYS:
        value = used.get(key)
        limit = limits.get(key)
        if value is None and limit is None:
            continue
        items.append(
            {
                "key": key,
                "label": label,
                "used": value,
                "limit": limit,
                "ratio": (round(value / limit, 3) if (limit and value is not None) else None),
                "state": _state(value, limit) if (limit and value is not None) else "unset",
            }
        )
    over = [i["label"].lower() for i in items if i["state"] == "over"]
    return {
        "venue": manuscript.target_venue,
        "limits": limits,
        "usage": used,
        "items": items,
        "over": over,
        "summary": (
            "over the limit on " + ", ".join(over)
            if over
            else "within every limit"
            if limits
            else "no limits set"
        ),
    }


def _pdf_pages(manuscript) -> int | None:
    try:
        from pypdf import PdfReader

        with manuscript.compiled_pdf.open("rb") as handle:
            return len(PdfReader(handle).pages)
    except Exception:
        return None
