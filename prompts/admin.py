from django import forms
from django.contrib import admin

from .models import Prompt, PromptUse


class PromptAdminForm(forms.ModelForm):
    """Audit #35: the admin refuses a chain loop the way the API does (#567) — the back
    office is not a way around the cycle guard."""

    class Meta:
        model = Prompt
        fields = ["title", "body", "tags", "next"]

    def clean(self):
        from .services import chain_would_cycle

        cleaned = super().clean()
        nxt = cleaned.get("next")
        if nxt is not None and self.instance.pk and chain_would_cycle(self.instance, nxt):
            self.add_error("next", "That would make the chain loop back to this prompt.")
        return cleaned


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    form = PromptAdminForm
    list_display = ["title", "tags", "next", "use_count", "last_used_at", "updated_at"]
    list_select_related = ["next"]
    search_fields = ["title", "body", "tags"]


@admin.register(PromptUse)
class PromptUseAdmin(admin.ModelAdmin):
    list_display = ["prompt", "created_at"]
    list_select_related = ["prompt"]
