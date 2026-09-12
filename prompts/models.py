from django.db import models

from core.models import TimeStampedModel


class Prompt(TimeStampedModel):
    """A reusable prompt for Claude (or any LLM) — global, like the reference library."""

    title = models.CharField(max_length=200, unique=True)
    body = models.TextField()
    tags = models.CharField(
        max_length=300, blank=True, help_text="Comma-separated, e.g. writing, lit-review"
    )

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def variables(self) -> list[dict]:
        """Distinct {{placeholders}} in order of first appearance, each with its default:
        `{{venue|NeurIPS}}` fills "NeurIPS" unless the user types something (#393)."""
        return parse_variables(self.body or "")

    @property
    def variable_names(self) -> list[str]:
        return [v["name"] for v in self.variables]


VARIABLE_RE = r"\{\{\s*([a-zA-Z0-9_ -]{1,40}?)\s*(?:\|([^}]{0,200}?))?\s*\}\}"


def parse_variables(body: str) -> list[dict]:
    import re

    seen: dict[str, str] = {}
    for match in re.finditer(VARIABLE_RE, body):
        name = match.group(1).strip()
        default = (match.group(2) or "").strip()
        if not name:
            continue
        if name not in seen:
            seen[name] = default
        elif default and not seen[name]:
            seen[name] = default  # the first occurrence that carries a default wins
    return [{"name": name, "default": default} for name, default in seen.items()]


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
