from django.contrib import admin

from .models import Prompt


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ["title", "tags", "use_count", "last_used_at", "updated_at"]
    search_fields = ["title", "body", "tags"]
