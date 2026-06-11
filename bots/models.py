from django.db import models

from core.models import TimeStampedModel


class Bot(TimeStampedModel):
    """State row for one automation; behavior lives in bots/registry.py."""

    slug = models.SlugField(unique=True)
    enabled = models.BooleanField(default=False)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_result = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return f"{self.slug} ({'on' if self.enabled else 'off'})"
