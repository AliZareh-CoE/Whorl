from django.apps import AppConfig


class WritingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "writing"

    def ready(self):
        from . import signals  # noqa: F401  (registers the ManuscriptFile->tree mirror)
