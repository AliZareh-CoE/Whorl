from django.contrib import admin

from .models import Document, DocumentVersion, Folder, Tag


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "parent", "created_at"]
    list_filter = ["project"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "color"]
    list_filter = ["project"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "folder", "file_size", "content_type", "created_at"]
    list_filter = ["project"]
    search_fields = ["title", "description"]


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ["document", "number", "source", "file_size", "note", "created_at"]
    list_filter = ["source"]
    search_fields = ["document__title", "note"]
