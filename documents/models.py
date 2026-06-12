from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from projects.models import Project

from .paths import kind_for_node_path, kind_for_path


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
    def rel_path(self):
        """Slash-joined path from the project root, for node rel_path derivation."""
        parts, node, seen = [], self, set()
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            parts.append(node.name)
            node = node.parent
        return "/".join(reversed(parts))

    def save(self, *args, **kwargs):
        renamed = False
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values("name", "parent_id").first()
            renamed = old is not None and (
                old["name"] != self.name or old["parent_id"] != self.parent_id
            )
        super().save(*args, **kwargs)
        if renamed:  # keep the denormalized node rel_paths in sync (unified tree, slice 1)
            for document in Document.objects.filter(
                project=self.project, folder_id__in=self.descendant_ids()
            ):
                document.save(update_fields=["rel_path", "updated_at"])

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


class Document(TimeStampedModel):
    """One node of the unified project file tree (file-workspace epic, slice 1).

    Text nodes store their bytes in `content`; binary nodes in `file`. Manuscript
    sources are nodes with role=MANUSCRIPT_SOURCE inside a manuscript's root_folder
    subtree — manuscript-ness is an attribute, not a separate table.
    """

    class Role(models.TextChoices):
        GENERAL = "general", "General"
        MANUSCRIPT_SOURCE = "manuscript_source", "Manuscript source"

    class Kind(models.TextChoices):
        TEX = "tex", "LaTeX"
        BIB = "bib", "BibTeX"
        ASSET = "asset", "Asset"
        OTHER = "other", "Text"

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
    # unified tree (slice 1)
    content = models.TextField(blank=True)  # inline text for editable files
    rel_path = models.CharField(max_length=500, blank=True, default="", editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.GENERAL)
    kind = models.CharField(max_length=10, choices=Kind.choices, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            GinIndex(fields=["title"], opclasses=["gin_trgm_ops"], name="document_title_trgm")
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "rel_path"],
                condition=~Q(rel_path=""),
                name="unique_rel_path_per_project",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def name(self) -> str:
        """The node's leaf name in the tree."""
        if self.rel_path:
            return self.rel_path.rsplit("/", 1)[-1]
        if self.file:
            return self.file.name.rsplit("/", 1)[-1]
        return self.title

    @property
    def is_text(self) -> bool:
        return self.kind in {self.Kind.TEX, self.Kind.BIB, self.Kind.OTHER}

    def compute_rel_path(self) -> str:
        """Denormalized folder-chain + leaf name, relative to the project root."""
        name = self.name
        if self.folder_id:
            return f"{self.folder.rel_path}/{name}"
        return name

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
            content_type = getattr(getattr(self.file, "file", None), "content_type", "")
            if content_type:
                self.content_type = content_type
        if not self.kind:
            classify = kind_for_path if self.role == self.Role.MANUSCRIPT_SOURCE else (
                kind_for_node_path
            )
            self.kind = classify(self.name)
        rel_path = self.compute_rel_path()
        if rel_path != self.rel_path:
            self.rel_path = rel_path
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "rel_path" not in update_fields:
                kwargs["update_fields"] = list(update_fields) + ["rel_path"]
        super().save(*args, **kwargs)
        # latex_source alias, new shape: a saved main-file node pushes its content back
        if self.role == self.Role.MANUSCRIPT_SOURCE and not getattr(
            self, "_from_alias_sync", False
        ):
            from django.utils import timezone

            from writing.models import Manuscript

            Manuscript.objects.filter(main_file=self).update(
                latex_source=self.content, updated_at=timezone.now()
            )


# The unified-tree name for a file node. Code written for the workspace epic should
# import ProjectFile; Document stays as the historical alias until the Slice 8 cleanup.
ProjectFile = Document
