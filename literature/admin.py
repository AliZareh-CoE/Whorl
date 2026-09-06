from django.contrib import admin

from .models import (
    CitationEdge,
    LibraryTag,
    ProjectReference,
    Reference,
    ReviewMark,
    ReviewTheme,
    SavedView,
)


@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = ["bibtex_key", "title", "year", "venue", "doi", "citation_count"]
    search_fields = ["title", "bibtex_key", "doi"]
    list_filter = ["entry_type"]


@admin.register(ProjectReference)
class ProjectReferenceAdmin(admin.ModelAdmin):
    list_display = ["reference", "project", "reading_status", "priority", "created_at"]
    list_filter = ["project", "reading_status", "priority"]


@admin.register(CitationEdge)
class CitationEdgeAdmin(admin.ModelAdmin):
    list_display = ["citing", "cited"]


@admin.register(ReviewTheme)
class ReviewThemeAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "order"]
    list_filter = ["project"]


@admin.register(ReviewMark)
class ReviewMarkAdmin(admin.ModelAdmin):
    list_display = ["__str__", "note"]


@admin.register(LibraryTag)
class LibraryTagAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "created_at")
    search_fields = ("name",)


@admin.register(SavedView)
class SavedViewAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "params", "created_at")
