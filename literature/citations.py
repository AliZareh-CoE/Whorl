"""Formatted citations (Library v2 slice 4): APA 7, MLA 9, Chicago author-date, Harvard,
Vancouver, and IEEE — bibliography entries, in-text forms, and whole bibliographies — from the
metadata Atlas already holds. Pure functions; `text` for clipboards, `html` for display (italic
titles/venues, no other markup).

Volume / issue / pages are used when present in `Reference.extra` (Crossref and OpenAlex
imports carry them under those keys); everything degrades gracefully when a field is missing.
"""

from __future__ import annotations

import html
import re

STYLES = ("apa", "mla", "chicago", "harvard", "vancouver", "ieee")
STYLE_LABELS = {
    "apa": "APA 7",
    "mla": "MLA 9",
    "chicago": "Chicago (author-date)",
    "harvard": "Harvard",
    "vancouver": "Vancouver",
    "ieee": "IEEE",
}


def _initials(given: str, dots: bool = True, spaced: bool = True) -> str:
    parts = re.split(r"[\s\-]+", (given or "").strip())
    inits = [p[0].upper() for p in parts if p]
    if not inits:
        return ""
    if dots:
        return (" " if spaced else "").join(f"{i}." for i in inits)
    return "".join(inits)


def _family(a: dict) -> str:
    return (a.get("family") or "").strip()


def _given(a: dict) -> str:
    return (a.get("given") or "").strip()


def _join(names: list[str], last_sep: str, sep: str = ", ", oxford: bool = True) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}{last_sep}{names[1]}"
    head = sep.join(names[:-1])
    return (
        f"{head}{sep.strip() if oxford else ''}{last_sep}{names[-1]}"
        if oxford
        else f"{head}{last_sep}{names[-1]}"
    )


def _authors(reference, style: str) -> str:
    authors = [a for a in (reference.authors or []) if _family(a) or _given(a)]
    if not authors:
        return ""
    if style == "apa":
        names = [f"{_family(a)}, {_initials(_given(a))}".strip(", ") for a in authors]
        if len(names) > 20:
            names = names[:19] + ["…", names[-1]]
        if len(names) == 1:
            return names[0]
        return (
            ", ".join(names[:-1]) + ", & " + names[-1]
            if len(names) > 2
            else f"{names[0]}, & {names[1]}"
        )
    if style == "mla":
        first = f"{_family(authors[0])}, {_given(authors[0])}".strip(", ")
        if len(authors) == 1:
            return first
        if len(authors) == 2:
            return f"{first}, and {_given(authors[1])} {_family(authors[1])}".replace(
                "  ", " "
            ).strip()
        return f"{first}, et al."
    if style == "chicago":
        first = f"{_family(authors[0])}, {_given(authors[0])}".strip(", ")
        rest = [f"{_given(a)} {_family(a)}".strip() for a in authors[1:]]
        if len(authors) > 10:
            return ", ".join([first] + rest[:6]) + ", et al."
        return _join([first] + rest, ", and " if len(authors) > 2 else " and ", oxford=False)
    if style == "harvard":
        names = [f"{_family(a)}, {_initials(_given(a), spaced=False)}".strip(", ") for a in authors]
        if len(names) > 3:
            return f"{names[0]} et al."
        return _join(names, " and ", oxford=False)
    if style == "vancouver":
        names = [f"{_family(a)} {_initials(_given(a), dots=False)}".strip() for a in authors]
        if len(names) > 6:
            return ", ".join(names[:6]) + ", et al."
        return ", ".join(names)
    if style == "ieee":
        names = [f"{_initials(_given(a))} {_family(a)}".strip() for a in authors]
        if len(names) > 6:
            return f"{names[0]} et al."
        return (
            _join(names, " and ", oxford=False)
            if len(names) <= 2
            else ", ".join(names[:-1]) + ", and " + names[-1]
        )
    raise ValueError(style)


def _vip(reference) -> tuple[str, str, str]:
    extra = reference.extra or {}
    return (
        str(extra.get("volume") or ""),
        str(extra.get("issue") or ""),
        str(extra.get("pages") or extra.get("page") or ""),
    )


