import factory

from projects.tests.factories import ProjectFactory
from writing.models import Manuscript, ManuscriptFile


class ManuscriptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Manuscript

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Manuscript {n}")


class ManuscriptFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ManuscriptFile

    manuscript = factory.SubFactory(ManuscriptFactory)
    path = "main.tex"
    kind = "tex"
    is_main = False
