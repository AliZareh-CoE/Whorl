# #561: nodes created without a `kind` (the classic upload form, the demo seed, older
# imports) never got the explorer's text preview or a typed icon; Document.save() now derives
# it, and this backfills the rows that already exist with the same rule.

from django.db import migrations

from documents.paths import kind_for_node_path


def derive_kinds(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    for doc in Document.objects.filter(kind="").iterator():
        if doc.content and not doc.file:
            kind = "other"
        else:
            name = doc.rel_path or (doc.file.name if doc.file else "") or doc.title
            kind = kind_for_node_path(name)
        Document.objects.filter(pk=doc.pk).update(kind=kind)


class Migration(migrations.Migration):
    dependencies = [("documents", "0005_inline_sizes")]

    operations = [migrations.RunPython(derive_kinds, migrations.RunPython.noop)]
