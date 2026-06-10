from projects.models import Project

from .models import Folder


def folder_tree(project: Project) -> list[dict]:
    """Nested folder structure: [{"folder": f, "children": [...]}, ...] sorted by name."""
    folders = list(project.folders.all())
    by_parent: dict[int | None, list[Folder]] = {}
    for folder in folders:
        by_parent.setdefault(folder.parent_id, []).append(folder)

    def build(parent_id):
        return [{"folder": f, "children": build(f.pk)} for f in by_parent.get(parent_id, [])]

    return build(None)


def move_targets(folder: Folder):
    """Folders this folder may become a child of (no cycles: not itself or a descendant)."""
    excluded = folder.descendant_ids()
    return folder.project.folders.exclude(pk__in=excluded)
