from django.db import migrations, models


def backfill(apps, schema_editor):
    from notes.tags import parse_tags

    Note = apps.get_model("notes", "Note")
    for note in Note.objects.all().iterator():
        tags = sorted(parse_tags(note.body))
        if tags:
            Note.objects.filter(pk=note.pk).update(tags=tags)


class Migration(migrations.Migration):
    dependencies = [("notes", "0007_capture_link_title")]

    operations = [
        migrations.AddField(
            model_name="note",
            name="tags",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
