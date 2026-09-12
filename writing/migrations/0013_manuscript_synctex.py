from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("writing", "0012_venue_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="manuscript",
            name="synctex",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
