from django import forms

from literature.models import Reference
from projects.forms import INPUT

from .models import Dataset, Evidence, ExperimentEntry, Hypothesis


class HypothesisForm(forms.ModelForm):
    class Meta:
        model = Hypothesis
        fields = ["statement", "status"]
        widgets = {
            "statement": forms.Textarea(attrs={"class": INPUT, "rows": 3}),
            "status": forms.Select(attrs={"class": INPUT}),
        }


class EvidenceForm(forms.ModelForm):
    class Meta:
        model = Evidence
        fields = ["direction", "summary", "reference", "note", "document"]
        widgets = {
            "direction": forms.Select(attrs={"class": INPUT}),
            "summary": forms.Textarea(attrs={"class": INPUT, "rows": 3}),
            "reference": forms.Select(attrs={"class": INPUT}),
            "note": forms.Select(attrs={"class": INPUT}),
            "document": forms.Select(attrs={"class": INPUT}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reference"].queryset = Reference.objects.filter(project_links__project=project)
        self.fields["note"].queryset = project.notes.all()
        self.fields["document"].queryset = project.documents.all()
        for name in ("reference", "note", "document"):
            self.fields[name].required = False


class ExperimentEntryForm(forms.ModelForm):
    class Meta:
        model = ExperimentEntry
        fields = ["date", "title", "body", "hypotheses"]
        widgets = {
            "date": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "title": forms.TextInput(attrs={"class": INPUT}),
            "body": forms.Textarea(attrs={"class": INPUT + " font-mono", "rows": 10}),
            "hypotheses": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hypotheses"].queryset = project.hypotheses.all()


class DatasetForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ["name", "location", "version", "checksum", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT}),
            "location": forms.TextInput(attrs={"class": INPUT}),
            "version": forms.TextInput(attrs={"class": INPUT}),
            "checksum": forms.TextInput(attrs={"class": INPUT}),
            "description": forms.Textarea(attrs={"class": INPUT, "rows": 3}),
        }
