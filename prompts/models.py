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
