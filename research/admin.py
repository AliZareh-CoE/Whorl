from django.contrib import admin

from .models import Dataset, Evidence, ExperimentEntry, Hypothesis


class EvidenceInline(admin.TabularInline):
    model = Evidence
    extra = 0


@admin.register(Hypothesis)
class HypothesisAdmin(admin.ModelAdmin):
    list_display = ["__str__", "project", "status"]
    list_filter = ["status", "project"]
    inlines = [EvidenceInline]


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ["__str__", "hypothesis", "direction", "created_at"]
    list_filter = ["direction"]


@admin.register(ExperimentEntry)
class ExperimentEntryAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "date"]
    list_filter = ["project"]


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "version", "location"]
    list_filter = ["project"]
