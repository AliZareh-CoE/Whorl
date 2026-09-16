from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "documents"

    def ready(self):
        from . import signals

        signals.connect()  # a delete removes the bytes (Audit #34, backlog 356)
