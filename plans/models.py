from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from projects.models import Project


class Phase(TimeStampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        BLOCKED = "blocked", "Blocked"
        DONE = "done", "Done"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="phases")
    name = models.CharField(max_length=200)
    order = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    objective = models.TextField(blank=True)  # markdown
    target_start = models.DateField(null=True, blank=True)
    target_end = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name

    @property
    def milestone_counts(self):
        milestones = list(self.milestones.all())
        done = sum(1 for m in milestones if m.completed_at)
        return done, len(milestones)

    @property
    def progress(self):
        """Completed milestones / total milestones, as a 0–100 int for progress bars."""
        done, total = self.milestone_counts
        return round(100 * done / total) if total else 0


class Milestone(TimeStampedModel):
    phase = models.ForeignKey(Phase, on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=300)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # #512: dependencies — a milestone is blocked while any of these is not complete
    blocked_by = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="blocks"
    )

    class Meta:
        ordering = ["due_date", "pk"]

    def __str__(self):
        return self.title

    # #516: the due date as it was loaded, so save() can log a move without a second query
    _due_loaded = None

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._due_loaded = instance.due_date if "due_date" in field_names else None
        return instance

    def save(self, *args, **kwargs):
        existed = self.pk is not None
        update_fields = kwargs.get("update_fields")
        super().save(*args, **kwargs)
        if existed and (update_fields is None or "due_date" in update_fields):
            if self.due_date != self._due_loaded:
                from .drift import record_move

                record_move(self, self._due_loaded, self.due_date)
        self._due_loaded = self.due_date

    @property
    def is_overdue(self):
        return bool(
            self.due_date and not self.completed_at and self.due_date < timezone.localdate()
        )

    def toggle_completed(self):
        self.completed_at = None if self.completed_at else timezone.now()
        self.save(update_fields=["completed_at", "updated_at"])


class MilestoneDateChange(models.Model):
    """#516: one due-date move of a milestone — what the date was, what it became, when. The
    first row's `from_date` is the milestone's baseline; the plan's drift is read from these."""

    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name="date_changes")
    from_date = models.DateField(null=True, blank=True)
    to_date = models.DateField(null=True, blank=True)
    changed_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["changed_at", "pk"]

    def __str__(self):
        return f"{self.milestone_id}: {self.from_date} → {self.to_date}"


class Task(TimeStampedModel):
    """Optional leaf nodes only — never the center of the product."""

    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=300)
    done = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return self.title


class ResearchQuestion(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PARTIALLY_ANSWERED = "partially_answered", "Partially answered"
        ANSWERED = "answered", "Answered"
        ABANDONED = "abandoned", "Abandoned"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="questions")
    question = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    phases = models.ManyToManyField(Phase, blank=True, related_name="questions")

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.question[:80]

    def get_absolute_url(self):
        from django.urls import reverse

        return f"{reverse('plans:questions', args=[self.project.slug])}#question-{self.pk}"
