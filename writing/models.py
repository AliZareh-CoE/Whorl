from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.models import TimeStampedModel
from documents.paths import (  # canonical home (file-workspace epic slice 1a);
    MAX_PATH_SEGMENTS,  # re-exported so writing.models.validate_manuscript_path
    PATH_SEGMENT_RE,  # keeps resolving for the historical 0006 migration.
    validate_manuscript_path,
)
from literature.models import Reference
from projects.models import Project

__all__ = ["validate_manuscript_path", "PATH_SEGMENT_RE", "MAX_PATH_SEGMENTS"]

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
    # File-workspace epic (Owner #30) slice 1b: a manuscript becomes a VIEW over the
    # unified tree — its sources are the Documents under root_folder's subtree. root_folder
    # is inert until the slice 1c data migration links each manuscript to its nodes. The
    # main_file → Document FK is deferred to 1c, where the existing main_file PROPERTY (which
    # returns the main ManuscriptFile) is reworked over it — adding the FK here would collide.
    root_folder = models.ForeignKey(
        "documents.Folder", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # the unified-tree node that is this manuscript's main file (slice 1c-ii-A, inert
    # until 1c-ii-B; named *_node to avoid colliding with the main_file PROPERTY, which
    # 1c-ii-B reworks; renamed to main_file once the ManuscriptFile property is removed).
    main_file_node = models.ForeignKey(
        "documents.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

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


class ManuscriptRevision(TimeStampedModel):
    """A point-in-time snapshot of a manuscript's whole file tree (Owner idea #24 slice 9).

    Taken automatically on each successful compile and on manual labeling. Beats
    Overleaf's free 24-hour history; trim policy keeps all labeled + the last 50 auto.
    """

    manuscript = models.ForeignKey(Manuscript, on_delete=models.CASCADE, related_name="revisions")
    label = models.CharField(max_length=200, blank=True)  # "" = automatic
    files = models.JSONField(default=dict)  # {path: content} for text files

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.manuscript_id} @ {self.created_at:%Y-%m-%d %H:%M}{' ' + self.label if self.label else ''}"

    @property
    def is_labeled(self) -> bool:
        return bool(self.label)


def snapshot_manuscript(manuscript, label: str = "") -> "ManuscriptRevision":
    """Create a revision from the current text files, then trim automatic ones."""
    text_files = manuscript.files.filter(kind__in=["tex", "bib"])
    if text_files.exists():
        files = {f.path: f.content for f in text_files}
    else:
        files = {"main.tex": manuscript.latex_source}
    revision = ManuscriptRevision.objects.create(manuscript=manuscript, label=label, files=files)
    # trim: keep all labeled + the most recent 50 automatic
    auto = manuscript.revisions.filter(label="").order_by("-created_at")
    stale_ids = list(auto.values_list("pk", flat=True)[50:])
    if stale_ids:
        ManuscriptRevision.objects.filter(pk__in=stale_ids).delete()
    return revision


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
