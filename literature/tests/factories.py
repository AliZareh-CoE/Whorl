import factory

from literature.models import ProjectReference, Reference
from projects.tests.factories import ProjectFactory


class ReferenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Reference

    bibtex_key = factory.Sequence(lambda n: f"author{2000 + n}word")
    title = factory.Sequence(lambda n: f"A Study of Topic {n}")
    authors = [{"family": "Author", "given": "Ann"}]
    year = 2024
    venue = "Journal of Things"
    entry_type = "article"


class ProjectReferenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProjectReference

    project = factory.SubFactory(ProjectFactory)
    reference = factory.SubFactory(ReferenceFactory)
