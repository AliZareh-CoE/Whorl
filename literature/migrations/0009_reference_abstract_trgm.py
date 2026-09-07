import django.contrib.postgres.indexes
from django.db import migrations

from core.migration_ops import PostgresAddIndex


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_pg_trgm"),
        ("literature", "0008_highlight_rects"),
    ]

    operations = [
        PostgresAddIndex(
            model_name="reference",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["abstract"],
                name="reference_abstract_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
