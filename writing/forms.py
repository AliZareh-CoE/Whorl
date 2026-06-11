from django import forms

from literature.models import Reference
from projects.forms import INPUT

from .models import Manuscript, ManuscriptReference, SubmissionEvent


class ManuscriptForm(forms.ModelForm):
    starter = forms.ChoiceField(
        required=False,
        label="Start from template",
        help_text="Seeds main.tex (new manuscripts only).",
    )

    class Meta:
        model = Manuscript
        fields = ["title", "status", "target_venue", "deadline", "abstract", "repo_url"]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT}),
            "status": forms.Select(attrs={"class": INPUT}),
            "target_venue": forms.TextInput(attrs={"class": INPUT}),
            "deadline": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "abstract": forms.Textarea(attrs={"class": INPUT, "rows": 5}),
            "repo_url": forms.TextInput(attrs={"class": INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .templates_gallery import template_choices

        if self.instance and self.instance.pk:
            self.fields.pop("starter", None)  # template seeding is create-only
        else:
            self.fields["starter"].choices = [("", "— blank —"), *template_choices()]
            self.fields["starter"].widget.attrs["class"] = INPUT


class ManuscriptReferenceForm(forms.ModelForm):
    class Meta:
        model = ManuscriptReference
        fields = ["reference", "cite_key_override"]
        widgets = {
            "reference": forms.Select(attrs={"class": INPUT}),
            "cite_key_override": forms.TextInput(
                attrs={"class": INPUT, "placeholder": "optional — defaults to the library key"}
            ),
        }

    def __init__(self, *args, manuscript=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.manuscript = manuscript
        self.fields["reference"].queryset = Reference.objects.exclude(
            manuscriptreference__manuscript=manuscript
        )

    def clean_reference(self):
        reference = self.cleaned_data["reference"]
        if ManuscriptReference.objects.filter(
            manuscript=self.manuscript, reference=reference
        ).exists():
            raise forms.ValidationError("Already in this manuscript's bibliography.")
        return reference


class SubmissionEventForm(forms.ModelForm):
    class Meta:
        model = SubmissionEvent
        fields = ["kind", "date", "notes"]
        widgets = {
            "kind": forms.Select(attrs={"class": INPUT}),
            "date": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "notes": forms.Textarea(attrs={"class": INPUT, "rows": 3}),
        }


class CiteCheckForm(forms.Form):
    tex_file = forms.FileField(required=False, label="Upload .tex file")
    tex_text = forms.CharField(
        required=False,
        label="…or paste LaTeX source",
        widget=forms.Textarea(attrs={"class": INPUT + " font-mono", "rows": 10}),
    )

    def clean(self):
        cleaned = super().clean()
        tex_file = cleaned.get("tex_file")
        if tex_file:
            cleaned["tex"] = tex_file.read().decode("utf-8", errors="replace")
        elif cleaned.get("tex_text"):
            cleaned["tex"] = cleaned["tex_text"]
        else:
            raise forms.ValidationError("Upload a .tex file or paste LaTeX source.")
        return cleaned
