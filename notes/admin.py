from django.contrib import admin

from .models import Note, NoteLink, QuickCapture


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "tags", "updated_at"]
    list_filter = ["project"]
    search_fields = ["title", "body"]


@admin.register(NoteLink)
class NoteLinkAdmin(admin.ModelAdmin):
    list_display = ["source", "target"]


@admin.register(QuickCapture)
class QuickCaptureAdmin(admin.ModelAdmin):
    list_display = ["__str__", "processed", "became_kind", "snoozed_until", "project", "created_at"]
    list_filter = ["processed", "project"]
