import datetime

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from documents.models import Document, Folder, Tag
from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.models import DecisionRecord, Project

DEMO_SLUG = "attention-and-memory"


class Command(BaseCommand):
    help = "Seed a realistic demo research project exercising every Atlas feature."

    def handle(self, *args, **options):
        Project.objects.filter(slug=DEMO_SLUG).delete()
        project = Project.objects.create(
            name="Attention and Working Memory",
            slug=DEMO_SLUG,
            description=(
                "A behavioural study of how **sustained attention** interacts with working "
                "memory load.\n\nCore bet: load effects on attention are *strategic*, not "
                "structural."
            ),
            status=Project.Status.ACTIVE,
        )
        today = timezone.localdate()

        # Plan: 4 phases, milestones in various states (incl. one overdue), optional tasks
        lit = Phase.objects.create(
            project=project,
            name="Literature & hypotheses",
            order=1,
            status=Phase.Status.DONE,
            objective="Map the load-attention literature; commit to testable hypotheses.",
            target_start=today - datetime.timedelta(days=120),
            target_end=today - datetime.timedelta(days=60),
        )
        design = Phase.objects.create(
            project=project,
            name="Experimental design & pilot",
            order=2,
            status=Phase.Status.IN_PROGRESS,
            objective="Finalize the dual-task paradigm and pilot with n=12.",
            target_start=today - datetime.timedelta(days=59),
            target_end=today + datetime.timedelta(days=30),
        )
        collection = Phase.objects.create(
            project=project,
            name="Data collection",
            order=3,
            objective="Run the full sample (n=80) across both load conditions.",
            target_start=today + datetime.timedelta(days=31),
            target_end=today + datetime.timedelta(days=90),
        )
        writing = Phase.objects.create(
            project=project,
            name="Analysis & write-up",
            order=4,
            objective="Pre-registered analyses, then the manuscript.",
        )

        done = timezone.now()
        Milestone.objects.create(
            phase=lit,
            title="Annotated bibliography (40 papers)",
            completed_at=done,
            due_date=today - datetime.timedelta(days=90),
        )
        Milestone.objects.create(
            phase=lit,
            title="Hypotheses registered in lab notebook",
            completed_at=done,
            due_date=today - datetime.timedelta(days=65),
        )
        Milestone.objects.create(
            phase=design,
            title="Paradigm implemented in PsychoPy",
            completed_at=done,
            due_date=today - datetime.timedelta(days=20),
        )
        overdue = Milestone.objects.create(
            phase=design,
            title="Pilot data collected (n=12)",
            due_date=today - datetime.timedelta(days=3),
            notes="Recruitment slower than expected; two no-shows last week.",
        )
        Milestone.objects.create(
            phase=design,
            title="Pilot analysed, design frozen",
            due_date=today + datetime.timedelta(days=25),
        )
        Milestone.objects.create(
            phase=collection,
            title="Ethics amendment approved",
            due_date=today + datetime.timedelta(days=40),
        )
        Milestone.objects.create(phase=collection, title="Full sample collected")
        Milestone.objects.create(phase=writing, title="Pre-registered analysis complete")
        Milestone.objects.create(phase=writing, title="Manuscript draft to co-authors")

        Task.objects.create(milestone=overdue, title="Email participant pool", done=True, order=1)
        Task.objects.create(
            milestone=overdue,
            title="Book lab room for next week",
            order=2,
            due_date=today + datetime.timedelta(days=2),
        )
        Task.objects.create(milestone=overdue, title="Run two make-up sessions", order=3)

        rq1 = ResearchQuestion.objects.create(
            project=project,
            question="Does working memory load reduce sustained attention, or redistribute it?",
            status=ResearchQuestion.Status.PARTIALLY_ANSWERED,
        )
        rq1.phases.set([lit, design, collection])
        rq2 = ResearchQuestion.objects.create(
            project=project,
            question="Are load effects better explained by strategic trade-offs than capacity limits?",
        )
        rq2.phases.set([collection, writing])

        # Documents: nested folders, tags, files
        lit_folder = Folder.objects.create(project=project, name="Literature")
        reviews = Folder.objects.create(project=project, parent=lit_folder, name="Review papers")
        methods_folder = Folder.objects.create(project=project, name="Methods")
        data_folder = Folder.objects.create(project=project, name="Data")
        Folder.objects.create(project=project, parent=data_folder, name="Pilot")

        key_paper = Tag.objects.create(project=project, name="key-paper", color="#dc2626")
        protocol = Tag.objects.create(project=project, name="protocol", color="#2563eb")

        def add_doc(title, folder, body, description="", tags=()):
            doc = Document.objects.create(
                project=project,
                folder=folder,
                title=title,
                description=description,
                file=ContentFile(body.encode(), name=f"{title.lower().replace(' ', '-')[:40]}.txt"),
            )
            doc.tags.set(tags)
            return doc

        add_doc(
            "Load theory review (Lavie 2010) — notes",
            reviews,
            "Summary of perceptual vs cognitive load distinction…",
            description="The anchor paper for our framing.",
            tags=[key_paper],
        )
        add_doc(
            "Dual-task protocol v3",
            methods_folder,
            "Block order, timing, counterbalancing…",
            description="Frozen after pilot feedback.",
            tags=[protocol],
        )
        add_doc(
            "Pilot session checklist",
            methods_folder,
            "1. Consent 2. Practice block 3. …",
            tags=[protocol],
        )
        add_doc("Project root readme", None, "Where everything lives in this project.")

        DecisionRecord.objects.create(
            project=project,
            title="Use a dual-task paradigm instead of load manipulation within a single task",
            context="Single-task load manipulations confound difficulty with load.",
            decision="Adopt the dual-task design with separate WM and attention components.",
            alternatives="Within-task load (rejected: confound); pupillometry only (rejected: cost).",
            decided_on=today - datetime.timedelta(days=70),
        )
        DecisionRecord.objects.create(
            project=project,
            title="Pre-register analyses before pilot is unblinded",
            decision="OSF pre-registration drafted in the Analysis phase, frozen before n=20.",
            decided_on=today - datetime.timedelta(days=10),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_demo: created project '{project.name}' (/projects/{project.slug}/) with "
                f"{project.phases.count()} phases, "
                f"{Milestone.objects.filter(phase__project=project).count()} milestones, "
                f"{project.documents.count()} documents, {project.decisions.count()} decisions."
            )
        )
