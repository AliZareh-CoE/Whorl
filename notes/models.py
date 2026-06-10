from django.db import models

from core.models import TimeStampedModel
from projects.models import Project


class QuickCapture(TimeStampedModel):
    """Global inbox: jot it down now, file it during triage."""

    text = models.TextField()
    processed = models.BooleanField(default=False)
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="captures"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.text[:60]
