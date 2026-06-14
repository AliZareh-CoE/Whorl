from django.contrib.postgres.indexes import GinIndex
from django.db import models

from core.models import TimeStampedModel
from projects.models import Project

# Raster image types that are safe to serve inline (they can't execute script). SVG is
# deliberately excluded — it can carry JavaScript — as are HTML/PDF; those fall back to download.
PREVIEWABLE_IMAGE_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"}
)


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

    objects = DocumentQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            GinIndex(fields=["title"], opclasses=["gin_trgm_ops"], name="document_title_trgm")
        ]

    def __str__(self):
        return self.title

    @property
    def is_previewable(self):
        """Whether this file is safe to show inline (#14 cheap previews). Raster images and
        plain text only — deliberately NOT SVG or HTML, which can carry script that would run
        in Atlas's own origin. Everything else falls back to download."""
        ct = (self.content_type or "").lower().split(";")[0].strip()
        return ct in PREVIEWABLE_IMAGE_TYPES or ct.startswith("text/")

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
            content_type = getattr(getattr(self.file, "file", None), "content_type", "")
            if content_type:
                self.content_type = content_type
        super().save(*args, **kwargs)
