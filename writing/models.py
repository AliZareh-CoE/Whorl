import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.models import TimeStampedModel
from literature.models import Reference
from projects.models import Project

PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,79}$")
MAX_PATH_SEGMENTS = 8


def validate_manuscript_path(path: str) -> str:
    """Workbench file paths are deliberately strict (Owner idea #24 slice 6).

    ASCII-only kills unicode tricks; segments can't start with a dot, which
    rejects "..", ".", and dotfiles in one rule; no absolute/drive/backslash
    forms. Compile has a resolve()-based guard as the second line of defense.
    """
    if not path or len(path) > 200:
        raise ValidationError("Path must be 1-200 characters.")
    if not path.isascii():
        raise ValidationError("Path must be ASCII.")
    if "\\" in path:
        raise ValidationError("Use forward slashes.")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise ValidationError("Path must be relative.")
    segments = path.split("/")
    if len(segments) > MAX_PATH_SEGMENTS:
        raise ValidationError(f"At most {MAX_PATH_SEGMENTS} path segments.")
    for segment in segments:
        if not PATH_SEGMENT_RE.match(segment):
            raise ValidationError(f"Invalid path segment: {segment!r}")
    return path


TEXT_EXTENSIONS = {".tex", ".sty", ".cls", ".bst"}


def kind_for_path(path: str) -> str:
    suffix = ("." + path.rsplit(".", 1)[-1]).lower() if "." in path else ""
    if suffix in TEXT_EXTENSIONS:
        return ManuscriptFile.Kind.TEX
    if suffix == ".bib":
        return ManuscriptFile.Kind.BIB
    return ManuscriptFile.Kind.ASSET


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

    class CompileStatus(models.TextChoices):
        IDLE = "idle", "Not compiled"
        RUNNING = "running", "Compiling…"
        OK = "ok", "Compiled"
        FAILED = "failed", "Failed"

    compiled_pdf = models.FileField(upload_to="manuscripts/pdf/", null=True, blank=True)
    compile_status = models.CharField(
        max_length=10, choices=CompileStatus.choices, default=CompileStatus.IDLE
    )
    compile_log = models.TextField(blank=True)
    compile_diagnostics = models.JSONField(default=list, blank=True)  # parsed from the log
    compile_generation = models.PositiveIntegerField(default=0)  # bumped per queue; stale drops
    compiled_at = models.DateTimeField(null=True, blank=True)
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

    # --- multi-file workbench (Owner idea #24 slice 6) ---
    # latex_source stays a real column for one release; it aliases the main file.

    def save(self, *args, update_fields=None, **kwargs):
        super().save(*args, update_fields=update_fields, **kwargs)
        if update_fields is not None and "latex_source" not in update_fields:
            return  # status-only saves (compile.py) must never push a stale alias
        main = self.files.filter(is_main=True).first()
        if main is not None:
            if main.content != self.latex_source:
                self.files.filter(pk=main.pk).update(
                    content=self.latex_source, updated_at=timezone.now()
                )
        elif self.latex_source.strip():
            main = ManuscriptFile(
                manuscript=self,
                path="main.tex",
                kind=ManuscriptFile.Kind.TEX,
                content=self.latex_source,
                is_main=True,
            )
            main._from_alias_sync = True
            main.save()

    @property
    def main_file(self):
        return self.files.filter(is_main=True).first()

    def ensure_main_file(self):
        """Bootstrap main.tex from the alias column on first editor open."""
        main = self.main_file
        if main is None:
            main = ManuscriptFile(
                manuscript=self,
                path="main.tex",
                kind=ManuscriptFile.Kind.TEX,
                content=self.latex_source,
                is_main=True,
            )
            main._from_alias_sync = True
            main.save()
        return main

    def source_text(self) -> str:
        main = self.main_file
        return main.content if main is not None else self.latex_source


def manuscript_asset_path(instance, filename):
    return f"manuscripts/{instance.manuscript_id}/assets/{filename}"


class ManuscriptFile(TimeStampedModel):
    """One file of a manuscript's source tree (Owner idea #24 slice 6)."""

    class Kind(models.TextChoices):
        TEX = "tex", "LaTeX"
        BIB = "bib", "BibTeX"
        ASSET = "asset", "Asset"

    manuscript = models.ForeignKey(Manuscript, on_delete=models.CASCADE, related_name="files")
    path = models.CharField(max_length=200, validators=[validate_manuscript_path])
    kind = models.CharField(max_length=10, choices=Kind.choices, blank=True)
    content = models.TextField(blank=True)
    asset = models.FileField(upload_to=manuscript_asset_path, null=True, blank=True)
    is_main = models.BooleanField(default=False)

    class Meta:
        ordering = ["path"]
        constraints = [
            models.UniqueConstraint(
                fields=["manuscript", "path"], name="unique_path_per_manuscript"
            ),
            models.UniqueConstraint(
                fields=["manuscript"],
                condition=Q(is_main=True),
                name="unique_main_file_per_manuscript",
            ),
        ]

    def __str__(self):
        return f"{self.manuscript_id}:{self.path}"

    def save(self, *args, **kwargs):
        if not self.kind:
            self.kind = kind_for_path(self.path)
        super().save(*args, **kwargs)
        if self.is_main and not getattr(self, "_from_alias_sync", False):
            Manuscript.objects.filter(pk=self.manuscript_id).update(
                latex_source=self.content, updated_at=timezone.now()
            )


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
