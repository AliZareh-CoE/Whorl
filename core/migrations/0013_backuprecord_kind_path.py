from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_comment_resolved"),
    ]

    operations = [
        migrations.AddField(
            model_name="backuprecord",
            name="kind",
            field=models.CharField(default="manual", max_length=10),
        ),
        migrations.AddField(
            model_name="backuprecord",
            name="path",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
