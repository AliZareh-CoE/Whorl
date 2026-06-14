from projects.models import Project

from .models import Folder


def folder_tree(project: Project, prefetched=None) -> list[dict]:
    """Nested folder structure: [{"folder": f, "children": [...]}, ...] sorted by name.

    Manuscript root folders (and their subtrees) are hidden from the general Documents
    tree — they belong to the manuscript workbench / the slice-2 explorer (epic #30).

    Pass ``prefetched`` (a list of all the project's Folders) to reuse a folder list the
    caller already loaded, avoiding a duplicate ``project.folders.all()`` query (#197).
    """
    manuscript_roots = set(
        project.manuscripts.exclude(root_folder__isnull=True).values_list(
            "root_folder_id", flat=True
        )
    )
    all_folders = project.folders.all() if prefetched is None else prefetched
    folders = [f for f in all_folders if f.pk not in manuscript_roots]
    by_parent: dict[int | None, list[Folder]] = {}
    for folder in folders:
        by_parent.setdefault(folder.parent_id, []).append(folder)

    def build(parent_id):
        return [{"folder": f, "children": build(f.pk)} for f in by_parent.get(parent_id, [])]

    return build(None)


def workspace_tree(project: Project) -> dict:
    """The whole project as one file tree (file-workspace epic #30, slice 2): every
    Folder and every Document node — general AND manuscript-source — flat, for the
    explorer to nest client-side. One query each.
    """
    TEXT_KINDS = {"tex", "bib", "other"}
    folders = [
        {"id": f.id, "name": f.name, "parent_id": f.parent_id} for f in project.folders.all()
    ]
    files = []
    for d in project.documents.all():
        name = d.title or (d.rel_path.rsplit("/", 1)[-1] if d.rel_path else "")
        files.append(
            {
                "id": d.id,
                "name": name,
                "rel_path": d.rel_path,
                "kind": d.kind,
                "role": d.role,
                "folder_id": d.folder_id,
                "size": d.file_size,
                "is_text": d.kind in TEXT_KINDS or (bool(d.content) and not d.file),
            }
        )
    return {"folders": folders, "files": files}


def move_targets(folder: Folder):
    """Folders this folder may become a child of (no cycles: not itself or a descendant)."""
    excluded = folder.descendant_ids()
    return folder.project.folders.exclude(pk__in=excluded)
