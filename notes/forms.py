from django import forms

from literature.models import Reference
from projects.forms import INPUT

from .models import Note


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["title", "body", "references"]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT}),
            "body": forms.Textarea(
                attrs={
                    "class": INPUT + " font-mono",
                    "rows": 16,
                    "placeholder": "Markdown. Link other notes with [[Their Title]].",
                }
            ),
            "references": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.fields["references"].queryset = Reference.objects.filter(
            project_links__project=project
        )
        self.fields["references"].label = "Cited references (from this project's literature)"

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        clash = Note.objects.filter(project=self.project, title__iexact=title).exclude(
            pk=self.instance.pk
        )
        if clash.exists():
            raise forms.ValidationError("A note with this title already exists in the project.")
        return title
