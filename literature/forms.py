from django import forms

from projects.forms import INPUT

from .models import ProjectReference, Reference


class AddByIdentifierForm(forms.Form):
    identifier = forms.CharField(
        label="DOI or arXiv ID",
        widget=forms.TextInput(
            attrs={"class": INPUT, "placeholder": "10.1038/nature12373 or 2106.01234"}
        ),
    )


class BibtexImportForm(forms.Form):
    bibtex = forms.CharField(
        label="BibTeX",
        widget=forms.Textarea(
            attrs={"class": INPUT + " font-mono", "rows": 12, "placeholder": "@article{...}"}
        ),
    )


class ReferenceForm(forms.ModelForm):
    authors_text = forms.CharField(
        label="Authors (one per line, “Family, Given”)",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT, "rows": 3}),
    )

    class Meta:
        model = Reference
        fields = [
            "entry_type",
            "title",
            "year",
            "venue",
            "doi",
            "arxiv_id",
            "url",
            "abstract",
            "pdf",
        ]
        widgets = {
            "entry_type": forms.Select(
                choices=[
                    (t, t)
                    for t in ("article", "inproceedings", "book", "phdthesis", "techreport", "misc")
                ],
                attrs={"class": INPUT},
            ),
            "title": forms.Textarea(attrs={"class": INPUT, "rows": 2}),
            "year": forms.NumberInput(attrs={"class": INPUT}),
            "venue": forms.TextInput(attrs={"class": INPUT}),
            "doi": forms.TextInput(attrs={"class": INPUT}),
            "arxiv_id": forms.TextInput(attrs={"class": INPUT}),
            "url": forms.TextInput(attrs={"class": INPUT}),
            "abstract": forms.Textarea(attrs={"class": INPUT, "rows": 4}),
            "pdf": forms.ClearableFileInput(attrs={"class": INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.authors:
            self.initial["authors_text"] = "\n".join(
                f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                for a in self.instance.authors
            )

    def clean_doi(self):
        from .services import normalize_doi

        doi = self.cleaned_data.get("doi") or ""
        return normalize_doi(doi) or None

    def save(self, commit=True):
        from .services import generate_bibtex_key

        reference = super().save(commit=False)
        authors = []
        for line in (self.cleaned_data.get("authors_text") or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if "," in line:
                family, given = line.split(",", 1)
                authors.append({"family": family.strip(), "given": given.strip()})
            else:
                authors.append({"family": line, "given": ""})
        reference.authors = authors
        if not reference.bibtex_key:
            reference.bibtex_key = generate_bibtex_key(authors, reference.year, reference.title)
        if commit:
            reference.save()
        return reference


class LinkReferenceForm(forms.ModelForm):
    class Meta:
        model = ProjectReference
        fields = ["reference", "reading_status", "priority", "notes"]
        widgets = {
            "reference": forms.Select(attrs={"class": INPUT}),
            "reading_status": forms.Select(attrs={"class": INPUT}),
            "priority": forms.Select(attrs={"class": INPUT}),
            "notes": forms.Textarea(attrs={"class": INPUT, "rows": 3}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        if not self.instance.pk:
            self.fields["reference"].queryset = Reference.objects.exclude(
                project_links__project=project
            )
        else:
            self.fields.pop("reference")

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk:
            reference = cleaned.get("reference")
            if (
                reference
                and ProjectReference.objects.filter(
                    project=self.project, reference=reference
                ).exists()
            ):
                raise forms.ValidationError("This reference is already linked to the project.")
        return cleaned


class ReviewThemeForm(forms.ModelForm):
    class Meta:
        from .models import ReviewTheme

        model = ReviewTheme
        fields = ["name", "order"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT}),
            "order": forms.NumberInput(attrs={"class": INPUT}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project

    def clean_name(self):
        from .models import ReviewTheme

        name = self.cleaned_data["name"].strip()
        clash = ReviewTheme.objects.filter(project=self.project, name__iexact=name).exclude(
            pk=self.instance.pk
        )
        if clash.exists():
            raise forms.ValidationError("This theme already exists in the project.")
        return name
