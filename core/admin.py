from django.contrib import admin

from . import models


@admin.register(models.TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    list_display = ("text", "done", "done_at", "project", "position", "created_at")
    list_filter = ("done", "project")
    search_fields = ("text",)
