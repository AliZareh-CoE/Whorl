from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_todoitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="pet",
            name="souls_mode",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="AchievementUnlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=60, unique=True)),
                ("unlocked_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-unlocked_at"]},
        ),
    ]
