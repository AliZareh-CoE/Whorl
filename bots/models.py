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


class BotRun(models.Model):
    """One execution of a bot — the Automations page shows recent history."""

    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="runs")
    started_at = models.DateTimeField(auto_now_add=True)
    ok = models.BooleanField(default=True)
    result = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.bot.slug} @ {self.started_at:%Y-%m-%d %H:%M}: {self.result[:40]}"
