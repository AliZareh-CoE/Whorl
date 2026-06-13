from django import forms

from .models import DecisionRecord, Project

INPUT = (
    "w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm "
    "focus:border-indigo-600 focus:outline-none"
)


class ProjectForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .project_templates import template_choices

        self.fields["starter"] = forms.ChoiceField(
            choices=template_choices(),
            required=False,
            label="Scaffold",
            widget=forms.Select(attrs={"class": INPUT}),
            help_text="Optionally lay down an organized folder structure.",
        )

    class Meta:
        model = Project
        fields = ["name", "description", "status", "color", "position"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT}),
            "description": forms.Textarea(attrs={"class": INPUT, "rows": 6}),
            "status": forms.Select(attrs={"class": INPUT}),
            "color": forms.TextInput(attrs={"class": INPUT, "type": "color"}),
            "position": forms.NumberInput(attrs={"class": INPUT}),
        }


class DecisionRecordForm(forms.ModelForm):
    class Meta:
        model = DecisionRecord
        fields = ["title", "context", "decision", "alternatives", "decided_on"]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT}),
            "context": forms.Textarea(attrs={"class": INPUT, "rows": 4}),
            "decision": forms.Textarea(attrs={"class": INPUT, "rows": 4}),
            "alternatives": forms.Textarea(attrs={"class": INPUT, "rows": 4}),
            "decided_on": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
        }
