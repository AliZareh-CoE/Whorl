from django import forms

from projects.forms import INPUT

from .models import Prompt


class PromptForm(forms.ModelForm):
    class Meta:
        model = Prompt
        fields = ["title", "body", "tags"]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT}),
            "body": forms.Textarea(attrs={"class": INPUT + " font-mono", "rows": 12}),
            "tags": forms.TextInput(attrs={"class": INPUT, "placeholder": "writing, lit-review"}),
        }
