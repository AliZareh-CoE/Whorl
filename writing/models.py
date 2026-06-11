from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import TimeStampedModel
from literature.models import Reference
from projects.models import Project


class Manuscript(TimeStampedModel):
    class Status(models.TextChoices):
        IDEA = "idea", "Idea"
        OUTLINING = "outlining", "Outlining"
        DRAFTING = "drafting", "Drafting"
        INTERNAL_REVIEW = "internal_review", "Internal review"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        REVISION = "revision", "Revision"
        ACCEPTED = "accepted", "Accepted"
        PUBLISHED = "published", "Published"
        SHELVED = "shelved", "Shelved"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="manuscripts")
    title = models.CharField(max_length=400)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IDEA)
    target_venue = models.CharField(max_length=300, blank=True)
    deadline = models.DateField(null=True, blank=True)
    abstract = models.TextField(blank=True)
    repo_url = models.URLField(blank=True)
    latex_source = models.TextField(blank=True)  # edited in the in-browser LaTeX editor
    references = models.ManyToManyField(Reference, through="ManuscriptReference", blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("writing:detail", kwargs={"slug": self.project.slug, "pk": self.pk})

    @property
    def days_to_deadline(self):
        if not self.deadline:
            return None
        return (self.deadline - timezone.localdate()).days


class ManuscriptReference(models.Model):
    manuscript = models.ForeignKey(Manuscript, on_delete=models.CASCADE)
    reference = models.ForeignKey(Reference, on_delete=models.CASCADE)
    cite_key_override = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["manuscript", "reference"], name="unique_reference_per_manuscript"
            ),
        ]

    def __str__(self):
        return f"{self.manuscript.title[:30]} ← {self.cite_key}"

    @property
    def cite_key(self):
        return self.cite_key_override or self.reference.bibtex_key


class SubmissionEvent(TimeStampedModel):
    class Kind(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        DESK_REJECT = "desk_reject", "Desk reject"
        REVIEWS_RECEIVED = "reviews_received", "Reviews received"
        REVISION_SUBMITTED = "revision_submitted", "Revision submitted"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        PUBLISHED = "published", "Published"
        NOTE = "note", "Note"

    manuscript = models.ForeignKey(Manuscript, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    date = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.manuscript.title[:30]}: {self.kind} on {self.date}"
