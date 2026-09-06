from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.urls import reverse

from core.models import TimeStampedModel
from projects.models import Project


def reference_pdf_path(instance, filename):
    return f"library/pdfs/{instance.bibtex_key}/{filename}"


class LibraryTag(TimeStampedModel):
    """A label on library references (Library v2 slice 5): global, case-insensitive-unique,
    optional colour. Distinct from documents.Tag (per-project document tags)."""

    name = models.CharField(max_length=60, unique=True)
    color = models.CharField(max_length=7, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def get_or_create_named(cls, name: str) -> "LibraryTag":
        clean = " ".join((name or "").split()).strip()[:60]
        if not clean:
            raise ValueError("A tag needs a name.")
        existing = cls.objects.filter(name__iexact=clean).first()
        return existing or cls.objects.create(name=clean)


class SavedView(TimeStampedModel):
    """A named set of Library filters ("smart view"): the rail lists them, one click restores
    the exact query. `params` holds the same keys the list endpoint accepts."""

    name = models.CharField(max_length=80, unique=True)
    params = models.JSONField(default=dict)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class Reference(TimeStampedModel):
    """One paper/book/etc. in the GLOBAL library, shared across projects."""

    # unique-but-optional: null (not "") so multiple references may lack a DOI
    doi = models.CharField(max_length=255, unique=True, null=True, blank=True)  # noqa: DJ001
    arxiv_id = models.CharField(max_length=50, blank=True, default="")
    openalex_id = models.CharField(max_length=50, blank=True, default="")
    bibtex_key = models.CharField(max_length=120, unique=True)
    entry_type = models.CharField(max_length=30, default="article")
    title = models.TextField()
    authors = models.JSONField(default=list)  # [{"family": "...", "given": "..."}]
    year = models.PositiveIntegerField(null=True, blank=True)
    venue = models.CharField(max_length=300, blank=True)
    abstract = models.TextField(blank=True)
    url = models.URLField(blank=True)
    pdf = models.FileField(upload_to=reference_pdf_path, null=True, blank=True)
    raw_bibtex = models.TextField(blank=True)
    extra = models.JSONField(default=dict)
    citation_count = models.PositiveIntegerField(null=True, blank=True)
    tags = models.ManyToManyField(LibraryTag, blank=True, related_name="references")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            GinIndex(fields=["title"], opclasses=["gin_trgm_ops"], name="reference_title_trgm")
        ]

    def __str__(self):
        return f"{self.bibtex_key}: {self.title[:60]}"

    def get_absolute_url(self):
        return reverse("literature:detail", kwargs={"pk": self.pk})

    @property
    def author_names(self):
        return ", ".join(
            " ".join(filter(None, [a.get("given", ""), a.get("family", "")])) for a in self.authors
        )


class ProjectReference(TimeStampedModel):
    """Per-project link to a global reference, with reading state."""

    class ReadingStatus(models.TextChoices):
        TO_READ = "to_read", "To read"
        SKIMMED = "skimmed", "Skimmed"
        READ = "read", "Read"
        ANNOTATED = "annotated", "Annotated"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="project_references"
    )
    reference = models.ForeignKey(Reference, on_delete=models.CASCADE, related_name="project_links")
    reading_status = models.CharField(
        max_length=20, choices=ReadingStatus.choices, default=ReadingStatus.TO_READ
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "reference"], name="unique_reference_per_project"
            ),
        ]

    def __str__(self):
        return f"{self.project.slug} ← {self.reference.bibtex_key}"


class CitationEdge(models.Model):
    """citing → cited, fetched from OpenAlex (synced in Phase 3)."""

    citing = models.ForeignKey(
        Reference, on_delete=models.CASCADE, related_name="outgoing_citations"
    )
    cited = models.ForeignKey(
        Reference, on_delete=models.CASCADE, related_name="incoming_citations"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["citing", "cited"], name="unique_citation_edge"),
        ]

    def __str__(self):
        return f"{self.citing.bibtex_key} → {self.cited.bibtex_key}"


class CitationSyncState(TimeStampedModel):
    """Per-project state of the OpenAlex citation-edge sync."""

    class Status(models.TextChoices):
        IDLE = "idle", "Never synced"
        SYNCING = "syncing", "Syncing"
        DONE = "done", "Synced"
        FAILED = "failed", "Failed"

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="citation_sync")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.IDLE)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    message = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"{self.project.slug}: {self.status}"


class ReviewTheme(TimeStampedModel):
    """A column in the project's literature review matrix (a theme/topic/method)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="review_themes")
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="unique_theme_per_project"),
        ]

    def __str__(self):
        return self.name


class ReviewMark(TimeStampedModel):
    """One cell of the review matrix: this paper addresses this theme (with an optional note)."""

    theme = models.ForeignKey(ReviewTheme, on_delete=models.CASCADE, related_name="marks")
    project_reference = models.ForeignKey(
        ProjectReference, on_delete=models.CASCADE, related_name="review_marks"
    )
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["theme", "project_reference"], name="unique_mark_per_cell"
            ),
        ]

    def __str__(self):
        return f"{self.project_reference.reference.bibtex_key} × {self.theme.name}"


class Highlight(TimeStampedModel):
    """A passage marked while reading a PDF (Library v2 slice 7).

    Structured, unlike the older "append to a highlights note" flow, so the workbench can list,
    jump to, comment on, and export highlights per paper. When a project is given the passage is
    still mirrored into that project's highlights note so it stays in the wiki-link graph.
    """

    class Color(models.TextChoices):
        YELLOW = "yellow", "Yellow"
        GREEN = "green", "Green"
        BLUE = "blue", "Blue"
        PINK = "pink", "Pink"

    reference = models.ForeignKey(Reference, on_delete=models.CASCADE, related_name="highlights")
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="highlights"
    )
    page = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField()
    comment = models.TextField(blank=True)
    color = models.CharField(max_length=10, choices=Color.choices, default=Color.YELLOW)

    class Meta:
        ordering = ["page", "created_at"]

    def __str__(self):
        page = f" p.{self.page}" if self.page else ""
        return f"{self.reference.bibtex_key}{page}: {self.text[:50]}"


class ReferenceText(models.Model):
    """Extracted text of a reference's PDF (Library v2 slice 8: search inside your PDFs).

    `pages` keeps one string per page so a match can say "p.4" and the reader can jump there;
    `body` is the same text joined, which is what the search filters run over.
    """

    reference = models.OneToOneField(Reference, on_delete=models.CASCADE, related_name="text")
    source_name = models.CharField(max_length=500, blank=True)  # the PDF file this came from
    pages = models.JSONField(default=list)
    body = models.TextField(blank=True)
    page_count = models.PositiveIntegerField(default=0)
    char_count = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)
    extracted_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"text of {self.reference.bibtex_key} ({self.page_count} pages)"
