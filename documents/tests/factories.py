import factory
from django.core.files.base import ContentFile

from documents.models import Document, Folder, Tag
from projects.tests.factories import ProjectFactory


class FolderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Folder

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Folder {n}")


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"tag-{n}")


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Document {n}")
    file = factory.LazyFunction(lambda: ContentFile(b"content", name="doc.txt"))
