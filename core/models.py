from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Comment(TimeStampedModel):
    """A comment anchored to any Atlas object (note, reference, manuscript, ...)."""

    from django.contrib.contenttypes.fields import GenericForeignKey
    from django.contrib.contenttypes.models import ContentType

    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE, related_name="atlas_comments"
    )
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    body = models.TextField()  # markdown
    page = models.PositiveIntegerField(null=True, blank=True)  # PDF page anchor (reader)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return self.body[:60]


class Pet(TimeStampedModel):
    """The single Atlas companion (Owner idea #12). State is derived; only the name is stored."""

    name = models.CharField(max_length=40, default="Mochi")

    def __str__(self):
        return self.name


class TodoItem(TimeStampedModel):
    """The owner's personal "Today" list (owner request, 2026-09-06): one plain list of things
    to do, ticked off with one click, never lost overnight. Deliberately NOT a plan task —
    plans stay about research; this is the ADHD-friendly scratch list for the day."""

    text = models.CharField(max_length=300)
    done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="todo_items",
    )

    class Meta:
        ordering = ["done", "position", "id"]

    def __str__(self):
        return self.text

    def mark(self, done: bool) -> None:
        from django.utils import timezone

        self.done = done
        self.done_at = timezone.now() if done else None
        self.save(update_fields=["done", "done_at", "updated_at"])
