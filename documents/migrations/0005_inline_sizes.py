# #557: inline-text nodes (write-file, editor-created files) were stored with file_size 0;
# Document.save() now sizes them, and this backfills the rows that already exist.

from django.db import migrations


def size_inline(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    for doc in Document.objects.filter(file="").exclude(content="").iterator():
        size = len(doc.content.encode())
        if doc.file_size != size:
            Document.objects.filter(pk=doc.pk).update(file_size=size)


class Migration(migrations.Migration):
    dependencies = [("documents", "0004_document_history")]

    operations = [migrations.RunPython(size_inline, migrations.RunPython.noop)]
