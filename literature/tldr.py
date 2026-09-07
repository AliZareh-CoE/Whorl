"""tl;dr of a whole paper, section by section (2026-09-07, #395 — backlog idea #32).

Works on the text the reader already extracted (`ReferenceText.pages`): find the section
headings, summarise each section with the local extractive summariser, and say which page
each section starts on so the reader can jump there. No model, no network. A paper with no
extracted text falls back to its abstract.
"""

from __future__ import annotations

import re

from core.summarize import summarize

KNOWN = (
    "abstract|introduction|background|related work|literature review|motivation|"
    "methods?|materials and methods|methodology|experimental setup|experiments?|"
    "results?|findings|analysis|discussion|general discussion|limitations|"
    "conclusions?|conclusion and future work|future work|acknowledg(e)?ments?|references|"
    "appendix|supplementary material"
)
HEADING_RE = re.compile(
    rf"^\s*(?:(\d+(?:\.\d+)*)\.?\s+)?((?:{KNOWN})|[A-Z][A-Za-z][A-Za-z ,:'&-]{{2,60}})\s*$",
    re.IGNORECASE,
)
STOP_AT = re.compile(r"^(references|bibliography|acknowledg(e)?ments?)$", re.IGNORECASE)
MAX_SECTIONS = 14


def _is_heading(line: str, known_only: bool) -> str | None:
    """The heading title if the line looks like one — a known section name, or a numbered
    short Title-Case line; unnumbered arbitrary lines count only when known."""
    stripped = line.strip()
    if not stripped or len(stripped) > 80 or stripped.endswith((".", ",", ";")):
        return None
    match = HEADING_RE.match(stripped)
    if not match:
        return None
    number, title = match.group(1), match.group(2).strip()
    if re.fullmatch(KNOWN, title, re.IGNORECASE):
        return title[:1].upper() + title[1:]
    if number and not known_only and len(title.split()) <= 8:
        return title
    return None


def split_sections(pages: list[str]) -> list[dict]:
    """[{title, page, text}] in reading order; the text before the first heading is
    'Opening'. Stops at the references."""
    sections: list[dict] = []
    current = {"title": "Opening", "page": 1, "lines": []}
    for page_no, page in enumerate(pages, start=1):
        for line in (page or "").splitlines():
            title = _is_heading(line, known_only=False)
            if title:
                if STOP_AT.match(title):
                    if current["lines"]:
                        sections.append(current)
                    return _finish(sections)
                if current["lines"] or current["title"] != "Opening":
                    sections.append(current)
                current = {"title": title, "page": page_no, "lines": []}
                continue
            current["lines"].append(line)
    sections.append(current)
    return _finish(sections)


def _finish(sections: list[dict]) -> list[dict]:
    out = []
    for s in sections:
        text = " ".join(line.strip() for line in s["lines"] if line.strip())
        if len(text) < 80:
            continue  # a heading with nothing under it (a table of contents line, say)
        out.append({"title": s["title"], "page": s["page"], "text": text})
    return out[:MAX_SECTIONS]


def tldr(reference, per_section: int = 2) -> dict:
    """Section summaries for a reference: from the extracted PDF text when there is one,
    else from the abstract. `sections` is empty (with a reason) when neither exists."""
    text = getattr(reference, "text", None)
    pages = list(text.pages) if text is not None and text.pages else []
    if pages:
        sections = split_sections(pages)
        if len(sections) <= 1:
            # no recognisable headings: one summary of the whole text, a little longer
            body = " ".join(p for p in pages if p)
            sentences = summarize(body, max_sentences=5)
            return {
                "source": "pdf-text",
                "sections": [{"title": "Whole paper", "page": 1, "sentences": sentences}],
            }
        return {
            "source": "pdf-text",
            "sections": [
                {
                    "title": s["title"],
                    "page": s["page"],
                    "sentences": summarize(s["text"], max_sentences=per_section),
                }
                for s in sections
            ],
        }
    abstract = (getattr(reference, "abstract", "") or "").strip()
    if abstract:
        return {
            "source": "abstract",
            "sections": [
                {
                    "title": "Abstract",
                    "page": None,
                    "sentences": summarize(abstract, max_sentences=3),
                }
            ],
        }
    return {
        "source": "none",
        "sections": [],
        "reason": "No PDF text and no abstract — attach a PDF and index its text first.",
    }
