from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        from . import schema  # noqa: F401 — registers the OpenAPI X-API-Key auth extension
