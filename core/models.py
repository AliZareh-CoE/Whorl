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
    # #415: when the mode was last switched on — the souls-only trophies count from here
    souls_since = models.DateTimeField(null=True, blank=True)

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
    # #431: an optional time ("call Sam at 3pm") — the sidebar nudges when it comes close
    due_at = models.DateTimeField(null=True, blank=True)
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


class FeedToken(models.Model):
    """The read-only token calendar apps use in the .ics URL (2026-09-07, #401 — backlog
    #253). One row; rotating it makes every previously copied URL stop working. The API key
    stays out of URLs that calendar services store on their servers."""

    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"feed token from {self.created_at:%Y-%m-%d}"

    @classmethod
    def current(cls) -> str:
        import secrets

        row = cls.objects.order_by("-created_at", "-id").first()
        if row is None:
            row = cls.objects.create(token=secrets.token_urlsafe(24))
        return row.token

    @classmethod
    def rotate(cls) -> str:
        import secrets

        cls.objects.all().delete()
        return cls.objects.create(token=secrets.token_urlsafe(24)).token

    @classmethod
    def matches(cls, candidate: str) -> bool:
        from django.utils.crypto import constant_time_compare

        if not candidate:
            return False
        row = cls.objects.order_by("-created_at", "-id").first()
        return bool(row) and constant_time_compare(candidate, row.token)


class BackupRecord(models.Model):
    """One row per backup downloaded (#424) — so the app can say when the last one was and
    nudge, calmly, when it has been a while."""

    created_at = models.DateTimeField(auto_now_add=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    media_files = models.PositiveIntegerField(default=0)
    database = models.CharField(max_length=20, blank=True)  # sqlite / json

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"backup {self.created_at:%Y-%m-%d %H:%M} ({self.size_bytes} B)"
