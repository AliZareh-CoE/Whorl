from datetime import date

from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from core.models import TimeStampedModel


class Project(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETE = "complete", "Complete"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)  # markdown
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    color = models.CharField(max_length=7, default="#4f46e5")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "project"
            slug = base
            n = 2
            while Project.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("projects:overview", kwargs={"slug": self.slug})


class DecisionRecord(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="decisions")
    title = models.CharField(max_length=300)
    context = models.TextField(blank=True)  # markdown: the situation
    decision = models.TextField()  # markdown: what was decided
    alternatives = models.TextField(blank=True)  # markdown: what was rejected and why
    decided_on = models.DateField(default=date.today)

    class Meta:
        ordering = ["-decided_on", "-created_at"]

    def __str__(self):
        return self.title
