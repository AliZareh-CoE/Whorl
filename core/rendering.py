"""One renderer for every markdown body Atlas shows (#407, backlog #45).

Notes had it first: ``[[Note Title]]`` becomes a link to the note (resolved inside the
project), ``@cite-key`` becomes a link to the paper, unresolved mentions stay visible in
italics, and the result goes through nh3. Decisions, experiment entries, protocols and
captures now share the same function, so a mention means the same thing everywhere.
"""

from __future__ import annotations

import re

import markdown as md
import nh3

from notes.services import CITE_RE, WIKI_LINK_RE, parse_cite_keys

TAG_AT_LINE_START_RE = re.compile(r"^( {0,3})#(?=[A-Za-z])", re.MULTILINE)


def render_markdown(text: str, *, soft_breaks: bool = False) -> str:
    """Markdown → sanitized HTML (fenced code + tables; optional newline = <br>)."""
    if not text:
        return ""
    extensions = ["fenced_code", "tables"] + (["nl2br"] if soft_breaks else [])
    # #507: a line that starts with a #tag (no space after the hash) is a tag, not a heading
    text = TAG_AT_LINE_START_RE.sub(r"\1\\#", text)
    return nh3.clean(md.markdown(text, extensions=extensions))


def resolve_mentions(body: str, project=None) -> str:
    """Rewrite ``[[Title]]`` and ``@key`` into markdown links. With a project, wiki-links
    resolve against that project's notes; without one, against every note (only when the
    title is unique). Unresolved mentions are emphasised so the gap is visible."""
    if not body:
        return ""
    from literature.models import Reference
    from notes.models import Note

    if "[[" in body:
        if project is not None:
            by_title = {n.title.lower(): n for n in project.notes.all()}
        else:
            by_title = {}
            ambiguous: set[str] = set()
            for note in Note.objects.select_related("project"):
                key = note.title.lower()
                if key in by_title:
                    ambiguous.add(key)
                by_title[key] = note
            for key in ambiguous:
                by_title.pop(key, None)

        def wiki(match: re.Match) -> str:
            title = match.group(1).strip()
            target = by_title.get(title.lower())
            if target:
                return f"[{title}]({target.get_absolute_url()})"
            return f"*[[{title}]]*"

        body = WIKI_LINK_RE.sub(wiki, body)

    keys = parse_cite_keys(body)
    if keys:
        refs = {r.bibtex_key.lower(): r for r in Reference.objects.filter(bibtex_key__in=keys)}

        def cite(match: re.Match) -> str:
            key = match.group(1).rstrip(".")
            ref = refs.get(key.lower())
            if ref:
                title = ref.title.replace('"', "'")
                return f'[@{key}]({ref.get_absolute_url()} "{title}")'
            return f"*@{key}*"

        body = CITE_RE.sub(cite, body)
    return body


def render_body(body: str, project=None, *, soft_breaks: bool = False) -> str:
    """Mentions resolved, markdown rendered, HTML sanitized — the field to show."""
    return render_markdown(resolve_mentions(body, project), soft_breaks=soft_breaks)
