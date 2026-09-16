from django.contrib.postgres.indexes import GinIndex
from django.db import models

from core.models import TimeStampedModel
from projects.models import Project

from .paths import KIND_OTHER, kind_for_node_path

# Raster image types that are safe to serve inline (they can't execute script). SVG is
# deliberately excluded — it can carry JavaScript — as are HTML/PDF; those fall back to download.
PREVIEWABLE_IMAGE_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"}
)


def sniff_image_type(head: bytes) -> str | None:
    """Return the raster image MIME for `head`'s magic bytes, or None (#235 hardening).

    The stored content_type is whatever the browser reported at upload, so it can disagree
    with the bytes (a mislabeled or hostile file). Before the preview endpoint serves anything
    `inline`, it sniffs the real signature here and only trusts what the bytes actually are.
    """
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"BM"):
        return "image/bmp"
    return None


class Folder(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="folders")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "parent", "name"], name="unique_folder_name_per_parent"
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def path(self):
        parts, node = [], self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return " / ".join(reversed(parts))

    @property
    def ancestors(self):
        """Folders from the project root down to (and including) this one — for clickable
        breadcrumbs. Walks the parent chain exactly like ``path`` does (same query cost)."""
        chain, node = [], self
        while node is not None:
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    def descendant_ids(self):
        """IDs of this folder and everything below it (for filtering and cycle checks)."""
        ids, frontier = {self.pk}, [self.pk]
        children_map = {}
        for folder in self.project.folders.all():
            children_map.setdefault(folder.parent_id, []).append(folder.pk)
        while frontier:
            nxt = []
            for pk in frontier:
                for child in children_map.get(pk, []):
                    if child not in ids:
                        ids.add(child)
                        nxt.append(child)
            frontier = nxt
        return ids


class Tag(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=60)
    color = models.CharField(max_length=7, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="unique_tag_per_project"),
        ]

    def __str__(self):
        return self.name


def project_document_path(instance, filename):
    return f"projects/{instance.project.slug}/documents/{filename}"


def document_version_path(instance, filename):
    """#553: a version's bytes live under the document's id and number, never under a
    user-supplied name — the basename is kept for the download only."""
    base = filename.rsplit("/", 1)[-1][-80:] or "file"
    return f"projects/{instance.document.project.slug}/versions/{instance.document_id}/v{instance.number}-{base}"


class DocumentQuerySet(models.QuerySet):
    def general(self):
        """Exclude unified-tree nodes that belong to a manuscript's source set, so the
        general Documents UI / counts don't surface them (file-workspace epic #30)."""
        return self.filter(role="general")


class Document(TimeStampedModel):
    # File-workspace epic (Owner #30), slice 1a: Document grows into the unified
    # tree node. These fields are additive and inert until later slices wire them
    # (the rel_path uniqueness constraint + backfill land with the data migration).
    class Role(models.TextChoices):
        GENERAL = "general", "General"
        MANUSCRIPT_SOURCE = "manuscript_source", "Manuscript source"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="documents")
    folder = models.ForeignKey(
        Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents"
    )  # null = project root
    file = models.FileField(upload_to=project_document_path, blank=True)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="documents")
    file_size = models.PositiveBigIntegerField(editable=False, default=0)
    content_type = models.CharField(max_length=100, editable=False, blank=True)
    # unified-tree node fields (inert until later slices)
    content = models.TextField(blank=True)  # inline text for editable nodes
    rel_path = models.CharField(max_length=300, blank=True)  # path from project root
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.GENERAL)
    kind = models.CharField(max_length=10, blank=True)  # tex/bib/asset/other (kind_for_node_path)
    # #553: bumped on every replace / edit / write / restore; the states left behind are
    # DocumentVersion rows (documents/history.py)
    version = models.PositiveIntegerField(default=1)

    objects = DocumentQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            GinIndex(fields=["title"], opclasses=["gin_trgm_ops"], name="document_title_trgm")
        ]

    def __str__(self):
        return self.title

    @property
    def preview_kind(self):
        """ "image", "text", or None (#14 cheap previews). Raster images and plain text only —
        deliberately NOT SVG or HTML, which can carry script that would run in Atlas's own
        origin. The SPA shows images in an in-app lightbox and opens text in a new tab."""
        ct = (self.content_type or "").lower().split(";")[0].strip()
        if ct in PREVIEWABLE_IMAGE_TYPES:
            return "image"
        if ct.startswith("text/"):
            return "text"
        return None

    @property
    def is_previewable(self):
        return self.preview_kind is not None

    def save(self, *args, **kwargs):
        if not self.kind:
            # #561: a node that arrives without a kind (the classic upload form, a seed, an
            # import) is still previewable — the explorer's text / image / table preview and
            # the tree's icons read `kind`; a text-only node is text whatever its title says
            if self.content and not self.file:
                self.kind = KIND_OTHER
            else:
                name = self.rel_path or (self.file.name if self.file else "") or self.title
                self.kind = kind_for_node_path(name)
        if self.file:
            self.file_size = self.file.size
            content_type = getattr(getattr(self.file, "file", None), "content_type", "")
            if content_type:
                self.content_type = content_type
        elif self.content:
            # #557: an inline-text node (write-file, the editor) has a size too — the tree's
            # size column and the Size sort read it
            self.file_size = len(self.content.encode())
        super().save(*args, **kwargs)


class DocumentVersion(models.Model):
    """#553: a general document's earlier state — the file (or inline text) a replace, an
    in-place edit, an MCP write or a restore left behind. Numbered per document; the last
    ``documents.history.KEEP`` are kept. Manuscript sources never get one (the studio has
    its own revisions)."""

    class Source(models.TextChoices):
        UPLOAD = "upload", "Replaced by an upload"
        EDIT = "edit", "Edited in place"
        WRITE = "write", "Written by the API or Claude"
        RESTORE = "restore", "Restored an earlier version"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    file = models.FileField(upload_to=document_version_path, blank=True)
    content = models.TextField(blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.UPLOAD)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "number"], name="documentversion_number_per_document"
            )
        ]

    def __str__(self):
        return f"{self.document_id} v{self.number}"
