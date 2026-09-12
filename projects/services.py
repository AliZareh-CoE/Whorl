"""Project services (file-workspace epic #30, slice 7-8): scaffold + snapshot templates."""

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


def instantiate_structure(project, structure: dict) -> dict:
    """Lay down a {folders, files} structure in `project`. Idempotent. Returns a summary."""
    made_folders = 0
    for path in structure.get("folders", []):
        before = Folder.objects.filter(project=project).count()
        _ensure_folder_path(project, path.split("/"))
        made_folders += Folder.objects.filter(project=project).count() - before

    made_files = 0
    for path, body in structure.get("files", {}).items():
        *dirs, filename = path.split("/")
        validate_workspace_name(filename)
        folder = _ensure_folder_path(project, dirs) if dirs else None
        body = body or ""
        content = body.format(name=project.name) if "{name}" in body else body
        _, created = Document.objects.get_or_create(
            project=project,
            rel_path=path,
            defaults={
                "folder": folder,
                "title": filename,
                "role": Document.Role.GENERAL,
                "kind": kind_for_node_path(path),
                "content": content,
            },
        )
        made_files += int(created)

    return {"folders": made_folders, "files": made_files}


def instantiate_research_scaffold(project, template: dict) -> dict:
    """#438: lay down the template's plan outline, research questions and review themes —
    each only when the project has none of that kind yet, so re-applying never duplicates."""
    from literature.models import ReviewTheme
    from plans import outline
    from plans.models import ResearchQuestion

    made = {"phases": 0, "questions": 0, "themes": 0}
    plan = template.get("plan") or ""
    if plan.strip() and not project.phases.exists():
        outline.apply(project, plan)
        made["phases"] = project.phases.count()
    if template.get("questions") and not project.questions.exists():
        for text in template["questions"]:
            ResearchQuestion.objects.create(project=project, question=text)
            made["questions"] += 1
    if template.get("themes") and not project.review_themes.exists():
        for order, name in enumerate(template["themes"], start=1):
            ReviewTheme.objects.create(project=project, name=name, order=order)
            made["themes"] += 1
    return made


def instantiate_template(project, key: str) -> dict:
    """Scaffold from a built-in (code) template by key, OR a user ProjectTemplate by name."""
    template = TEMPLATES.get(key)
    if template:
        return {
            **instantiate_structure(project, template),
            **instantiate_research_scaffold(project, template),
        }

    from .models import ProjectTemplate

    saved = ProjectTemplate.objects.filter(name=key).first()
    if saved:
        return instantiate_structure(project, saved.structure)
    return {"folders": 0, "files": 0}


# Cap a saved file's content so snapshots stay light (larger files become empty placeholders).
SNAPSHOT_FILE_CAP = 64 * 1024


def snapshot_project_structure(project) -> dict:
    """Capture a project's GENERAL folders + text files as a reusable structure dict.

    Manuscript folders/sources are excluded — they're owned by the editor/mirror, not
    part of a reusable scaffold.
    """
    manuscript_roots = set(
        project.manuscripts.exclude(root_folder__isnull=True).values_list(
            "root_folder_id", flat=True
        )
    )

    def _under_manuscript(folder):
        node = folder
        while node is not None:
            if node.pk in manuscript_roots:
                return True
            node = node.parent
        return False

    folders = []
    for folder in project.folders.all():
        if _under_manuscript(folder):
            continue
        parts, node = [], folder
        while node is not None:
            parts.append(node.name)
            node = node.parent
        folders.append("/".join(reversed(parts)))

    files = {}
    for doc in project.documents.general():
        if not doc.rel_path:
            continue
        content = doc.content or ""
        files[doc.rel_path] = content if len(content) <= SNAPSHOT_FILE_CAP else ""
    return {"folders": sorted(folders), "files": files}


def save_project_as_template(project, name: str, description: str = ""):
    """Snapshot `project` into a (new or updated) user ProjectTemplate."""
    from .models import ProjectTemplate

    template, _ = ProjectTemplate.objects.update_or_create(
        name=name,
        defaults={"description": description, "structure": snapshot_project_structure(project)},
    )
    return template
