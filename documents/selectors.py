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


def workspace_tree(project: Project, tags: list[str] | None = None) -> dict:
    """The whole project as one file tree (file-workspace epic #30, slice 2): every
    Folder and every Document node — general AND manuscript-source — flat, for the
    explorer to nest client-side. One query each. `tags` (backlog 354) keeps only the files
    carrying every named tag; folders are always listed.
    """
    from django.conf import settings

    TEXT_KINDS = {"tex", "bib", "other"}
    # desktop only: where the file lives on this computer, so the explorer can hand it to
    # the OS ("Open with the system app", "Show in folder"); never exposed on a server
    local_paths = settings.ATLAS_DESKTOP
    folders = [
        {"id": f.id, "name": f.name, "parent_id": f.parent_id} for f in project.folders.all()
    ]
    files = []
    from django.db.models import Count, Max

    # #554: tags + description ride along (one prefetch, not one query per row)
    # #557: `modified_at` is when the bytes last changed — a version is filed at that moment,
    # so it is the newest version's stamp (or the creation) — not `updated_at`, which a tag,
    # a description or a move also bumps
    from .tags import filter_by_tags

    documents = (
        filter_by_tags(project.documents.all(), tags or [])
        .annotate(
            versions_count=Count("versions", distinct=True),
            last_filed=Max("versions__created_at"),
        )
        .prefetch_related("tags")
    )
    for d in documents:
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
                "version": d.version,
                "versions": d.versions_count,  # #553: earlier states in its history
                "description": d.description,
                "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in d.tags.all()],
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
                # a manuscript source has no versions: only the Studio's mirror writes it, so
                # its updated_at is the honest change time
                "modified_at": (
                    d.last_filed
                    or (d.updated_at if d.role == "manuscript_source" else d.created_at)
                ).isoformat(),
                "is_text": d.kind in TEXT_KINDS or (bool(d.content) and not d.file),
                "local_path": (d.file.path if local_paths and d.file else None),
            }
        )
    return {"folders": folders, "files": files}


def move_targets(folder: Folder):
    """Folders this folder may become a child of (no cycles: not itself or a descendant)."""
    excluded = folder.descendant_ids()
    return folder.project.folders.exclude(pk__in=excluded)


def project_figures(project: Project) -> list[dict]:
    """Every inline-previewable raster image in the project, newest first — the figure
    gallery's data layer (#8). An image is a Document whose ``preview_kind`` is "image"
    (png/jpeg/gif/webp/bmp); SVG is excluded (it can carry script), matching the preview
    whitelist. select_related(folder) + prefetch(tags) keep it to a couple of queries.
    """
    docs = (
        project.documents.filter(content_type__startswith="image/")
        .select_related("folder")
        .prefetch_related("tags")
        .order_by("-created_at")
    )
    figures = []
    for d in docs:
        if d.preview_kind != "image":  # exact whitelist (excludes image/svg+xml)
            continue
        figures.append(
            {
                "id": d.id,
                "title": d.title,
                "folder": d.folder.name if d.folder else None,
                "folder_id": d.folder_id,
                "tags": sorted(t.name for t in d.tags.all()),
                "size": d.file_size,
                "content_type": d.content_type,
                "created_at": d.created_at,
            }
        )
    return figures
