from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Document, Folder, Tag
from literature import services as literature_services
from literature.models import ProjectReference, Reference
from notes import services as note_services
from notes.models import Note, QuickCapture
from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.models import DecisionRecord, Project
from prompts.models import Prompt

from . import serializers
from .authentication import APIKeyAuthentication


@method_decorator(login_not_required, name="dispatch")
class AtlasViewSet(viewsets.ModelViewSet):
    """Base viewset: exempt from session-login middleware; guarded by X-API-Key auth instead.

    Subclasses can set `project_filter` to a lookup path that allows filtering the
    queryset with the `?project=<slug>` query parameter.
    """

    project_filter: str | None = None

    def get_queryset(self):
        queryset = super().get_queryset()
        slug = self.request.query_params.get("project")
        if slug and self.project_filter:
            queryset = queryset.filter(**{self.project_filter: slug})
        return queryset

    # --- conditional GETs: cheap ETags so MCP/scripted polling can 304 ---

    def _list_etag(self):
        import hashlib

        from django.db.models import Count, Max

        try:
            agg = self.filter_queryset(self.get_queryset()).aggregate(
                n=Count("pk"), latest=Max("updated_at")
            )
        except Exception:
            return None
        raw = f"{self.request.get_full_path()}|{agg['n']}|{agg['latest']}"
        return f'W/"{hashlib.md5(raw.encode()).hexdigest()}"'

    def _conditional(self, request, etag, render):
        if etag and request.headers.get("If-None-Match") == etag:
            response = Response(status=status.HTTP_304_NOT_MODIFIED)
        else:
            response = render()
        if etag:
            response["ETag"] = etag
        return response

    def list(self, request, *args, **kwargs):
        return self._conditional(
            request,
            self._list_etag(),
            lambda: super(AtlasViewSet, self).list(request, *args, **kwargs),
        )

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        updated = getattr(obj, "updated_at", None)
        etag = f'W/"{obj.pk}-{updated.timestamp()}"' if updated else None
        return self._conditional(
            request, etag, lambda: super(AtlasViewSet, self).retrieve(request, *args, **kwargs)
        )


