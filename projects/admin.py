from django.contrib import admin

from .models import DecisionRecord, Project, ProjectTemplate


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "status", "position", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(DecisionRecord)
class DecisionRecordAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "decided_on", "created_at"]
    list_filter = ["project"]
    search_fields = ["title", "decision"]


@admin.register(ProjectTemplate)
class ProjectTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name", "description"]
