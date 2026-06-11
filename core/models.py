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

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return self.body[:60]