class ProjectViewSet(AtlasViewSet):
    queryset = Project.objects.all()
    serializer_class = serializers.ProjectSerializer
    lookup_field = "slug"

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Knowledge graph: {nodes: [...], links: [...]}")
        },
        description=(
            "The project's knowledge graph. Nodes are references and notes "
            "(id, type, label, group, size); links are citations, note-links, "
            "and note→reference citations (source, target, kind)."
        ),
    )
    @action(detail=True, methods=["get"])
    def graph(self, request, slug=None):
        from core.graph import project_graph

        return Response(project_graph(self.get_object()))

    @extend_schema(
        responses={200: OpenApiResponse(description="Situational summary of the project")},
        description="One-glance overview: current phase, progress, next milestones, counts.",
    )
    @action(detail=True, methods=["get"])
    def overview(self, request, slug=None):
        from plans import selectors as plan_selectors

        project = self.get_object()
        done, total, percent = plan_selectors.project_progress(project)
        phase = plan_selectors.current_phase(project)
        return Response(
            {
                "project": serializers.ProjectSerializer(project).data,
                "current_phase": serializers.PhaseSerializer(phase).data if phase else None,
                "progress": {"done": done, "total": total, "percent": percent},
                "next_milestones": [
                    {
                        "id": m.pk,
                        "title": m.title,
                        "due_date": m.due_date,
                        "overdue": m.is_overdue,
                        "phase": m.phase.name,
                    }
                    for m in plan_selectors.upcoming_milestones(project)
                ],
                "counts": {
                    "documents": project.documents.count(),
                    "decisions": project.decisions.count(),
                    "questions": project.questions.count(),
                    "references": project.project_references.count(),
                    "notes": project.notes.count(),
                    "manuscripts": project.manuscripts.count(),
                    "hypotheses": project.hypotheses.count(),
                },
                # SPA overview extras (Owner idea #20 slice 2)
                "recent_documents": [
                    {
                        "id": d.pk,
                        "title": d.title,
                        "added": d.created_at.strftime("%Y-%m-%d"),
                        "url": reverse("documents:download", args=[project.slug, d.pk]),
                    }
                    for d in project.documents.order_by("-created_at")[:5]
                ],
                "recent_decisions": [
                    {
                        "id": dec.pk,
                        "title": dec.title,
                        "decided_on": dec.decided_on.isoformat(),
                    }
                    for dec in project.decisions.all()[:5]
                ],
            }
        )

    @extend_schema(
        responses={200: OpenApiResponse(description="Phases with nested milestones and tasks")},
        description="The full plan: ordered phases, their milestones, and optional tasks.",
    )
    @action(detail=True, methods=["get"])
    def plan(self, request, slug=None):
        project = self.get_object()
        phases = []
        for phase in project.phases.prefetch_related("milestones__tasks"):
            phases.append(
                {
                    "id": phase.pk,
                    "name": phase.name,
                    "order": phase.order,
                    "status": phase.status,
                    "progress": phase.progress,
                    "milestones": [
                        {
                            "id": m.pk,
                            "title": m.title,
                            "due_date": m.due_date,
                            "completed_at": m.completed_at,
                            "overdue": m.is_overdue,
                            "tasks": [
                                {"id": t.pk, "title": t.title, "done": t.done}
                                for t in m.tasks.all()
                            ],
                        }
                        for m in phase.milestones.all()
                    ],
                }
            )
        return Response({"project": project.slug, "phases": phases})

    @extend_schema(
        responses={200: OpenApiResponse(description="Unread references, highest priority first")},
        description="The reading queue: to-read and skimmed references sorted by priority.",
    )
    @action(detail=True, methods=["get"], url_path="reading-queue")
    def reading_queue(self, request, slug=None):
        from literature.views import PRIORITY_ORDER

        project = self.get_object()
        links = list(
            project.project_references.filter(
                reading_status__in=["to_read", "skimmed"]
            ).select_related("reference")
        )
        links.sort(key=lambda link: (PRIORITY_ORDER[link.priority], link.created_at))
        return Response(
            [
                {
                    "id": link.pk,
                    "reference_id": link.reference_id,
                    "bibtex_key": link.reference.bibtex_key,
                    "title": link.reference.title,
                    "year": link.reference.year,
                    "reading_status": link.reading_status,
                    "priority": link.priority,
                }
                for link in links
            ]
        )

    @extend_schema(
        responses={200: OpenApiResponse(description="Themes × papers with marks and notes")},
        description="The literature review matrix: which paper covers which theme.",
    )
    @action(detail=True, methods=["get"], url_path="review-matrix")
    def review_matrix(self, request, slug=None):
        from literature.models import ReviewMark

        project = self.get_object()
        themes = list(project.review_themes.all())
        marks = {}
        for mark in ReviewMark.objects.filter(theme__project=project).select_related("theme"):
            marks.setdefault(mark.project_reference_id, {})[mark.theme.name] = mark.note or True
        papers = [
            {
                "bibtex_key": link.reference.bibtex_key,
                "title": link.reference.title,
                "reading_status": link.reading_status,
                "marks": marks.get(link.pk, {}),
            }
            for link in project.project_references.select_related("reference")
        ]
        return Response({"themes": [t.name for t in themes], "papers": papers})

    @extend_schema(
        responses={200: OpenApiResponse(description="Bib checker findings grouped by category")},
        description=(
            "Run the bib checkers over the project's references. Pass ?network=1 to include "
            "DOI-resolution and retraction checks (slower, calls external APIs)."
        ),
    )
    @action(detail=True, methods=["get"], url_path="bib-report")
    def bib_report(self, request, slug=None):
        project = self.get_object()
        references = Reference.objects.filter(project_links__project=project)
        include_network = request.query_params.get("network") == "1"
        report = literature_services.run_bib_report(
            references, include_network_checks=include_network
        )
        return Response(
            {
                "network_checks_included": include_network,
                "findings": {
                    category: [
                        {
                            "level": f["level"],
                            "message": f["message"],
                            "reference_ids": [r.pk for r in f["references"]],
                        }
                        for f in findings
                    ]
                    for category, findings in report.items()
                },
            }
        )


class PhaseViewSet(AtlasViewSet):
    queryset = Phase.objects.all()
    serializer_class = serializers.PhaseSerializer
    project_filter = "project__slug"


class MilestoneViewSet(AtlasViewSet):
    queryset = Milestone.objects.all()
    serializer_class = serializers.MilestoneSerializer
    project_filter = "phase__project__slug"


class TaskViewSet(AtlasViewSet):
    queryset = Task.objects.all()
    serializer_class = serializers.TaskSerializer
    project_filter = "milestone__phase__project__slug"


class ResearchQuestionViewSet(AtlasViewSet):
    queryset = ResearchQuestion.objects.all()
    serializer_class = serializers.ResearchQuestionSerializer
    project_filter = "project__slug"


class DecisionRecordViewSet(AtlasViewSet):
    queryset = DecisionRecord.objects.all()
    serializer_class = serializers.DecisionRecordSerializer
    project_filter = "project__slug"


class FolderViewSet(AtlasViewSet):
    queryset = Folder.objects.all()
    serializer_class = serializers.FolderSerializer
    project_filter = "project__slug"


class TagViewSet(AtlasViewSet):
    queryset = Tag.objects.all()
    serializer_class = serializers.TagSerializer
    project_filter = "project__slug"


class DocumentViewSet(AtlasViewSet):
    queryset = Document.objects.all()
    serializer_class = serializers.DocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    project_filter = "project__slug"


