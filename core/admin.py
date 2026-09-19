from django.contrib import admin

from . import models


@admin.register(models.TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "done",
        "done_at",
        "due_at",
        "all_day",
        "repeat",
        "project",
        "position",
        "deleted_at",
        "created_at",
    )
    list_filter = ("done", "project", ("deleted_at", admin.EmptyFieldListFilter))
    search_fields = ("text",)

    def get_queryset(self, request):
        # #570: the back office sees the Trash too (the default manager hides it)
        return models.TodoItem.all_objects.select_related("project")


@admin.register(models.Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("name", "souls_mode", "updated_at")


@admin.register(models.AchievementUnlock)
class AchievementUnlockAdmin(admin.ModelAdmin):
    list_display = ("key", "unlocked_at")
    ordering = ("-unlocked_at",)


@admin.register(models.AccessEvent)
class AccessEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "address", "detail", "user_agent")
    list_filter = ("kind",)
    search_fields = ("address", "detail", "user_agent")
    readonly_fields = ("created_at",)


@admin.register(models.FeedToken)
class FeedTokenAdmin(admin.ModelAdmin):
    list_display = ("created_at",)
    readonly_fields = ("token", "created_at")


from core.models import BackupRecord  # noqa: E402


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "size_bytes", "media_files", "database", "path")
    ordering = ("-created_at",)
