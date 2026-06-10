import factory

from notes.models import Note
from projects.tests.factories import ProjectFactory


class NoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Note

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Note {n}")
    body = "Some **markdown** body."