def _doi_url(reference) -> str:
    if reference.doi:
        return f"https://doi.org/{reference.doi}"
    return reference.url or ""


def _year(reference) -> str:
    return str(reference.year) if reference.year else "n.d."


def _is_proceedings(reference) -> bool:
    return reference.entry_type in ("inproceedings", "incollection", "conference")


def _i(text: str, as_html: bool) -> str:
    """Italicise for HTML output; plain for text."""
    if not text:
        return ""
    return f"<i>{html.escape(text)}</i>" if as_html else text


def _e(text: str, as_html: bool) -> str:
    return html.escape(text) if as_html else text


def _entry(reference, style: str, as_html: bool) -> str:
    authors = _authors(reference, style)
    title = (reference.title or "Untitled").strip().rstrip(".")
    venue = (reference.venue or "").strip()
    year = _year(reference)
    volume, issue, pages = _vip(reference)
    doi = _doi_url(reference)
    proc = _is_proceedings(reference)

    if style == "apa":
        vol = f", {_i(volume, as_html)}" if volume else ""
        iss = f"({_e(issue, as_html)})" if issue and volume else ""
        pg = f", {_e(pages, as_html)}" if pages else ""
        if proc:
            src = f"In {_i(venue, as_html)}" if venue else ""
            core = f"{_e(title, as_html)}. {src}{pg}." if src else f"{_e(title, as_html)}{pg}."
        else:
            src = f"{_i(venue, as_html)}{vol}{iss}{pg}." if venue else ""
            core = f"{_e(title, as_html)}. {src}".strip()
        parts = [
            f"{_e(authors, as_html)} ({year})." if authors else f"{_e(title, as_html)}. ({year}).",
            core if authors else src,
        ]
        out = " ".join(p for p in parts if p)
        return f"{out} {_e(doi, as_html)}".strip()

    if style == "mla":
        container = _i(venue, as_html) if venue else ""
        vol = f", vol. {_e(volume, as_html)}" if volume else ""
        iss = f", no. {_e(issue, as_html)}" if issue else ""
        pg = f", pp. {_e(pages, as_html)}" if pages else ""
        loc = f", {_e(doi, as_html)}" if doi else ""
        head = f"{_e(authors, as_html)}. " if authors else ""
        tail = f" {container}{vol}{iss}, {year}{pg}{loc}." if container else f" {year}{pg}{loc}."
        return f"{head}“{_e(title, as_html)}.”{tail}".replace("..", ".")

    if style == "chicago":
        vol = f" {_e(volume, as_html)}" if volume else ""
        iss = f" ({_e(issue, as_html)})" if issue else ""
        pg = f": {_e(pages, as_html)}" if pages else ""
        src = (
            (f"In {_i(venue, as_html)}" if proc else f"{_i(venue, as_html)}{vol}{iss}{pg}")
            if venue
            else ""
        )
        head = f"{_e(authors, as_html)}. {year}. " if authors else f"{year}. "
        body = f"“{_e(title, as_html)}.”" + (f" {src}." if src else "")
        return f"{head}{body} {_e(doi, as_html)}".strip()

    if style == "harvard":
        vol = f", {_e(volume, as_html)}" if volume else ""
        iss = f"({_e(issue, as_html)})" if issue else ""
        pg = f", pp. {_e(pages, as_html)}" if pages else ""
        src = (
            (f"In: {_i(venue, as_html)}" if proc else f"{_i(venue, as_html)}{vol}{iss}{pg}")
            if venue
            else ""
        )
        head = f"{_e(authors, as_html)} ({year}) " if authors else f"({year}) "
        body = f"‘{_e(title, as_html)}’" + (f", {src}" if src else "") + "."
        tail = f" Available at: {_e(doi, as_html)}." if doi else ""
        return f"{head}{body}{tail}".strip()

    if style == "vancouver":
        vol = f";{_e(volume, as_html)}" if volume else ""
        iss = f"({_e(issue, as_html)})" if issue else ""
        pg = f":{_e(pages, as_html)}" if pages else ""
        src = (
            (f"In: {_e(venue, as_html)}" if proc else f"{_e(venue, as_html)}. {year}{vol}{iss}{pg}")
            if venue
            else str(year)
        )
        head = f"{_e(authors, as_html)}. " if authors else ""
        tail = f" doi:{_e(reference.doi, as_html)}" if reference.doi else ""
        return f"{head}{_e(title, as_html)}. {src}.{tail}".replace("..", ".")

    if style == "ieee":
        vol = f", vol. {_e(volume, as_html)}" if volume else ""
        iss = f", no. {_e(issue, as_html)}" if issue else ""
        pg = f", pp. {_e(pages, as_html)}" if pages else ""
        src = (
            (f"in {_i(venue, as_html)}" if proc else f"{_i(venue, as_html)}{vol}{iss}{pg}")
            if venue
            else ""
        )
        head = f"{_e(authors, as_html)}, " if authors else ""
        body = f"“{_e(title, as_html)},” " + (f"{src}, " if src else "") + f"{year}"
        tail = f", doi: {_e(reference.doi, as_html)}." if reference.doi else "."
        return f"{head}{body}{tail}"

    raise ValueError(f"Unknown style {style}")


