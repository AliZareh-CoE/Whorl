"""Seed main.tex ManuscriptFile rows from latex_source (Owner idea #24 slice 6).

Manuscripts with empty latex_source get no row — they bootstrap lazily via
ensure_main_file() on first editor open.
"""

from django.db import migrations


def seed_main_files(apps, schema_editor):
    Manuscript = apps.get_model("writing", "Manuscript")
    ManuscriptFile = apps.get_model("writing", "ManuscriptFile")
    for manuscript in Manuscript.objects.exclude(latex_source="").iterator():
        ManuscriptFile.objects.get_or_create(
            manuscript=manuscript,
            path="main.tex",
            defaults={"kind": "tex", "content": manuscript.latex_source, "is_main": True},
        )


def unseed_main_files(apps, schema_editor):
    Manuscript = apps.get_model("writing", "Manuscript")
    ManuscriptFile = apps.get_model("writing", "ManuscriptFile")
    for f in ManuscriptFile.objects.filter(is_main=True).iterator():
        Manuscript.objects.filter(pk=f.manuscript_id).update(latex_source=f.content)
    ManuscriptFile.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("writing", "0006_manuscriptfile")]
    operations = [migrations.RunPython(seed_main_files, unseed_main_files)]
