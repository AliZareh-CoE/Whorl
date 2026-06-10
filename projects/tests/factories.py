import factory

from projects.models import DecisionRecord, Project


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    name = factory.Sequence(lambda n: f"Project {n}")


class DecisionRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DecisionRecord

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Decision {n}")
    decision = "We decided."
