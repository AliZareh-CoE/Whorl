import factory

from projects.tests.factories import ProjectFactory
from writing.models import Manuscript


class ManuscriptFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Manuscript

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Manuscript {n}")