class ReferenceViewSet(AtlasViewSet):
    queryset = Reference.objects.all()
    serializer_class = serializers.ReferenceSerializer
    project_filter = "project_links__project__slug"

    @extend_schema(
        request=serializers.AddByDoiSerializer,
        responses={
            200: serializers.ReferenceSerializer,
            201: serializers.ReferenceSerializer,
            400: OpenApiResponse(description="Identifier could not be resolved"),
        },
        description=(
            "Add a reference by DOI or arXiv ID. Metadata is fetched from Crossref with an "
            "OpenAlex fallback. Pass an optional project slug to also link the reference."
        ),
    )
    @action(detail=False, methods=["post"], url_path="by-doi")
    def by_doi(self, request):
        serializer = serializers.AddByDoiSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reference, created = literature_services.add_reference_by_identifier(
                serializer.validated_data["doi"]
            )
        except literature_services.MetadataError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        slug = serializer.validated_data.get("project")
        if slug:
            project = get_object_or_404(Project, slug=slug)
            ProjectReference.objects.get_or_create(project=project, reference=reference)
        if created and settings.ATLAS_AUTO_FETCH_PDF and not reference.pdf:
            from literature.tasks import fetch_oa_pdf_task

            fetch_oa_pdf_task(reference.pk)
        return Response(
            serializers.ReferenceSerializer(reference, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        responses={200: OpenApiResponse(description="Most similar library references with scores")},
        description="Related papers in the library (TF-IDF cosine over title/abstract/venue).",
    )
    @action(detail=True, methods=["get"])
    def related(self, request, pk=None):
        from literature.related import related_references

        return Response(
            [
                {
                    "id": ref.pk,
                    "bibtex_key": ref.bibtex_key,
                    "title": ref.title,
                    "year": ref.year,
                    "score": round(score, 3),
                }
                for ref, score in related_references(self.get_object())
            ]
        )


class ProjectReferenceViewSet(AtlasViewSet):
    queryset = ProjectReference.objects.all()
    serializer_class = serializers.ProjectReferenceSerializer
    project_filter = "project__slug"


class QuickCaptureViewSet(AtlasViewSet):
    queryset = QuickCapture.objects.all()
    serializer_class = serializers.QuickCaptureSerializer
    project_filter = "project__slug"


class PromptViewSet(AtlasViewSet):
    queryset = Prompt.objects.all()
    serializer_class = serializers.PromptSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.query_params.get("q")
        if query:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(title__icontains=query) | Q(body__icontains=query) | Q(tags__icontains=query)
            )
        return queryset


class NoteViewSet(AtlasViewSet):
    queryset = Note.objects.all()
    serializer_class = serializers.NoteSerializer
    project_filter = "project__slug"

    def perform_create(self, serializer):
        note = serializer.save()
        note_services.sync_note_links(note)

    def perform_update(self, serializer):
        note = serializer.save()
        note_services.sync_note_links(note)


@method_decorator(login_not_required, name="dispatch")
class SearchAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]

    @extend_schema(
        parameters=[OpenApiParameter(name="q", type=str, required=True, description="Search text")],
        responses={200: OpenApiResponse(description="Ranked results grouped by object type")},
        description="Global full-text search across projects, references, notes, documents, decisions, and plans.",
    )
    def get(self, request):
        from core.search import search_all

        results = []
        for result in search_all(request.query_params.get("q", "")):
            obj = result["object"]
            results.append(
                {
                    "type": result["type"],
                    "id": obj.pk,
                    "label": str(obj),
                    "project": result["project"].slug if result["project"] else None,
                    "url": obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else None,
                }
            )
        return Response({"query": request.query_params.get("q", ""), "results": results})


class DashboardAPIView(APIView):
    """Everything the dashboard shows, as JSON — the SPA's first data source."""

    @extend_schema(
        description="Dashboard data: stats, active projects with progress, "
        "upcoming milestones and deadlines, inbox count.",
        responses={200: None},
    )
    def get(self, request):
        from django.urls import reverse

        from core.dashboard import dashboard_context

        data = dashboard_context()
        return Response(
            {
                "stats": data["stats"],
                "inbox_count": data["inbox_count"],
                "active": [
                    {
                        "name": row["project"].name,
                        "slug": row["project"].slug,
                        "url": row["project"].get_absolute_url(),
                        "color": row["project"].color,
                        "phase": row["phase"].name if row["phase"] else None,
                        "done": row["done"],
                        "total": row["total"],
                        "percent": row["percent"],
                        "tree_size": row["tree_size"],
                    }
                    for row in data["active"]
                ],
                "milestones": [
                    {
                        "title": m.title,
                        "project": m.phase.project.name,
                        "due_date": m.due_date.isoformat() if m.due_date else None,
                        "overdue": m.is_overdue,
                        "url": reverse("plans:plan", args=[m.phase.project.slug]),
                    }
                    for m in data["milestones"]
                ],
                "deadlines": [
                    {
                        "title": d.title,
                        "deadline": d.deadline.isoformat() if d.deadline else None,
                        "url": d.get_absolute_url(),
                    }
                    for d in data["deadlines"]
                ],
            }
        )
