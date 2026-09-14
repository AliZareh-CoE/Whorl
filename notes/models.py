from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.urls import reverse

from core.models import TimeStampedModel
from literature.models import Reference
from projects.models import Project


class Note(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=300)
    body = models.TextField(blank=True)  # markdown; [[Title]] creates links
    references = models.ManyToManyField(Reference, blank=True, related_name="notes")

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "title"], name="unique_note_title_per_project"
            ),
        ]
        indexes = [GinIndex(fields=["title"], opclasses=["gin_trgm_ops"], name="note_title_trgm")]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("notes:detail", kwargs={"slug": self.project.slug, "pk": self.pk})


class NoteLink(models.Model):
    """Parsed from [[wiki-links]] on save."""

    source = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="outgoing_links")
    target = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="incoming_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "target"], name="unique_note_link"),
        ]

    def __str__(self):
        return f"{self.source.title} → {self.target.title}"


class QuickCapture(TimeStampedModel):
    """Global inbox: jot it down now, file it during triage."""

    text = models.TextField()
    processed = models.BooleanField(default=False)
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="captures"
    )
    # #423: the bot run that filed this capture (null for hand-written ones), so a bar on the
    # Automations chart can open the Inbox filtered to exactly what that run produced
    bot_run = models.ForeignKey(
        "bots.BotRun", on_delete=models.SET_NULL, null=True, blank=True, related_name="captures"
    )
    # #495: "not now" — hidden from the inbox and every untriaged count until this day
    snoozed_until = models.DateField(null=True, blank=True)
    # #496: what the capture became when it was converted (reference / note / todo /
    # milestone / decision + that object's id) and when it left the inbox, so "what happened
    # to that thought?" has an answer
    became_kind = models.CharField(max_length=20, blank=True)
    became_id = models.PositiveIntegerField(null=True, blank=True)
    triaged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.text[:60]
