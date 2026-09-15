from django.contrib import admin

from .models import (
    CitationEdge,
    CitingWork,
    Feed,
    FeedItem,
    Highlight,
    LibraryTag,
    ProjectReference,
    Reference,
    ReferenceText,
    ReviewMark,
    ReviewTheme,
    SavedView,
)


@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = [
        "bibtex_key",
        "title",
        "year",
        "venue",
        "doi",
        "citation_count",
        "retraction_kind",
    ]
    search_fields = ["title", "bibtex_key", "doi"]
    list_filter = ["entry_type", "retraction_kind"]


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


@admin.register(Highlight)
class HighlightAdmin(admin.ModelAdmin):
    list_display = ("reference", "project", "page", "color", "created_at")
    list_filter = ("color", "project")
    search_fields = ("text", "comment", "reference__title")
    raw_id_fields = ("reference",)


@admin.register(ReferenceText)
class ReferenceTextAdmin(admin.ModelAdmin):
    list_display = ("reference", "page_count", "char_count", "error", "extracted_at")
    search_fields = ("reference__title", "body")
    raw_id_fields = ("reference",)


@admin.register(CitingWork)
class CitingWorkAdmin(admin.ModelAdmin):
    list_display = [
        "openalex_id",
        "title",
        "year",
        "published_on",
        "venue",
        "reference",
        "dismissed_at",
    ]
    search_fields = ["title", "doi", "openalex_id"]
    list_filter = ["year"]
    raw_id_fields = ["cites", "reference"]


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "url",
        "project",
        "last_fetched_at",
        "last_ok_at",
        "last_error",
        "muted_total",
    ]
    search_fields = ["title", "url"]
    raw_id_fields = ["project"]


@admin.register(FeedItem)
class FeedItemAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "feed",
        "published_on",
        "doi",
        "arxiv_id",
        "reference",
        "dismissed_at",
        "muted_by",
    ]
    search_fields = ["title", "doi", "arxiv_id", "guid"]
    list_filter = ["feed"]
    raw_id_fields = ["feed", "reference"]
