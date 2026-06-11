from django.contrib import admin

from .models import Manuscript, ManuscriptFile, ManuscriptReference, SubmissionEvent


class ManuscriptReferenceInline(admin.TabularInline):
    model = ManuscriptReference
    extra = 0


class SubmissionEventInline(admin.TabularInline):
    model = SubmissionEvent
    extra = 0


class ManuscriptFileInline(admin.TabularInline):
    model = ManuscriptFile
    fields = ["path", "kind", "is_main"]
    extra = 0


@admin.register(Manuscript)
class ManuscriptAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "status", "target_venue", "deadline"]
    list_filter = ["status", "project"]
    inlines = [ManuscriptReferenceInline, SubmissionEventInline, ManuscriptFileInline]


@admin.register(ManuscriptReference)
class ManuscriptReferenceAdmin(admin.ModelAdmin):
    list_display = ["manuscript", "reference", "cite_key_override"]


@admin.register(SubmissionEvent)
class SubmissionEventAdmin(admin.ModelAdmin):
    list_display = ["manuscript", "kind", "date"]
    list_filter = ["kind"]
