from django import forms

from projects.forms import INPUT

from .models import Document, Folder, Tag
from .selectors import move_targets


class FolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ["name", "parent"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT}),
            "parent": forms.Select(attrs={"class": INPUT}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        if self.instance.pk:
            self.fields["parent"].queryset = move_targets(self.instance)
        else:
            self.fields["parent"].queryset = project.folders.all()
        self.fields["parent"].label = "Inside folder (blank = project root)"

    def clean(self):
        cleaned = super().clean()
        name, parent = cleaned.get("name"), cleaned.get("parent")
        if name:
            clash = Folder.objects.filter(project=self.project, parent=parent, name=name).exclude(
                pk=self.instance.pk
            )
            if clash.exists():
                raise forms.ValidationError("A folder with this name already exists here.")
        return cleaned


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "file", "folder", "description", "tags"]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT}),
            "file": forms.ClearableFileInput(attrs={"class": INPUT}),
            "folder": forms.Select(attrs={"class": INPUT}),
            "description": forms.Textarea(attrs={"class": INPUT, "rows": 3}),
            "tags": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folder"].queryset = project.folders.all()
        self.fields["folder"].label = "Folder (blank = project root)"
        self.fields["tags"].queryset = project.tags.all()
        if self.instance.pk:
            self.fields["file"].required = False


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["name", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT}),
            "color": forms.TextInput(attrs={"class": INPUT, "type": "color"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project

    def clean_name(self):
        name = self.cleaned_data["name"]
        clash = Tag.objects.filter(project=self.project, name=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("This tag already exists in the project.")
        return name
