from django.contrib.auth.decorators import login_not_required
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from documents.models import Document, Folder, Tag
from literature import services as literature_services
from literature.models import ProjectReference, Reference
from notes.models import QuickCapture
from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.models import DecisionRecord, Project

from . import serializers


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
        return Response(
            serializers.ReferenceSerializer(reference, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ProjectReferenceViewSet(AtlasViewSet):
    queryset = ProjectReference.objects.all()
    serializer_class = serializers.ProjectReferenceSerializer
    project_filter = "project__slug"


class QuickCaptureViewSet(AtlasViewSet):
    queryset = QuickCapture.objects.all()
    serializer_class = serializers.QuickCaptureSerializer
    project_filter = "project__slug"
