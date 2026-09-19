from django.contrib import admin

from .models import Prompt, PromptUse


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ["title", "tags", "next", "use_count", "last_used_at", "updated_at"]
    list_select_related = ["next"]
    search_fields = ["title", "body", "tags"]


@admin.register(PromptUse)
class PromptUseAdmin(admin.ModelAdmin):
    list_display = ["prompt", "created_at"]
    list_select_related = ["prompt"]