def _intext(reference, style: str) -> str:
    authors = [a for a in (reference.authors or []) if _family(a)]
    year = _year(reference)
    fams = [_family(a) for a in authors]
    if not fams:
        # no author: a short title, cut at a word boundary
        words = (reference.title or "Untitled").split(":")[0].split()
        short = ""
        for w in words:
            if len(f"{short} {w}".strip()) > 40:
                break
            short = f"{short} {w}".strip()
        short = short or words[0][:40]
        return f"({short}, {year})" if style in ("apa", "harvard") else f"({short} {year})"
    if style in ("apa", "harvard"):
        if len(fams) == 1:
            who = fams[0]
        elif len(fams) == 2:
            who = f"{fams[0]} & {fams[1]}" if style == "apa" else f"{fams[0]} and {fams[1]}"
        else:
            who = f"{fams[0]} et al."
        return f"({who}, {year})"
    if style == "chicago":
        who = (
            fams[0]
            if len(fams) == 1
            else (f"{fams[0]} and {fams[1]}" if len(fams) == 2 else f"{fams[0]} et al.")
        )
        return f"({who} {year})"
    if style == "mla":
        who = (
            fams[0]
            if len(fams) == 1
            else (f"{fams[0]} and {fams[1]}" if len(fams) == 2 else f"{fams[0]} et al.")
        )
        return f"({who})"
    if style in ("vancouver", "ieee"):
        return "[n]"  # numbered styles: the number is the entry's position in the bibliography
    raise ValueError(style)


def cite(reference, style: str = "apa") -> dict:
    """{style, label, text, html, intext} for one reference."""
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}")
    return {
        "style": style,
        "label": STYLE_LABELS[style],
        "text": _entry(reference, style, as_html=False),
        "html": _entry(reference, style, as_html=True),
        "intext": _intext(reference, style),
    }


def bibliography(references, style: str = "apa") -> dict:
    """A whole bibliography: alphabetical for author-date styles, numbered in the given order
    for Vancouver/IEEE. Returns {style, entries[], text, html}."""
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}")
    refs = list(references)
    numbered = style in ("vancouver", "ieee")
    if not numbered:
        refs.sort(
            key=lambda r: (
                (_family(r.authors[0]) if r.authors else r.title or "").lower(),
                r.year or 0,
            )
        )
    entries = []
    for i, ref in enumerate(refs, start=1):
        one = cite(ref, style)
        if numbered:
            prefix = f"[{i}] " if style == "ieee" else f"{i}. "
            one["text"] = prefix + one["text"]
            one["html"] = prefix + one["html"]
            one["intext"] = f"[{i}]" if style == "ieee" else f"({i})"
        one["reference_id"] = ref.pk
        entries.append(one)
    return {
        "style": style,
        "label": STYLE_LABELS[style],
        "entries": entries,
        "text": "\n\n".join(e["text"] for e in entries),
        "html": "".join(f"<p>{e['html']}</p>" for e in entries),
    }
