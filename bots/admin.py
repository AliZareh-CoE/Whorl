from django.contrib import admin

from .models import Bot


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ["slug", "enabled", "last_run_at", "last_result"]
