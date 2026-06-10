from django.contrib import admin

from .models import QuickCapture


@admin.register(QuickCapture)
class QuickCaptureAdmin(admin.ModelAdmin):
    list_display = ["__str__", "processed", "project", "created_at"]
    list_filter = ["processed", "project"]
