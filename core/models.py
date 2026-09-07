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
    """The single Atlas companion (Owner idea #12). State is derived; only the name and the
    owner's chosen mode are stored."""

    name = models.CharField(max_length=40, default="Mochi")
    # Souls mode (owner, 2026-09-07): grim, dramatic tone — deaths, bonfires, bosses.
    souls_mode = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class AchievementUnlock(models.Model):
    """When an achievement was first seen unlocked (achievements themselves are derived from
    the data; this row only remembers the moment, for "new" badges and the ledger's order)."""

    key = models.CharField(max_length=60, unique=True)
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-unlocked_at"]

    def __str__(self):
        return self.key


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


class AccessEvent(models.Model):
    """Who touched the door (2026-09-07, #399 — backlog #42): logins, lockouts and rejected
    API keys, kept to the last few hundred rows and shown on Diagnostics › Access."""

    class Kind(models.TextChoices):
        LOGIN_OK = "login_ok", "Login"
        LOGIN_FAILED = "login_failed", "Failed login"
        LOGIN_LOCKED = "login_locked", "Login locked out"
        API_KEY_REJECTED = "api_key_rejected", "API key rejected"

    kind = models.CharField(max_length=24, choices=Kind.choices)
    address = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    detail = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_kind_display()} from {self.address or '?'} at {self.created_at:%Y-%m-%d %H:%M}"
