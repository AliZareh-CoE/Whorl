import factory

from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.tests.factories import ProjectFactory


class PhaseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Phase

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Phase {n}")
    order = factory.Sequence(lambda n: n)


class MilestoneFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Milestone

    phase = factory.SubFactory(PhaseFactory)
    title = factory.Sequence(lambda n: f"Milestone {n}")


class TaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Task

    milestone = factory.SubFactory(MilestoneFactory)
    title = factory.Sequence(lambda n: f"Task {n}")


class ResearchQuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ResearchQuestion

    project = factory.SubFactory(ProjectFactory)
    question = factory.Sequence(lambda n: f"Why does thing {n} happen?")
