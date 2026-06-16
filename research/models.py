from datetime import date

from django.db import models

from core.models import TimeStampedModel
from documents.models import Document
from literature.models import Reference
from notes.models import Note
from projects.models import Project


class Hypothesis(TimeStampedModel):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        TESTING = "testing", "Testing"
        SUPPORTED = "supported", "Supported"
        CONTRADICTED = "contradicted", "Contradicted"
        INCONCLUSIVE = "inconclusive", "Inconclusive"
        ABANDONED = "abandoned", "Abandoned"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="hypotheses")
    statement = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)

    class Meta:
        ordering = ["pk"]
        verbose_name_plural = "hypotheses"

    def __str__(self):
        return self.statement[:80]

    def get_absolute_url(self):
        from django.urls import reverse

        return f"{reverse('research:ledger', args=[self.project.slug])}#hypothesis-{self.pk}"

    @property
    def evidence_balance(self):
        counts = {"supports": 0, "contradicts": 0, "mixed": 0}
        for item in self.evidence.all():
            counts[item.direction] += 1
        return counts

    @property
    def suggested_status(self):
        """Suggested from evidence balance; the stored status always wins in the UI."""
        balance = self.evidence_balance
        total = sum(balance.values())
        if total == 0:
            return None
        if balance["mixed"] or (balance["supports"] and balance["contradicts"]):
            return self.Status.INCONCLUSIVE
        if balance["supports"]:
            return self.Status.SUPPORTED
        return self.Status.CONTRADICTED


class Evidence(TimeStampedModel):
    class Direction(models.TextChoices):
        SUPPORTS = "supports", "Supports"
        CONTRADICTS = "contradicts", "Contradicts"
        MIXED = "mixed", "Mixed"

    hypothesis = models.ForeignKey(Hypothesis, on_delete=models.CASCADE, related_name="evidence")
    direction = models.CharField(max_length=12, choices=Direction.choices)
    summary = models.TextField()
    reference = models.ForeignKey(
        Reference, on_delete=models.SET_NULL, null=True, blank=True, related_name="evidence"
    )
    note = models.ForeignKey(
        Note, on_delete=models.SET_NULL, null=True, blank=True, related_name="evidence"
    )
    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, null=True, blank=True, related_name="evidence"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "evidence"

    def __str__(self):
        return f"{self.direction}: {self.summary[:60]}"


class ExperimentEntry(TimeStampedModel):
    """Lab-notebook style dated entries."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="experiment_entries"
    )
    date = models.DateField(default=date.today)
    title = models.CharField(max_length=300)
    body = models.TextField(blank=True)  # markdown: setup, what happened, outcome
    hypotheses = models.ManyToManyField(Hypothesis, blank=True, related_name="experiments")
    # link a lab-notebook entry to the exact code that produced it (#4). Just a pasted URL —
    # no GitHub API call — so it works for any host and offline; commit_label prettifies it.
    commit_url = models.URLField(blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "experiment entries"

    def __str__(self):
        return f"{self.date}: {self.title}"

    @property
    def commit_label(self):
        """A compact label for commit_url — ``owner/repo@shortsha`` for a GitHub/GitLab
        commit link, else the host. Empty when no commit is linked."""
        if not self.commit_url:
            return ""
        from urllib.parse import urlparse

        parsed = urlparse(self.commit_url)
        segs = [s for s in parsed.path.split("/") if s]
        if "commit" in segs:
            i = segs.index("commit")
            sha = segs[i + 1][:7] if i + 1 < len(segs) else ""
            repo = "/".join(segs[:2]) if i >= 2 else ""
            if repo and sha:
                return f"{repo}@{sha}"
            if sha:
                return sha
        return parsed.netloc or self.commit_url

    def get_absolute_url(self):
        from django.urls import reverse

        return f"{reverse('research:experiments', args=[self.project.slug])}#experiment-{self.pk}"


class Dataset(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="datasets")
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=500)  # path or URL
    version = models.CharField(max_length=60, blank=True)
    checksum = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Protocol(TimeStampedModel):
    """A versioned lab/analysis protocol (Backlog #7).

    Protocols are append-only: editing a protocol means creating a new version (via
    ``new_version``) that points back to its ``parent``, so the exact steps a past
    experiment followed are never overwritten. The newest version in a chain — the one no
    other version names as its parent — is the *current* one.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="protocols")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)  # markdown: the steps
    version = models.PositiveIntegerField(default=1)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="revisions"
    )

    class Meta:
        ordering = ["title", "-version"]

    def __str__(self):
        return f"{self.title} v{self.version}"

    @property
    def is_current(self):
        """True when no later version derives from this one (it's the head of its chain)."""
        return not self.revisions.exists()

    def new_version(self, **changes):
        """Create and return the next version, carrying fields over unless overridden."""
        return Protocol.objects.create(
            project=self.project,
            title=changes.get("title", self.title),
            body=changes.get("body", self.body),
            version=self.version + 1,
            parent=self,
        )
