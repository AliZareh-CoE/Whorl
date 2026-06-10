from django import forms

from projects.forms import INPUT

from .models import Milestone, Phase, ResearchQuestion, Task


class PhaseForm(forms.ModelForm):
    class Meta:
        model = Phase
        fields = ["name", "order", "status", "objective", "target_start", "target_end"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT}),
            "order": forms.NumberInput(attrs={"class": INPUT}),
            "status": forms.Select(attrs={"class": INPUT}),
            "objective": forms.Textarea(attrs={"class": INPUT, "rows": 4}),
            "target_start": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "target_end": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
        }


class MilestoneForm(forms.ModelForm):
    class Meta:
        model = Milestone
        fields = ["title", "due_date", "notes"]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT}),
            "due_date": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "notes": forms.Textarea(attrs={"class": INPUT, "rows": 3}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "due_date", "order"]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT}),
            "due_date": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "order": forms.NumberInput(attrs={"class": INPUT}),
        }


class ResearchQuestionForm(forms.ModelForm):
    class Meta:
        model = ResearchQuestion
        fields = ["question", "status", "phases"]
        widgets = {
            "question": forms.Textarea(attrs={"class": INPUT, "rows": 3}),
            "status": forms.Select(attrs={"class": INPUT}),
            "phases": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            self.fields["phases"].queryset = project.phases.all()
