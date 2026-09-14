"""One renderer for every markdown body Atlas shows (#407, backlog #45).

Notes had it first: ``[[Note Title]]`` becomes a link to the note (resolved inside the
project), ``@cite-key`` becomes a link to the paper, unresolved mentions stay visible in
italics, and the result goes through nh3. Decisions, experiment entries, protocols and
captures now share the same function, so a mention means the same thing everywhere.
"""

from __future__ import annotations

import html
import re

import markdown as md
import nh3

from notes.services import CITE_RE, WIKI_LINK_RE, parse_cite_keys

TAG_AT_LINE_START_RE = re.compile(r"^( {0,3})#(?=[A-Za-z])", re.MULTILINE)

# #509: research markdown — math, task boxes, callouts, footnotes and ==highlights== in every
# rendered body. Math is lifted out before Markdown runs (so `$a_i$` keeps its underscores)
# and put back as escaped TeX inside a marked element; the SPA renders it with KaTeX.
CODE_SEGMENT_RE = re.compile(r"(```.*?```|~~~.*?~~~|`[^`\n]*`)", re.DOTALL)
MATH_DISPLAY_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
MATH_INLINE_RE = re.compile(r"(?<![\\$\w])\$(?!\s)([^$\n]{1,500}?)(?<!\s)\$(?![\w$])")
HIGHLIGHT_RE = re.compile(r"==([^=\n]{1,200}?)==")
TASK_ITEM_RE = re.compile(r"<li>(<p>)?\[([ xX])\][ \t]")
TASK_MARK_RE = re.compile(r'<li class="task( task-done)?">')
BLOCKQUOTE_RE = re.compile(r"<blockquote>(.*?)</blockquote>", re.DOTALL)
CALLOUT_MARK_RE = re.compile(r"<p>\[!([A-Za-z]+)\][ \t]*([^\n<]*)(\n|</p>)")
CALLOUT_KINDS = {
    "note",
    "info",
    "tip",
    "success",
    "warning",
    "danger",
    "failure",
    "bug",
    "question",
    "example",
    "quote",
    "abstract",
    "todo",
}
CLASS_RE = re.compile(r"[a-z][\w-]*( [a-z][\w-]*)*")
MATH_TOKEN = "ATLASMATH{}X"
ALLOWED_ATTRIBUTES = {
    **nh3.ALLOWED_ATTRIBUTES,
    "*": {"class"},
    "li": {"id"},
    "sup": {"id"},
    "a": set(nh3.ALLOWED_ATTRIBUTES["a"]) | {"title"},
}


def _attribute_filter(tag: str, attribute: str, value: str):
    if attribute == "class":
        return value if CLASS_RE.fullmatch(value) else None
    if attribute == "id":
        return value if value.startswith(("fn:", "fnref:")) else None
    return value


def _lift_math(text: str) -> tuple[str, list[tuple[str, bool]]]:
    """Replace math outside code with tokens; returns the text and [(tex, display)]."""
    stash: list[tuple[str, bool]] = []

    def keep(match: re.Match, display: bool) -> str:
        stash.append((match.group(1).strip(), display))
        return MATH_TOKEN.format(len(stash) - 1)

    out = []
    for i, segment in enumerate(CODE_SEGMENT_RE.split(text)):
        if i % 2 == 1:  # code — leave every dollar alone
            out.append(segment)
            continue
        segment = MATH_DISPLAY_RE.sub(lambda m: keep(m, True), segment)
        segment = MATH_INLINE_RE.sub(lambda m: keep(m, False), segment)
        segment = HIGHLIGHT_RE.sub(r"<mark>\1</mark>", segment)
        out.append(segment)
    return "".join(out), stash


def _restore_math(html_text: str, stash: list[tuple[str, bool]]) -> str:
    for index, (tex, display) in enumerate(stash):
        token = MATH_TOKEN.format(index)
        escaped = html.escape(tex)
        if display:
            block = f'<div class="math-display">{escaped}</div>'
            html_text = html_text.replace(f"<p>{token}</p>", block).replace(token, block)
        else:
            html_text = html_text.replace(token, f'<span class="math-inline">{escaped}</span>')
    return html_text


def _callouts(match: re.Match) -> str:
    """One <blockquote> → plain quote and/or one callout per `[!kind]` marker inside it
    (Python-Markdown folds quotes separated by a blank line into one blockquote)."""
    inner = match.group(1)
    parts = CALLOUT_MARK_RE.split(inner)
    if len(parts) == 1:
        return match.group(0)
    out = []
    lead = parts[0].strip()
    if lead:
        out.append(f"<blockquote>{lead}</blockquote>")
    for i in range(1, len(parts), 4):
        kind, title, ending, rest = parts[i].lower(), parts[i + 1], parts[i + 2], parts[i + 3]
        kind = kind if kind in CALLOUT_KINDS else "note"
        title = title.strip() or kind.capitalize()
        body = ("<p>" if ending == "\n" else "") + rest.strip()
        out.append(
            f'<blockquote class="callout callout-{kind}"><p class="callout-title">{title}</p>'
            f"{body}</blockquote>"
        )
    return "\n".join(out)


def _task_item(match: re.Match) -> str:
    done = match.group(2) != " "
    return f'<li class="task{" task-done" if done else ""}">{match.group(1) or ""}'


def render_markdown(text: str, *, soft_breaks: bool = False) -> str:
    """Markdown → sanitized HTML: fenced code, tables, footnotes, $math$, - [ ] tasks,
    > [!kind] callouts and ==highlights== (optional newline = <br>)."""
    if not text:
        return ""
    extensions = ["fenced_code", "tables", "footnotes"] + (["nl2br"] if soft_breaks else [])
    # #507: a line that starts with a #tag (no space after the hash) is a tag, not a heading
    text = TAG_AT_LINE_START_RE.sub(r"\1\\#", text)
    text, stash = _lift_math(text)
    rendered = md.markdown(text, extensions=extensions)
    rendered = TASK_ITEM_RE.sub(_task_item, rendered)
    rendered = BLOCKQUOTE_RE.sub(_callouts, rendered)
    rendered = _restore_math(rendered, stash)
    clean = nh3.clean(rendered, attributes=ALLOWED_ATTRIBUTES, attribute_filter=_attribute_filter)
    # the boxes go in after sanitising — nh3 never sees an <input>, only our own class
    return TASK_MARK_RE.sub(
        lambda m: (
            m.group(0)
            + '<input type="checkbox" disabled'
            + (" checked" if m.group(1) else "")
            + "> "
        ),
        clean,
    )


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
