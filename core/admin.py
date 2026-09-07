from django.contrib import admin

from . import models


@admin.register(models.TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    list_display = ("text", "done", "done_at", "project", "position", "created_at")
    list_filter = ("done", "project")
    search_fields = ("text",)


@admin.register(models.Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("name", "souls_mode", "updated_at")


@admin.register(models.AchievementUnlock)
class AchievementUnlockAdmin(admin.ModelAdmin):
    list_display = ("key", "unlocked_at")
    ordering = ("-unlocked_at",)
