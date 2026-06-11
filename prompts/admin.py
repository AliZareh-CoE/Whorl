from django.contrib import admin

from .models import Prompt


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ["title", "tags", "updated_at"]
    search_fields = ["title", "body", "tags"]
