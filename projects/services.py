"""Project services (file-workspace epic #30, slice 7): scaffold from a template."""


from documents.models import Document, Folder
from documents.paths import kind_for_node_path, validate_workspace_name

from .project_templates import TEMPLATES


def _ensure_folder_path(project, segments):
    """Create (idempotently) the nested folders for a path; return the leaf Folder."""
    parent = None
    for name in segments:
        validate_workspace_name(name)
        parent, _ = Folder.objects.get_or_create(project=project, parent=parent, name=name)
    return parent


def instantiate_template(project, key: str) -> dict:
    """Lay down a template's folders + starter files in `project`. Idempotent.

    Returns a small summary {folders, files}. Unknown/blank key is a no-op.
    """
    template = TEMPLATES.get(key)
    if not template:
        return {"folders": 0, "files": 0}

    made_folders = 0
    for path in template["folders"]:
        before = Folder.objects.filter(project=project).count()
        _ensure_folder_path(project, path.split("/"))
        made_folders += Folder.objects.filter(project=project).count() - before

    made_files = 0
    for path, body in template["files"].items():
        *dirs, filename = path.split("/")
        validate_workspace_name(filename)
        folder = _ensure_folder_path(project, dirs) if dirs else None
        rel_path = path
        content = body.format(name=project.name)
        _, created = Document.objects.get_or_create(
            project=project,
            rel_path=rel_path,
            defaults={
                "folder": folder,
                "title": filename,
                "role": Document.Role.GENERAL,
                "kind": kind_for_node_path(rel_path),
                "content": content,
            },
        )
        made_files += int(created)

    return {"folders": made_folders, "files": made_files}
