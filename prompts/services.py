"""#562: typed prompt variables filled from Atlas itself — a `{{paper:reference}}` picked from
the library expands to the paper's title, authors, venue and abstract at copy time; a note,
a project or a manuscript likewise. `render_prompt` in models stays pure; this module is the
one place that reads rows, shared by the API's render endpoint, the SPA's Copy and Claude."""

from __future__ import annotations

from django.db.models import F
from django.utils import timezone

from core.ids import MAX_PK

from .models import Prompt, parse_variables, render_prompt

EXPANSION_CAP = 50_000  # characters per fill-in — the same cap the note preview uses


class PromptError(ValueError):
    pass


def _lines(*parts: str) -> str:
    return "\n".join(p for p in parts if p)


def _titled(title: str, body: str) -> str:
    """A title, a blank line, the body — the body alone when there is no title, the title
    alone when there is no body."""
    return f"{title}\n\n{body}" if title and body else (title or body or "")


def expand_reference(ref) -> str:
    head = ref.title or ""
    bits = ", ".join(p for p in (ref.author_names, str(ref.year) if ref.year else "") if p)
    if bits:
        head = f"{head} ({bits})" if head else bits
    return _lines(
        f"{head}." if head and not head.endswith(".") else head,
        f"{ref.venue}." if ref.venue else "",
        f"doi:{ref.doi}" if ref.doi else "",
        f"Abstract: {ref.abstract}" if ref.abstract else "",
    )


def expand_value(kind: str, raw, name: str = "") -> tuple[str, str]:
    """(text, label) for one fill-in. A typed kind whose value is an id reads the row; any
    other value is used as typed, so Claude may pass a title it has no id for."""
    value = str(raw if raw is not None else "").strip()
    if kind == "text" or not value.isdigit():
        return value, value
    pk = int(value)
    if pk <= 0 or pk > MAX_PK:
        raise PromptError(f"No {kind} with id {value} for {name or kind}.")
    if kind == "reference":
        from literature.models import Reference

        row = Reference.objects.filter(pk=pk).first()
        return (expand_reference(row), row.title) if row else (None, None)
    if kind == "note":
        from notes.models import Note

        row = Note.objects.filter(pk=pk).first()
        return (_titled(row.title, row.body), row.title) if row else (None, None)
    if kind == "project":
        from projects.models import Project

        row = Project.objects.filter(pk=pk).first()
        return (_titled(row.name, row.description), row.name) if row else (None, None)
    if kind == "manuscript":
        from writing.models import Manuscript

        row = Manuscript.objects.filter(pk=pk).first()
        return (_titled(row.title, row.abstract), row.title) if row else (None, None)
    return value, value


def render_with_data(prompt: Prompt, values: dict | None) -> dict:
    """The prompt's text with every fill-in applied — typed values expanded from their rows,
    text values as typed, defaults where nothing was given, the bare placeholder where
    neither exists — plus the resolved variables for a client to show."""
    if values is None:
        values = {}
    if not isinstance(values, dict):
        raise PromptError("values must be an object of name → value.")
    rows = parse_variables(prompt.body or "")
    filled: dict[str, str] = {}
    out = []
    for var in rows:
        raw = values.get(var["name"])
        text, label = expand_value(var["kind"], raw, var["name"])
        if text is None:
            raise PromptError(f"No {var['kind']} with id {raw} for {var['name']}.")
        text = text[:EXPANSION_CAP]
        if text:
            filled[var["name"]] = text
        out.append({**var, "value": str(raw if raw is not None else ""), "label": label or ""})
    return {"text": render_prompt(prompt.body or "", filled), "variables": out}


def record_use(prompt: Prompt) -> Prompt:
    """#563: one more use, now — called after a render succeeded (a 404 for a missing row
    does not count). An F() increment survives two copies landing at once; save() rather
    than update() so the ETag data version bumps; update_fields keeps auto_now off
    updated_at, so "used" stays distinct from "edited"."""
    prompt.use_count = F("use_count") + 1
    prompt.last_used_at = timezone.now()
    prompt.save(update_fields=["use_count", "last_used_at"])
    prompt.refresh_from_db(fields=["use_count", "last_used_at"])
    return prompt
