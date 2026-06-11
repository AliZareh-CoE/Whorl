"""Resolve [[Note Title]] and @cite-key mentions into markdown links (Backlog #20).

Runs before markdownify, so the output is plain markdown and goes through the
same nh3 sanitization as everything else.
"""

import re

from notes.services import WIKI_LINK_RE

CITE_KEY_RE = re.compile(r"(?<![\w@])@([A-Za-z][\w-]{2,})")


def resolve_mentions(body: str) -> str:
    """Replace [[Title]] with a note link (when exactly one note matches) and
    @cite-key with a reference link. Unresolved mentions are left untouched."""
    if not body:
        return ""
    from literature.models import Reference
    from notes.models import Note

    def replace_wiki(match):
        title = match.group(1).strip()
        notes = list(Note.objects.filter(title__iexact=title)[:2])
        if len(notes) == 1:
            return f"[{title}]({notes[0].get_absolute_url()})"
        return match.group(0)  # missing or ambiguous across projects — leave as typed

    def replace_cite(match):
        key = match.group(1)
        reference = Reference.objects.filter(bibtex_key__iexact=key).first()
        if reference:
            return f"[@{key}]({reference.get_absolute_url()})"
        return match.group(0)

    return CITE_KEY_RE.sub(replace_cite, WIKI_LINK_RE.sub(replace_wiki, body))
