"""Materialize a manuscript's ManuscriptFile rows into the unified Document tree.

File-workspace epic (Owner #30), slice 1c-ii-A. Called by the data migration (with
historical model classes) and by tests (with the real classes). The nodes it writes
are INERT until slice 1c-ii-B flips the readers — nothing reads them yet, so this
copy is purely additive and reversible.

Each manuscript gets a root folder ``manuscript-<pk>`` at the project root; every
ManuscriptFile becomes a Document node under it (creating intermediate folders for
nested paths), with ``rel_path`` = ``manuscript-<pk>/<file path>``, ``role`` =
``manuscript_source``, ``kind`` copied from the source, text in ``content`` and
binary bytes copied into ``file``.
"""

MANUSCRIPT_SOURCE = "manuscript_source"


def root_folder_name(manuscript_pk: int) -> str:
    return f"manuscript-{manuscript_pk}"


def materialize_manuscript_tree(manuscript, *, Folder, Document):
    """Create (idempotently) the Document tree mirroring ``manuscript.files``.

    Returns ``(root_folder, main_node)``. Safe to re-run: nodes are keyed by
    ``(project, rel_path)`` via get_or_create.
    """
    project = manuscript.project
    root_name = root_folder_name(manuscript.pk)
    root, _ = Folder.objects.get_or_create(project=project, parent=None, name=root_name)

    main_node = None
    for mf in manuscript.files.all():
        *dirs, filename = mf.path.split("/")
        folder = root
        rel_parts = [root_name]
        for segment in dirs:
            folder, _ = Folder.objects.get_or_create(project=project, parent=folder, name=segment)
            rel_parts.append(segment)
        rel_parts.append(filename)
        rel_path = "/".join(rel_parts)

        node, _ = Document.objects.get_or_create(
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
        # copy binary bytes for asset nodes (text lives in content)
        asset = getattr(mf, "asset", None)
        if asset and not node.file:
            node.file.save(filename, asset.file, save=False)
            node.file_size = asset.size
            node.save()
        if mf.is_main:
            main_node = node
    return root, main_node


def dematerialize_manuscript_tree(manuscript, *, Folder, Document):
    """Reverse: drop the manuscript's source nodes + its root folder subtree."""
    root_name = root_folder_name(manuscript.pk)
    root = Folder.objects.filter(project=manuscript.project, parent=None, name=root_name).first()
    if root is None:
        return
    Document.objects.filter(rel_path__startswith=root_name + "/").delete()
    # delete the folder subtree (children first via cascade on Folder.parent)
    root.delete()
