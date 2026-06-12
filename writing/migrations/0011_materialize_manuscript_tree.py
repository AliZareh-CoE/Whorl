"""Materialize existing manuscripts into the unified Document tree (Owner #30, slice 1c-ii-A).

Inert copy: writes root folders + Document nodes from each manuscript's ManuscriptFile
rows and links Manuscript.main_file_node. Nothing reads these nodes yet (1c-ii-B flips
readers). Reversible and idempotent.
"""

from django.db import migrations


def forward(apps, schema_editor):
    Manuscript = apps.get_model("writing", "Manuscript")
    Folder = apps.get_model("documents", "Folder")
    Document = apps.get_model("documents", "Document")
    from writing.tree_sync import materialize_manuscript_tree

    for manuscript in Manuscript.objects.all():
        if not manuscript.files.exists():
            continue
        root, main_node = materialize_manuscript_tree(manuscript, Folder=Folder, Document=Document)
        manuscript.root_folder = root
        manuscript.main_file_node = main_node
        manuscript.save(update_fields=["root_folder", "main_file_node"])


def reverse(apps, schema_editor):
    Manuscript = apps.get_model("writing", "Manuscript")
    Folder = apps.get_model("documents", "Folder")
    Document = apps.get_model("documents", "Document")
    from writing.tree_sync import dematerialize_manuscript_tree

    for manuscript in Manuscript.objects.all():
        manuscript.main_file_node = None
        manuscript.root_folder = None
        manuscript.save(update_fields=["root_folder", "main_file_node"])
        dematerialize_manuscript_tree(manuscript, Folder=Folder, Document=Document)


class Migration(migrations.Migration):
    dependencies = [
        ("writing", "0010_manuscript_main_file_node"),
        ("documents", "0003_document_content_document_kind_document_rel_path_and_more"),
    ]
    operations = [migrations.RunPython(forward, reverse)]
