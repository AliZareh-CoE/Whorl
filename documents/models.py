from django.db import models

from core.models import TimeStampedModel
from projects.models import Project


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
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="documents")
    folder = models.ForeignKey(
        Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents"
    )  # null = project root
    file = models.FileField(upload_to=project_document_path)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="documents")
    file_size = models.PositiveBigIntegerField(editable=False, default=0)
    content_type = models.CharField(max_length=100, editable=False, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
            content_type = getattr(getattr(self.file, "file", None), "content_type", "")
            if content_type:
                self.content_type = content_type
        super().save(*args, **kwargs)
