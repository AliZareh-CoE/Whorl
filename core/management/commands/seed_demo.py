import datetime

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from documents.models import Document, Folder, Tag
from literature.models import CitationEdge, ProjectReference, Reference, ReviewMark, ReviewTheme
from notes.models import Note, QuickCapture
from notes.services import sync_note_links
from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.models import DecisionRecord, Project
from prompts.models import Prompt
from research.models import Dataset, Evidence, ExperimentEntry, Hypothesis
from writing.models import Manuscript, ManuscriptReference, SubmissionEvent

DEMO_SLUG = "attention-and-memory"


def make_demo_pdf(lines: list[str]) -> bytes:
    """A minimal valid one-page PDF with selectable text (no extra dependencies)."""
    text_ops = "\n".join(
        f"BT /F1 14 Tf 72 {720 - 24 * i} Td ({line}) Tj ET" for i, line in enumerate(lines)
    )
    stream = text_ops.encode()
    objects = [
        b"<</Type /Catalog /Pages 2 0 R>>",
        b"<</Type /Pages /Kids [3 0 R] /Count 1>>",
        b"<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources <</Font <</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(stream)).encode() + b">>\nstream\n" + stream + b"\nendstream",
        b"<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<</Size {len(objects) + 1} /Root 1 0 R>>\nstartxref\n{xref_at}\n%%EOF"
    ).encode()
    return bytes(out)


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
        figures_folder = Folder.objects.create(project=project, name="Figures")
        # a real image so the Figures gallery and the studio's "Project figures" have one
        fig = Document.objects.create(
            project=project,
            folder=figures_folder,
            title="Pilot d-prime by condition",
            description="Sensitivity by load × incentive from the 12-participant pilot.",
            file=ContentFile(_demo_png(), name="pilot-dprime.png"),
            content_type="image/png",  # ContentFile carries no browser-reported type
        )
        fig.tags.set([Tag.objects.get_or_create(project=project, name="figure")[0]])
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
            context="Single-task load manipulations confound difficulty with load "
            "(the argument in @lavie2010attention; see [[Load theory overview]]).",
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
                "abstract": (
                    "Selective attention determines which stimuli reach awareness. Load theory "
                    "proposes that the level and type of information load in a task determines the "
                    "efficiency of selective attention. Under high perceptual load that engages "
                    "full capacity, distractor processing is reduced because no spare capacity "
                    "spills over to irrelevant stimuli. In contrast, high cognitive load on "
                    "working memory reduces control over attention, increasing distractor "
                    "interference. This dissociation reconciles decades of conflicting findings "
                    "on early versus late selection and predicts when distraction will help or hurt."
                ),
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
                "abstract": (
                    "Working memory is the system that holds and manipulates information over "
                    "short timescales in service of cognition. The multicomponent model "
                    "distinguishes a central executive from two storage buffers, the phonological "
                    "loop and the visuospatial sketchpad, later joined by an episodic buffer that "
                    "binds information across modalities and links to long-term memory. Three "
                    "decades of evidence support fractionation of the system, with implications "
                    "for attention control, fluid intelligence, and the cognitive consequences of "
                    "neurological damage."
                ),
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
                "abstract": (
                    "Attention control — the ability to maintain task goals against "
                    "interference — has emerged as a strong candidate for the mechanism "
                    "linking low-level sensory discrimination to higher-order fluid intelligence. "
                    "Across a battery of tasks, individual differences in attention control "
                    "mediate the relationship between processing speed and reasoning ability. The "
                    "authors argue that measurement reliability, not construct invalidity, "
                    "explains prior null results, and propose toolbox tasks that isolate control "
                    "from working-memory capacity."
                ),
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
        demo_pdf = make_demo_pdf(
            [
                "Attention, Distraction, and Cognitive Control Under Load",
                "Demo PDF for the Atlas in-browser reader.",
                "Select any of this text to save a highlight to a note.",
                "Perceptual load gates distractor processing early;",
                "cognitive load releases it. The dissociation matters.",
            ]
        )
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
                    "abstract": spec.get("abstract", ""),
                    "entry_type": "article",
                },
            )
            ProjectReference.objects.update_or_create(
                project=project,
                reference=reference,
                defaults={"reading_status": spec["status"], "priority": spec["priority"]},
            )
            if spec["bibtex_key"] == "lavie2010attention" and not reference.pdf:
                reference.pdf.save("lavie2010-demo.pdf", ContentFile(demo_pdf), save=True)

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
                    # #448: an abstract per paper so the rail's peek and the reader's tl;dr
                    # have something to show on the demo
                    "abstract": (
                        f"{family} et al. ({year}) asked whether working-memory load changes "
                        f"how attention is allocated. In {2 + index % 3} experiments (n = "
                        f"{24 + index * 4}) they varied load and distractor salience; load "
                        f"{'reduced' if index % 2 else 'redistributed'} vigilance rather than "
                        "capping it, and the effect grew with practice. The paper is a "
                        "standard reference for the "
                        f"{'strategic' if index % 2 else 'capacity'} account."
                    ),
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

        from core.models import Comment

        if not Comment.objects.filter(object_id=hub.pk).exists():
            Comment.objects.create(
                target=hub,
                body=(
                    f"Chunking effect in [[Pilot observations]] might explain the "
                    f"outlier — see @{corpus_refs[0].bibtex_key} for a similar pattern."
                ),
            )

        from core.models import TodoItem

        for i, text in enumerate(
            [
                "Email the lab about Thursday's pilot slot",
                "Skim the two new load-theory papers",
                "Draft the ethics amendment paragraph",
            ],
            start=1,
        ):
            TodoItem.objects.get_or_create(text=text, defaults={"position": i, "project": project})
        QuickCapture.objects.get_or_create(
            text="Check whether the 2024 load-modulation preprint ever got published"
        )

        # Literature review matrix: themes × papers with a few marks
        theme_specs = [
            "Dual-task paradigm",
            "Capacity account",
            "Strategic account",
            "Pupillometry",
        ]
        themes = [
            ReviewTheme.objects.update_or_create(project=project, name=name, defaults={"order": i})[
                0
            ]
            for i, name in enumerate(theme_specs, start=1)
        ]
        matrix_links = list(project.project_references.select_related("reference"))[:8]
        for i, link in enumerate(matrix_links):
            for j, theme in enumerate(themes):
                if (i + j) % 3 == 0:
                    ReviewMark.objects.update_or_create(
                        theme=theme,
                        project_reference=link,
                        defaults={"note": "Directly tests this." if (i + j) % 6 == 0 else ""},
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
        _seed_manuscript_source(manuscript)
        # #413: a fortnight of writing — the sparkline and the streak have something to show
        from writing.models import WordCountSample
        from writing.progress import manuscript_words

        final_words = manuscript_words(manuscript)
        for days_ago, share in enumerate(
            (1.0, 0.94, 0.94, 0.9, 0.85, 0.85, 0.78, 0.7, 0.7, 0.64, 0.6, 0.52, 0.5, 0.45)
        ):
            WordCountSample.objects.update_or_create(
                manuscript=manuscript,
                date=today - datetime.timedelta(days=days_ago),
                defaults={"words": int(final_words * share)},
            )
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

        # Research: hypotheses with mixed evidence, experiment entries, datasets
        strategic_h, _ = Hypothesis.objects.update_or_create(
            project=project,
            statement="Load effects on sustained attention reflect strategic resource "
            "allocation, not a structural capacity limit.",
            defaults={"status": Hypothesis.Status.TESTING},
        )
        capacity_h, _ = Hypothesis.objects.update_or_create(
            project=project,
            statement="High WM load uniformly degrades vigilance regardless of incentive.",
            defaults={"status": Hypothesis.Status.PROPOSED},
        )
        if not strategic_h.evidence.exists():
            Evidence.objects.create(
                hypothesis=strategic_h,
                direction=Evidence.Direction.SUPPORTS,
                summary="Incentive manipulation in pilot shifted the load effect by ~40%.",
                note=pilot_note,
            )
            Evidence.objects.create(
                hypothesis=strategic_h,
                direction=Evidence.Direction.SUPPORTS,
                summary="Draheim (2022) finds attention-control variance explains load effects.",
                reference=corpus_refs[2],
            )
            Evidence.objects.create(
                hypothesis=strategic_h,
                direction=Evidence.Direction.CONTRADICTS,
                summary="Two pilot participants showed load costs even at maximal incentive.",
            )
        ExperimentEntry.objects.update_or_create(
            project=project,
            title="Pilot session block order check",
            defaults={
                "date": today - datetime.timedelta(days=8),
                "body": "Counterbalancing verified across 6 pilots. **Outcome:** no order effect "
                "visible; proceeding with frozen design.",
            },
        )[0].hypotheses.set([strategic_h])
        ExperimentEntry.objects.update_or_create(
            project=project,
            title="Incentive manipulation dry run",
            defaults={
                "date": today - datetime.timedelta(days=3),
                "body": "Bonus structure explained; comprehension check passed by 9/9. "
                "Follows the incentive framing in [[Strategic allocation hypothesis]].",
            },
        )[0].hypotheses.set([strategic_h, capacity_h])
        Dataset.objects.update_or_create(
            project=project,
            name="pilot-behavioral-v1",
            defaults={
                "location": "/data/atlas/pilot/v1/",
                "version": "2026-06-01",
                "checksum": "sha256:9f86d081884c7d659a2feaa0c55ad015",
                "description": "Pilot dual-task trials, 9 participants, pre-exclusions.",
            },
        )

        for title, body, tags in [
            (
                "Summarize paper for the lit matrix",
                "Summarize the attached paper in 5 bullets: claim, method, sample, key result, "
                "limitation. Then say which of my review-matrix themes it speaks to.",
                "lit-review, summarize",
            ),
            (
                "Summarize {{paper}} for {{venue}}",
                "Summarize {{paper}} in 5 bullets aimed at {{venue}} reviewers: claim, "
                "method, sample, key result, limitation.",
                "lit-review, variables",
            ),
            (
                "Reviewer-2 pass",
                "Act as a tough but fair Reviewer 2 on the draft below. List the three weakest "
                "points with concrete fixes. Be specific about stats and framing.",
                "writing, review",
            ),
        ]:
            Prompt.objects.update_or_create(title=title, defaults={"body": body, "tags": tags})

        from bots.models import Bot, BotRun

        reminder_bot, _ = Bot.objects.get_or_create(slug="deadline-reminder")
        if not reminder_bot.runs.exists():
            for n in (0, 1, 0, 3, 2, 0, 1, 4, 2, 1):
                BotRun.objects.create(bot=reminder_bot, ok=True, result=f"{n} new reminder(s).")
            BotRun.objects.create(
                bot=reminder_bot, ok=False, result="failed: ConnectError: network unreachable"
            )
            reminder_bot.last_run_at = timezone.now()
            reminder_bot.last_result = "1 new reminder(s)."
            reminder_bot.save()

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


def _seed_manuscript_source(manuscript):
    """A realistic multi-file LaTeX tree for the studio (Owner report 2026-09-06): main.tex
    with an \\input, real \\cite keys from the manuscript's bibliography, a table, an equation
    and a bibliography line — so the outline, cite completion, compile and PDF preview all
    have something to show. Never clobbers a source someone has actually written."""
    from writing.models import ManuscriptFile

    main = manuscript.main_file
    if main is not None and len(main.content.strip()) > 120:
        return
    keys = [
        link.cite_key for link in manuscript.manuscriptreference_set.select_related("reference")
    ]
    k = (keys + ["placeholder"] * 4)[:4]
    main_src = f"""\\documentclass[11pt]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{amsmath,booktabs,graphicx,hyperref}}
\\usepackage[numbers]{{natbib}}

\\title{{Strategic Allocation of Attention Under Working Memory Load}}
\\author{{A. Researcher \\and B. Collaborator}}
\\date{{\\today}}

\\begin{{document}}
\\maketitle

\\begin{{abstract}}
Load effects on sustained attention are usually read as a structural capacity limit.
We argue instead that they reflect a strategic trade-off, and test the account with an
incentive manipulation in a dual-task paradigm.
\\end{{abstract}}

\\section{{Introduction}}
Working-memory load reliably degrades vigilance \\citep{{{k[0]}}}. The dominant reading is a
capacity account \\citep{{{k[1]}}}; an alternative is that observers allocate a limited but
flexible resource according to payoffs \\citep{{{k[2]},{k[3]}}}. The two accounts make
different predictions when incentives change mid-block.

\\section{{Hypotheses}}
\\begin{{enumerate}}
  \\item Load costs shrink under incentive if allocation is strategic.
  \\item Load costs are invariant to incentive if the limit is structural.
\\end{{enumerate}}

\\input{{sections/method}}

\\section{{Results}}
% TODO Replace the pilot numbers with the full-sample results (n = 80).
Mean sensitivity by condition is summarised in Table~\\ref{{tab:dprime}}.

\\begin{{table}}[h]
  \\centering
  \\begin{{tabular}}{{lcc}}
    \\toprule
    Condition & Low load & High load \\\\
    \\midrule
    No incentive & 2.41 & 1.72 \\\\
    Incentive    & 2.39 & 2.18 \\\\
    \\bottomrule
  \\end{{tabular}}
  \\caption{{Sensitivity ($d'$) by load and incentive (pilot, $n = 12$).}}
  \\label{{tab:dprime}}
\\end{{table}}

\\begin{{figure}}[h]
  \\centering
  \\includegraphics[width=0.6\\textwidth]{{figures/pilot-dprime}}
  \\caption{{Pilot sensitivity by condition (bars: low vs.\\ high load).}}
  \\label{{fig:pilot}}
\\end{{figure}}

The load cost under incentive (Figure~\\ref{{fig:pilot}}) was
\\begin{{equation}}
  \\Delta d' = d'_{{\\text{{low}}}} - d'_{{\\text{{high}}}} = 0.21,
  \\label{{eq:cost}}
\\end{{equation}}
roughly 30\\% of the cost without incentive.

\\section{{Discussion}}
A structural limit cannot shrink by 70\\% because money was offered. The pattern favours
strategic allocation, with the residual cost as an upper bound on the structural component.

\\bibliographystyle{{plainnat}}
\\bibliography{{references}}

\\end{{document}}
"""
    method_src = """\\section{Method}
\\subsection{Participants}
% FIXME The power analysis R2 asked for is still missing here.
Twelve pilot participants (target $n = 80$ after the power analysis requested by R2).

\\subsection{Design}
A $2 \\times 2$ within-subject design crossing working-memory load (low, high) with
incentive (none, performance-contingent bonus). Blocks were counterbalanced.

\\subsection{Procedure}
Each block paired a sustained-attention task with a concurrent memory set. Targets appeared
for 250 ms with a 1.5 s response window; conditions are listed in Table \\ref{tab:dprime}. The
bonus structure was explained before incentive blocks and verified by a comprehension check.
"""
    manuscript.latex_source = main_src
    manuscript.save(update_fields=["latex_source", "updated_at"])
    main = manuscript.ensure_main_file()
    if main.content != main_src:
        main.content = main_src
        main.save()
    ManuscriptFile.objects.update_or_create(
        manuscript=manuscript,
        path="sections/method.tex",
        defaults={"content": method_src, "kind": ManuscriptFile.Kind.TEX},
    )
    # #473: a real raster figure in the tree so the figure audit has something to measure
    # (1600 px at 0.6\textwidth ≈ 410 dpi — prints sharp)
    fig, created = ManuscriptFile.objects.get_or_create(
        manuscript=manuscript,
        path="figures/pilot-dprime.png",
        defaults={"kind": ManuscriptFile.Kind.ASSET},
    )
    if created or not fig.asset:
        fig.asset.save("pilot-dprime.png", ContentFile(_demo_png(1600, 1000)), save=True)


def _demo_png(width: int = 320, height: int = 200) -> bytes:
    """A small bar-chart-like PNG built from raw scanlines (no image library needed)."""
    import struct
    import zlib

    bars = [(40, 150, 0.85), (100, 150, 0.6), (180, 150, 0.83), (240, 150, 0.77)]  # x, w, height
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            colour = (245, 244, 240)
            for i, (bx, _bw, h) in enumerate(bars):
                if bx <= x < bx + 50 and y > height - int(h * (height - 20)):
                    colour = (79, 70, 229) if i % 2 == 0 else (16, 185, 129)
            if y == height - 12:
                colour = (120, 113, 108)
            row += bytes(colour)
        rows.append(bytes(row))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )
