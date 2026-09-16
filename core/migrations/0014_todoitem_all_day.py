from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0013_backuprecord_kind_path")]

    operations = [
        migrations.AddField(
            model_name="todoitem",
            name="all_day",
            field=models.BooleanField(default=False),
        ),
    ]
