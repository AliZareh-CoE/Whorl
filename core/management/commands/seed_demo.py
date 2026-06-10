import datetime

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from documents.models import Document, Folder, Tag
from literature.models import CitationEdge, ProjectReference, Reference
from notes.models import Note, QuickCapture
from notes.services import sync_note_links
from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.models import DecisionRecord, Project
from writing.models import Manuscript, ManuscriptReference, SubmissionEvent

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

        # Literature: a small shared library linked to the project with reading states
        demo_refs = [
            {
                "doi": "10.0000/demo.lavie.2010",
                "bibtex_key": "lavie2010attention",
                "title": "Attention, Distraction, and Cognitive Control Under Load",
                "authors": [{"family": "Lavie", "given": "Nilli"}],
                "year": 2010,
                "venue": "Current Directions in Psychological Science",
                "citation_count": 1200,
                "status": ProjectReference.ReadingStatus.ANNOTATED,
                "priority": ProjectReference.Priority.HIGH,
            },
            {
                "doi": "10.0000/demo.baddeley.2003",
                "bibtex_key": "baddeley2003working",
                "title": "Working Memory: Looking Back and Looking Forward",
                "authors": [{"family": "Baddeley", "given": "Alan"}],
                "year": 2003,
                "venue": "Nature Reviews Neuroscience",
                "citation_count": 5400,
                "status": ProjectReference.ReadingStatus.READ,
                "priority": ProjectReference.Priority.NORMAL,
            },
            {
                "doi": "10.0000/demo.draheim.2022",
                "bibtex_key": "draheim2022attention",
                "title": "Attention Control: The Missing Link Between Sensory Discrimination and Intelligence",
                "authors": [{"family": "Draheim", "given": "Christopher"}],
                "year": 2022,
                "venue": "Attention, Perception, & Psychophysics",
                "citation_count": 90,
                "status": ProjectReference.ReadingStatus.TO_READ,
                "priority": ProjectReference.Priority.HIGH,
            },
            {
                "bibtex_key": "anonndworking",  # deliberately incomplete: exercises the bib report
                "title": "Working Notes on Load Effects",
                "authors": [],
                "year": None,
                "venue": "",
                "citation_count": None,
                "status": ProjectReference.ReadingStatus.TO_READ,
                "priority": ProjectReference.Priority.LOW,
            },
        ]
        for spec in demo_refs:
            reference, _ = Reference.objects.update_or_create(
                bibtex_key=spec["bibtex_key"],
                defaults={
                    "doi": spec.get("doi"),
                    "title": spec["title"],
                    "authors": spec["authors"],
                    "year": spec["year"],
                    "venue": spec["venue"],
                    "citation_count": spec["citation_count"],
                    "entry_type": "article",
                },
            )
            ProjectReference.objects.update_or_create(
                project=project,
                reference=reference,
                defaults={"reading_status": spec["status"], "priority": spec["priority"]},
            )

        # A larger cited corpus so the knowledge graph is worth looking at (20+ refs)
        corpus_authors = [
            "Norman",
            "Posner",
            "Kahneman",
            "Engle",
            "Cowan",
            "Oberauer",
            "Logan",
            "Treisman",
            "Duncan",
            "Desimone",
            "Awh",
            "Vogel",
            "Luck",
            "Miller",
            "Chun",
            "Wolfe",
            "Carrasco",
            "Theeuwes",
        ]
        corpus_refs = []
        for index, family in enumerate(corpus_authors):
            year = 1995 + index
            reference, _ = Reference.objects.update_or_create(
                bibtex_key=f"{family.lower()}{year}study",
                defaults={
                    "title": f"{family}'s Study of Attention and Memory Interaction {index + 1}",
                    "authors": [{"family": family, "given": "A."}],
                    "year": year,
                    "venue": "Journal of Cognitive Demonstration",
                    "citation_count": (index * 37) % 900 + 10,
                    "entry_type": "article",
                },
            )
            corpus_refs.append(reference)
            ProjectReference.objects.update_or_create(
                project=project,
                reference=reference,
                defaults={
                    "reading_status": [
                        ProjectReference.ReadingStatus.TO_READ,
                        ProjectReference.ReadingStatus.SKIMMED,
                        ProjectReference.ReadingStatus.READ,
                    ][index % 3]
                },
            )
        # Deterministic synthetic citation edges: each paper cites 2-3 earlier ones
        for i, citing in enumerate(corpus_refs):
            for j in {(i * 7 + 1) % i if i else None, (i * 3 + 2) % i if i else None}:
                if j is not None and j < i:
                    CitationEdge.objects.get_or_create(citing=citing, cited=corpus_refs[j])

        # Notes with wiki-links and reference citations
        hub, _ = Note.objects.update_or_create(
            project=project,
            title="Load theory overview",
            defaults={
                "body": (
                    "Central claim: perceptual load gates distractor processing.\n\n"
                    "Open threads live in [[Strategic allocation hypothesis]] and "
                    "[[Pilot observations]]."
                )
            },
        )
        strategic, _ = Note.objects.update_or_create(
            project=project,
            title="Strategic allocation hypothesis",
            defaults={
                "body": (
                    "If load effects are *strategic*, practice should modulate them. "
                    "Contrast with the capacity view in [[Load theory overview]]."
                )
            },
        )
        pilot_note, _ = Note.objects.update_or_create(
            project=project,
            title="Pilot observations",
            defaults={
                "body": "n=9 so far. Two participants reported chunking digits — relevant to [[Strategic allocation hypothesis]]."
            },
        )
        for note in (hub, strategic, pilot_note):
            sync_note_links(note)
        hub.references.set(corpus_refs[:3])
        strategic.references.set(corpus_refs[3:5])

        QuickCapture.objects.get_or_create(
            text="Check whether the 2024 load-modulation preprint ever got published"
        )

        # Writing: one manuscript mid-pipeline with bibliography + submission history
        manuscript, _ = Manuscript.objects.update_or_create(
            project=project,
            title="Strategic Allocation of Attention Under Working Memory Load",
            defaults={
                "status": Manuscript.Status.REVISION,
                "target_venue": "Journal of Experimental Psychology: General",
                "deadline": today + datetime.timedelta(days=18),
                "abstract": "We show that load effects on sustained attention reflect "
                "**strategic trade-offs** rather than structural capacity limits.",
            },
        )
        for reference in corpus_refs[:6]:
            ManuscriptReference.objects.get_or_create(manuscript=manuscript, reference=reference)
        for kind, days_ago, note in [
            (SubmissionEvent.Kind.SUBMITTED, 95, "Initial submission."),
            (SubmissionEvent.Kind.REVIEWS_RECEIVED, 40, "R2 wants a power analysis."),
            (SubmissionEvent.Kind.NOTE, 20, "Power analysis done; n=80 holds."),
        ]:
            SubmissionEvent.objects.get_or_create(
                manuscript=manuscript,
                kind=kind,
                date=today - datetime.timedelta(days=days_ago),
                defaults={"notes": note},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_demo: created project '{project.name}' (/projects/{project.slug}/) with "
                f"{project.phases.count()} phases, "
                f"{Milestone.objects.filter(phase__project=project).count()} milestones, "
                f"{project.documents.count()} documents, {project.decisions.count()} decisions, "
                f"{project.project_references.count()} linked references, "
                f"{project.notes.count()} notes, "
                f"{CitationEdge.objects.filter(citing__project_links__project=project).count()} citation edges."
            )
        )
