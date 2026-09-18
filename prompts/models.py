from django.db import models

from core.models import TimeStampedModel


class Prompt(TimeStampedModel):
    """A reusable prompt for Claude (or any LLM) — global, like the reference library."""

    title = models.CharField(max_length=200, unique=True)
    body = models.TextField()
    tags = models.CharField(
        max_length=300, blank=True, help_text="Comma-separated, e.g. writing, lit-review"
    )
    # #563: how often and when last the prompt was copied (a successful render) — the
    # gallery's Recent strip and the "used N×" chip; a use never touches updated_at
    use_count = models.PositiveIntegerField(default=0, editable=False)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def variables(self) -> list[dict]:
        """Distinct {{placeholders}} in order of first appearance, each with its kind and
        default: `{{venue|NeurIPS}}` fills "NeurIPS" unless the user types something (#393);
        `{{paper:reference}}` is picked from the library and expands to the paper's
        title, authors, venue and abstract at copy time (#562)."""
        return parse_variables(self.body or "")

    @property
    def variable_names(self) -> list[str]:
        return [v["name"] for v in self.variables]


# {{name}}, {{name|default}}, {{name:kind}}, {{name:kind|default}} — the kind (#562) says what
# the fill-in is picked from: a paper in the library, a note, a project, a manuscript; text
# (the default, and any unknown kind) is typed
VARIABLE_RE = (
    r"\{\{\s*([a-zA-Z0-9_ -]{1,40}?)\s*(?::\s*([a-zA-Z]{1,20})\s*)?(?:\|([^}]{0,200}?))?\s*\}\}"
)
KINDS = ("text", "reference", "note", "project", "manuscript")


def parse_variables(body: str) -> list[dict]:
    import re

    seen: dict[str, dict] = {}
    for match in re.finditer(VARIABLE_RE, body):
        name = match.group(1).strip()
        kind = (match.group(2) or "").strip().lower()
        kind = kind if kind in KINDS else "text"
        default = (match.group(3) or "").strip()
        if not name:
            continue
        if name not in seen:
            seen[name] = {"name": name, "kind": kind, "default": default}
            continue
        row = seen[name]
        if default and not row["default"]:
            row["default"] = default  # the first occurrence that carries a default wins
        if kind != "text" and row["kind"] == "text":
            row["kind"] = kind  # …and the first occurrence that names a kind
    return list(seen.values())


def render_prompt(body: str, values: dict | None = None) -> str:
    """Substitute {{name}} / {{name|default}}: the given value, else the default, else the
    bare placeholder stays as {{name}} so it is still visible."""
    import re

    values = values or {}
    defaults = {v["name"]: v["default"] for v in parse_variables(body or "")}

    def sub(match):
        name = match.group(1).strip()
        value = str(values.get(name, "")).strip()
        return value or defaults.get(name, "") or "{{" + name + "}}"

    return re.sub(VARIABLE_RE, sub, body or "")
