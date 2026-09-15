from django.db import migrations, models
from django.db.models import F


def backfill(apps, schema_editor):
    """Existing links: a read paper finished when it was last touched, a skimmed one started
    then — the best date the record holds (works on Postgres and the desktop's SQLite)."""
    ProjectReference = apps.get_model("literature", "ProjectReference")
    ProjectReference.objects.filter(
        reading_status__in=["read", "annotated"], finished_at__isnull=True
    ).update(finished_at=F("updated_at"))
    ProjectReference.objects.filter(reading_status="skimmed", started_at__isnull=True).update(
        started_at=F("updated_at")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("literature", "0009_reference_abstract_trgm"),
    ]

    operations = [
        migrations.AddField(
            model_name="reference",
            name="last_page",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reference",
            name="page_count",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reference",
            name="last_read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectreference",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectreference",
            name="finished_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
