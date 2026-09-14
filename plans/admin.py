from django.contrib import admin

from .models import Milestone, MilestoneDateChange, Phase, PlanReview, ResearchQuestion, Task


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "order", "status", "target_start", "target_end"]
    list_filter = ["status", "project"]
    inlines = [MilestoneInline]


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ["title", "phase", "due_date", "completed_at"]
    list_filter = ["phase__project"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "milestone", "done", "due_date", "order"]
    list_filter = ["done"]


@admin.register(ResearchQuestion)
class ResearchQuestionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "project", "status"]
    list_filter = ["status", "project"]


@admin.register(MilestoneDateChange)
class MilestoneDateChangeAdmin(admin.ModelAdmin):
    list_display = ["milestone", "from_date", "to_date", "changed_at", "reason"]
    list_filter = ["milestone__phase__project"]
    date_hierarchy = "changed_at"


@admin.register(PlanReview)
class PlanReviewAdmin(admin.ModelAdmin):
    list_display = ["project", "reviewed_at", "kept", "completed", "moved", "skipped"]
    list_filter = ["project"]
    date_hierarchy = "reviewed_at"
