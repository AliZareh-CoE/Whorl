"""Keep a manuscript's unified-tree mirror in sync with its ManuscriptFile rows.

File-workspace epic (Owner #30), slice 1c-ii. A manuscript's source files live
canonically as ManuscriptFile rows (the compile pipeline, the workbench API, and the
six MCP tools all read/write them). This module mirrors them into the unified Document
tree so the file workspace / explorer (slice 2) shows them live alongside general
documents — the same dual-store pattern as the latex_source<->main-file alias.

``resync_manuscript_tree`` is the one entry point: it ensures the ``manuscript-<pk>``
root folder, upserts a Document node per ManuscriptFile (content for text, bytes for
assets, intermediate folders for nested paths), prunes nodes whose source file is gone
(renames/deletes), and links ``Manuscript.main_file_node``. It is model-class-injected
so the data migration uses historical models and signals/tests use the real ones.
"""

MANUSCRIPT_SOURCE = "manuscript_source"


def root_folder_name(manuscript_pk: int) -> str:
    return f"manuscript-{manuscript_pk}"


def resync_manuscript_tree(manuscript, *, Folder, Document):
    """Make the Document tree mirror ``manuscript.files`` exactly. Returns (root, main)."""
    project = manuscript.project
    root_name = root_folder_name(manuscript.pk)
    root, _ = Folder.objects.get_or_create(project=project, parent=None, name=root_name)

    desired: dict[str, tuple] = {}
    for mf in manuscript.files.all():
        *dirs, filename = mf.path.split("/")
        folder = root
        rel_parts = [root_name]
        for segment in dirs:
            folder, _ = Folder.objects.get_or_create(project=project, parent=folder, name=segment)
            rel_parts.append(segment)
        rel_parts.append(filename)
        desired["/".join(rel_parts)] = (mf, folder, filename)

    # prune nodes whose source file no longer exists (renames, deletes)
    Document.objects.filter(
        project=project, role=MANUSCRIPT_SOURCE, rel_path__startswith=root_name + "/"
    ).exclude(rel_path__in=desired).delete()

    main_node = None
    for rel_path, (mf, folder, filename) in desired.items():
        node, created = Document.objects.get_or_create(
            project=project,
            rel_path=rel_path,
            defaults={
                "folder": folder,
                "title": filename,
                "role": MANUSCRIPT_SOURCE,
                "kind": mf.kind or "",
                "content": mf.content or "",
            },
        )
        if not created:
            updates = {}
            if node.content != (mf.content or ""):
                updates["content"] = mf.content or ""
            if node.kind != (mf.kind or ""):
                updates["kind"] = mf.kind or ""
            if node.folder_id != folder.pk:
                updates["folder"] = folder
            if node.role != MANUSCRIPT_SOURCE:
                updates["role"] = MANUSCRIPT_SOURCE
            if updates:
                for field, value in updates.items():
                    setattr(node, field, value)
                node.save(update_fields=[*updates, "updated_at"])

        asset = getattr(mf, "asset", None)
        if asset and not node.file:
            node.file.save(filename, asset.file, save=False)
            node.file_size = asset.size
            node.save()
        if mf.is_main:
            main_node = node
    return root, main_node


# back-compat name for the slice 1c-ii-A migration (create + link; resync is a superset).
materialize_manuscript_tree = resync_manuscript_tree


def dematerialize_manuscript_tree(manuscript, *, Folder, Document):
    """Reverse: drop the manuscript's source nodes + its root folder subtree."""
    root_name = root_folder_name(manuscript.pk)
    root = Folder.objects.filter(project=manuscript.project, parent=None, name=root_name).first()
    if root is None:
        return
    Document.objects.filter(rel_path__startswith=root_name + "/").delete()
    root.delete()
