import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0014_todoitem_all_day")]

    operations = [
        migrations.AddField(
            model_name="todoitem",
            name="repeat",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Never"),
                    ("daily", "Every day"),
                    ("weekdays", "Every weekday"),
                    ("weekly", "Every week"),
                    ("monthly", "Every month"),
                ],
                default="",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="todoitem",
            name="repeat_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="repeats",
                to="core.todoitem",
            ),
        ),
    ]
