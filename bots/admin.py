from django.contrib import admin

from .models import Bot


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ["slug", "enabled", "last_run_at", "last_result"]


from .models import BotRun  # noqa: E402


@admin.register(BotRun)
class BotRunAdmin(admin.ModelAdmin):
    list_display = ["bot", "started_at", "ok", "result"]
    list_filter = ["bot", "ok"]
