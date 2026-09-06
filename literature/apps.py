from django.apps import AppConfig


class LiteratureConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "literature"

    def ready(self):
        from . import signals  # noqa: F401 — connects the PDF text indexer
