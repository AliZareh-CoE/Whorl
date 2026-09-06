from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers as rf_serializers
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import TodoItem
from documents.models import Document, Folder, Tag
from literature import services as literature_services
from literature.models import LibraryTag, ProjectReference, Reference, SavedView
from notes import services as note_services
from notes.models import Note, QuickCapture
from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.models import DecisionRecord, Project
from prompts.models import Prompt
from research.models import Dataset, ExperimentEntry, Hypothesis, Protocol
from writing.models import Manuscript

from . import serializers
from .authentication import APIKeyAuthentication


@method_decorator(login_not_required, name="dispatch")
class AtlasViewSet(viewsets.ModelViewSet):
    """Base viewset: exempt from session-login middleware; guarded by X-API-Key auth instead.

    Subclass knobs (Backlog #100 — one place instead of per-viewset overrides):
    - `project_filter`: lookup path enabling the `?project=<slug>` query parameter.
    - `q_fields`: fields searched (icontains, OR) by the `?q=` query parameter.
    - `bulk_create`: POST a JSON list to create many objects in one call.
    """

    project_filter: str | None = None
    q_fields: tuple[str, ...] = ()
    bulk_create = False

    def get_queryset(self):
        queryset = super().get_queryset()
        slug = self.request.query_params.get("project")
        if slug and self.project_filter:
            queryset = queryset.filter(**{self.project_filter: slug})
        # AUDIT #10: cap the needle like ?theme= — unbounded input is free DoS surface
        q = (self.request.query_params.get("q") or "").strip()[:200]
        if q and self.q_fields:
            from django.db.models import Q

            match = Q()
            for field in self.q_fields:
                match |= Q(**{f"{field}__icontains": q})
            queryset = queryset.filter(match)
        return queryset

    def get_serializer(self, *args, **kwargs):
        if self.bulk_create and isinstance(kwargs.get("data"), list):
            kwargs["many"] = True
        return super().get_serializer(*args, **kwargs)

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
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        request=None,
        responses={201: OpenApiResponse(description="Uploaded files into the workspace")},
        description="Upload one or more files into the workspace (optionally a folder), "
        "as general tree nodes. Multipart: files[], optional folder id.",
    )
    @action(detail=True, methods=["post"], url_path="upload-file")
    def upload_file(self, request, slug=None):
        from django.core.exceptions import ValidationError as DjangoVE

        from core.security import validate_upload_size
        from documents.models import Document
        from documents.paths import kind_for_node_path

        project = self.get_object()
        folder = None
        prefix = ""
        if request.data.get("folder"):
            folder = get_object_or_404(project.folders, pk=request.data["folder"])
            parts, node = [], folder
            while node is not None:
                parts.append(node.name)
                node = node.parent
            prefix = "/".join(reversed(parts)) + "/"
        created, errors = [], []
        for f in request.FILES.getlist("files"):
            try:
                validate_upload_size(f)
            except DjangoVE as exc:
                errors.append(f"{f.name}: {exc.messages[0]}")
                continue
            rel_path = f"{prefix}{f.name}"
            doc = Document.objects.create(
                project=project,
                folder=folder,
                file=f,
                title=f.name,
                rel_path=rel_path,
                role=Document.Role.GENERAL,
                kind=kind_for_node_path(f.name),
            )
            created.append(doc.rel_path)
        return Response({"created": created, "errors": errors}, status=201 if created else 400)

    def perform_create(self, serializer):
        project = serializer.save()
        # optional scaffold (file-workspace epic #30, slice 7)
        template = self.request.data.get("template")
        if template:
            from projects.services import instantiate_template

            instantiate_template(project, template)

    @extend_schema(
        responses={200: OpenApiResponse(description="Available project scaffolds")},
        description="Project templates that scaffold an organized folder structure on "
        "creation (POST /projects/ with an optional `template` key).",
    )
    @action(detail=False, methods=["get"], url_path="templates")
    def templates(self, request):
        from projects.models import ProjectTemplate
        from projects.project_templates import template_list

        items = template_list()  # built-in (code) scaffolds
        for t in ProjectTemplate.objects.all():  # user-saved
            items.append(
                {
                    "key": t.name,
                    "name": t.name,
                    "description": t.description,
                    "folders": t.structure.get("folders", []),
                    "saved": True,
                }
            )
        return Response(items)

    @extend_schema(
        request=None,
        responses={201: OpenApiResponse(description="Saved a reusable template")},
        description="Snapshot this project's general folder/file structure as a reusable "
        "user template (file-workspace epic): POST {name, description}.",
    )
    @action(detail=True, methods=["post"], url_path="save-template")
    def save_template(self, request, slug=None):
        from projects.services import save_project_as_template

        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "A template name is required."}, status=400)
        template = save_project_as_template(
            self.get_object(), name, request.data.get("description", "")
        )
        return Response({"name": template.name, "structure": template.structure}, status=201)

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
        responses={200: OpenApiResponse(description="iCalendar feed (text/calendar)")},
        description="An iCalendar (.ics) feed of the project's deadlines — every milestone "
        "due date and manuscript deadline as an all-day event — to subscribe to in any "
        "calendar app or automation.",
    )
    @action(detail=True, methods=["get"], url_path="calendar.ics")
    def calendar_ics(self, request, slug=None):
        from django.http import HttpResponse

        from core.calendar import build_project_ics

        project = self.get_object()
        response = HttpResponse(build_project_ics(project), content_type="text/calendar")
        response["Content-Disposition"] = f'inline; filename="{project.slug}.ics"'
        return response

    @extend_schema(
        responses={200: OpenApiResponse(description="The project's images for a figure gallery")},
        description="Every inline-previewable raster image in the project (newest first) for a "
        "figure gallery — id, title, folder, tags, size, plus a `raw_url` that serves the image "
        "inline. SVG is excluded (script-bearing).",
    )
    @action(detail=True, methods=["get"])
    def figures(self, request, slug=None):
        from documents.selectors import project_figures

        items = project_figures(self.get_object())
        for fig in items:
            fig["raw_url"] = request.build_absolute_uri(f"/api/v1/documents/{fig['id']}/raw/")
        return Response(items)

    @extend_schema(
        responses={200: OpenApiResponse(description="The project's whole file tree")},
        description="Unified file workspace tree (file-workspace epic): every folder and "
        "every file node — general documents and manuscript sources — as flat "
        "{folders, files} lists for a client-side explorer.",
    )
    @action(detail=True, methods=["get"])
    def tree(self, request, slug=None):
        from documents.selectors import workspace_tree

        return Response(workspace_tree(self.get_object()))

    @extend_schema(
        request=None,
        responses={
            200: OpenApiResponse(description="Updated a general file"),
            201: OpenApiResponse(description="Created a general file"),
            409: OpenApiResponse(description="Manuscript files are edited in the LaTeX editor"),
        },
        description="Create-or-update a general text file at a tree path (workspace / MCP "
        "write): POST {path, content}. Manuscript-source paths are refused.",
    )
    @action(detail=True, methods=["post"], url_path="write-file")
    def write_file(self, request, slug=None):
        from django.core.exceptions import ValidationError as DjangoVE

        from documents.models import Document, Folder
        from documents.paths import kind_for_node_path, validate_workspace_name

        project = self.get_object()
        path = (request.data.get("path") or "").strip().strip("/")
        content = request.data.get("content", "")
        if not path:
            return Response({"detail": "A file path is required."}, status=400)
        segments = path.split("/")
        try:
            for seg in segments:
                validate_workspace_name(seg)
        except DjangoVE as exc:
            return Response({"detail": str(exc.messages[0])}, status=400)
        if segments[0].startswith("manuscript-"):
            return Response({"detail": "Manuscript files are edited in the LaTeX editor."}, 409)

        *dirs, filename = segments
        parent = None
        for name in dirs:
            parent, _ = Folder.objects.get_or_create(project=project, parent=parent, name=name)
        doc, created = Document.objects.get_or_create(
            project=project,
            rel_path=path,
            defaults={
                "folder": parent,
                "title": filename,
                "role": Document.Role.GENERAL,
                "kind": kind_for_node_path(path),
                "content": content,
            },
        )
        if not created:
            if doc.role == "manuscript_source":
                return Response({"detail": "Manuscript files are edited in the editor."}, 409)
            doc.content = content
            doc.save(update_fields=["content", "updated_at"])
        return Response(
            {"id": doc.id, "rel_path": doc.rel_path, "created": created},
            status=201 if created else 200,
        )

    @extend_schema(
        responses={200: OpenApiResponse(description="Situational summary of the project")},
        description="One-glance overview: current phase, progress, next milestones, counts.",
    )
    @action(detail=True, methods=["get"])
    def overview(self, request, slug=None):
        from documents.models import PREVIEWABLE_IMAGE_TYPES
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
                    "documents": project.documents.general().count(),
                    "figures": project.documents.filter(
                        content_type__in=PREVIEWABLE_IMAGE_TYPES
                    ).count(),
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
                    for d in project.documents.general().order_by("-created_at")[:5]
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
        responses={200: OpenApiResponse(description="The synthesis scaffold markdown")},
        description="A theme-organized literature-review scaffold for the project — read-only "
        "(does not create a note). For drafting a review section in chat.",
    )
    @action(detail=True, methods=["get"])
    def synthesis(self, request, slug=None):
        from literature.selectors import synthesis_scaffold

        project = self.get_object()
        return Response({"scaffold": synthesis_scaffold(project)})

    @extend_schema(
        responses={200: OpenApiResponse(description="Chronological event stream + markdown")},
        description="The project's research timeline: every dated event (milestones, papers, "
        "notes, decisions, experiments, hypotheses, documents, manuscript events) newest "
        "first, plus an oldest-first markdown rendering for a paper's methods/history section.",
    )
    @action(detail=True, methods=["get"])
    def timeline(self, request, slug=None):
        from core.timeline import project_timeline, timeline_markdown

        project = self.get_object()
        events = project_timeline(project)
        return Response({"events": events, "markdown": timeline_markdown(project, events)})

    @extend_schema(
        responses={200: OpenApiResponse(description="Ordered reading queue for reading-flow mode")},
        description="Unread/skimmed papers, priority-ordered, with the fields the focused "
        "reading-flow session needs.",
    )
    @action(detail=True, methods=["get"], url_path="reading-flow")
    def reading_flow(self, request, slug=None):
        from literature.views import PRIORITY_ORDER

        project = self.get_object()
        links = list(
            project.project_references.filter(
                reading_status__in=["to_read", "skimmed"]
            ).select_related("reference")
        )
        links.sort(key=lambda link: (PRIORITY_ORDER[link.priority], link.created_at))
        return Response(
            {
                "papers": [
                    {
                        "id": link.pk,
                        "reading_status": link.reading_status,
                        "priority": link.priority,
                        "reference": {
                            "id": link.reference.pk,
                            "bibtex_key": link.reference.bibtex_key,
                            "title": link.reference.title,
                            "authors": link.reference.authors,
                            "year": link.reference.year,
                            "venue": link.reference.venue,
                            "abstract": link.reference.abstract,
                            "pdf": link.reference.pdf.url if link.reference.pdf else None,
                            "doi": link.reference.doi,
                        },
                    }
                    for link in links
                ]
            }
        )

    @extend_schema(
        responses={200: OpenApiResponse(description="Props for the React documents table")},
        description="Documents table data for the SPA: rows, folders, tags, bulk endpoint.",
    )
    @action(detail=True, methods=["get"], url_path="documents-table")
    def documents_table(self, request, slug=None):
        from documents.views import documents_table_props

        project = self.get_object()
        documents = project.documents.general().select_related("folder").prefetch_related("tags")
        if request.query_params.get("folder"):
            documents = documents.filter(folder_id=request.query_params["folder"])
        return Response(documents_table_props(project, documents))

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
        return Response(
            {
                "project": project.slug,
                # the SPA plan page prints the name and paints progress in the accent colour
                "project_name": project.name,
                "project_color": project.color,
                "phases": phases,
            }
        )

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
        from literature.selectors import theme_coverage

        return Response(
            {
                "themes": [t.name for t in themes],
                "papers": papers,
                "coverage": theme_coverage(project),
            }
        )

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
    q_fields = ("title",)  # Backlog #72
    bulk_create = True  # Backlog #71


class TaskViewSet(AtlasViewSet):
    queryset = Task.objects.all()
    serializer_class = serializers.TaskSerializer
    project_filter = "milestone__phase__project__slug"
    q_fields = ("title",)  # Backlog #80
    bulk_create = True


class ResearchQuestionViewSet(AtlasViewSet):
    queryset = ResearchQuestion.objects.all()
    serializer_class = serializers.ResearchQuestionSerializer
    project_filter = "project__slug"
    q_fields = ("question",)  # Backlog #100: search opt-in


class DecisionRecordViewSet(AtlasViewSet):
    queryset = DecisionRecord.objects.all()
    serializer_class = serializers.DecisionRecordSerializer
    project_filter = "project__slug"
    q_fields = ("title", "decision")  # Backlog #100: search opt-in


def _manuscript_root_ids(project):
    return set(
        project.manuscripts.exclude(root_folder__isnull=True).values_list(
            "root_folder_id", flat=True
        )
    )


class FolderViewSet(AtlasViewSet):
    queryset = Folder.objects.all()
    serializer_class = serializers.FolderSerializer
    project_filter = "project__slug"

    def _guard(self, folder):
        # manuscript folders (root + subtree) are owned by the LaTeX editor / the mirror
        from rest_framework.exceptions import PermissionDenied

        roots = _manuscript_root_ids(folder.project)
        node = folder
        while node is not None:
            if node.pk in roots:
                raise PermissionDenied("Manuscript folders are managed in the LaTeX editor.")
            node = node.parent

    def perform_update(self, serializer):
        self._guard(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._guard(instance)
        instance.delete()


class TagViewSet(AtlasViewSet):
    queryset = Tag.objects.all()
    serializer_class = serializers.TagSerializer
    project_filter = "project__slug"


# Inline-previewable binary types (file-workspace epic #30, slice 2c). Allowlist, not
# blocklist — SVG is deliberately absent (inline SVG can execute script on our origin).
INLINE_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}
TEXT_PREVIEW_KINDS = {"tex", "bib", "other"}
TEXT_PREVIEW_CAP = 1_000_000  # 1 MB of text


class DocumentViewSet(AtlasViewSet):
    queryset = Document.objects.all()
    serializer_class = serializers.DocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    project_filter = "project__slug"

    def _guard(self, doc):
        from rest_framework.exceptions import PermissionDenied

        if doc.role == "manuscript_source":
            raise PermissionDenied("Manuscript files are managed in the LaTeX editor.")

    def perform_update(self, serializer):
        self._guard(serializer.instance)
        doc = serializer.save()
        # workspace move: keep rel_path in sync when a general file changes folder
        if doc.role == Document.Role.GENERAL:
            filename = doc.rel_path.rsplit("/", 1)[-1] if doc.rel_path else (doc.title or "file")
            parts, node = [], doc.folder
            while node is not None:
                parts.append(node.name)
                node = node.parent
            new_rel = "/".join([*reversed(parts), filename]) if parts else filename
            if new_rel != doc.rel_path:
                doc.rel_path = new_rel
                doc.save(update_fields=["rel_path", "updated_at"])

    def perform_destroy(self, instance):
        self._guard(instance)
        instance.delete()

    @extend_schema(
        responses={200: OpenApiResponse(description="Text content of a file node")},
        description="UTF-8 text of a previewable file node (text kinds) for the workspace "
        "viewer — inline content for tree nodes, decoded file bytes for uploaded text.",
    )
    @action(detail=True, methods=["get"])
    def content(self, request, pk=None):
        doc = self.get_object()
        if doc.content:
            text = doc.content
        elif doc.kind in TEXT_PREVIEW_KINDS and doc.file:
            try:
                text = doc.file.read().decode("utf-8")
            except (UnicodeDecodeError, OSError):
                return Response({"detail": "Not a UTF-8 text file."}, status=415)
        else:
            return Response({"detail": "No text preview for this file."}, status=415)
        return Response(
            {
                "id": doc.id,
                "rel_path": doc.rel_path,
                "kind": doc.kind,
                "content": text[:TEXT_PREVIEW_CAP],
                "truncated": len(text) > TEXT_PREVIEW_CAP,
            }
        )

    @extend_schema(
        request=None,
        responses={
            200: OpenApiResponse(description="Saved"),
            409: OpenApiResponse(description="Manuscript sources are edited in the LaTeX editor"),
        },
        description="Save edited text for a general file node (workspace in-place editing). "
        "Manuscript-source nodes are read-only here — they sync from the LaTeX editor.",
    )
    @content.mapping.put
    def save_content(self, request, pk=None):
        doc = self.get_object()
        if doc.role == "manuscript_source":
            return Response(
                {"detail": "Manuscript files are edited in the LaTeX editor."}, status=409
            )
        text = request.data.get("content", "")
        if len(text) > TEXT_PREVIEW_CAP:
            return Response({"detail": "File too large to edit in-app."}, status=413)
        from django.core.files.base import ContentFile

        if doc.file:
            doc.file.save(doc.file.name.rsplit("/", 1)[-1], ContentFile(text.encode()), save=False)
        doc.content = text
        doc.save()
        return Response({"id": doc.id, "saved": True})

    @extend_schema(
        responses={200: OpenApiResponse(description="Raw file bytes, inline")},
        description="Raw bytes of an image/PDF file node, inline, for the workspace preview. "
        "Allowlisted content types only (no SVG); nosniff.",
    )
    @action(detail=True, methods=["get"])
    def raw(self, request, pk=None):
        from django.http import FileResponse, Http404

        from documents.models import sniff_image_type

        doc = self.get_object()
        ext = (doc.rel_path or doc.file.name if doc.file else "").rsplit(".", 1)
        suffix = ext[-1].lower() if len(ext) == 2 else ""
        content_type = INLINE_CONTENT_TYPES.get(suffix)
        if not doc.file or content_type is None:
            raise Http404("Not inline-previewable.")
        # #250: the extension only *claims* the type; confirm with the real magic bytes before
        # serving inline, so a mislabeled file (e.g. HTML named .png) can't reach the inline path.
        handle = doc.file.open("rb")
        head = handle.read(32)
        handle.seek(0)
        confirmed = (
            head.startswith(b"%PDF-")
            if content_type == "application/pdf"
            else (sniff_image_type(head) == content_type)
        )
        if not confirmed:
            handle.close()
            raise Http404("Not inline-previewable.")
        response = FileResponse(handle, content_type=content_type)
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Disposition"] = "inline"
        # #254: uploaded files are immutable (edits create new files), so let the workspace
        # PDF/image preview revalidate cheaply instead of re-downloading on every view — matching
        # document_download / document_preview.
        response["Cache-Control"] = "private, max-age=86400"
        return response


class ReferenceViewSet(AtlasViewSet):
    queryset = Reference.objects.prefetch_related("project_links__project")
    serializer_class = serializers.ReferenceSerializer
    project_filter = "project_links__project__slug"

    def get_queryset(self):
        # Library v2 workbench filters (q, year, year_min/max, entry_type, venue, has_pdf,
        # needs_metadata, project, reading_status, unfiled, sort) — see literature/library.py.
        from literature.library import filter_references

        queryset = Reference.objects.prefetch_related("project_links__project")
        if self.action == "list":
            return filter_references(queryset, self.request.query_params)
        return queryset

    @extend_schema(
        parameters=[OpenApiParameter("project", str, description="Optional project slug")],
        responses={
            200: OpenApiResponse(
                description="Facet counts: years, entry types, venues, projects, PDF/needs-metadata/unfiled totals"
            )
        },
        description="Counts that drive the Library's filter rail, over the whole library (or one project).",
    )
    @action(detail=False, methods=["get"])
    def facets(self, request):
        from literature.library import facets

        queryset = Reference.objects.all()
        slug = request.query_params.get("project")
        if slug:
            queryset = queryset.filter(project_links__project__slug=slug).distinct()
        return Response(facets(queryset))

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "kind",
                str,
                description="similar (OpenAlex related works), references (what it cites), or cited_by (what cites it)",
            ),
            OpenApiParameter("limit", int, description="Max rows (default 12, max 50)"),
        ],
        responses={
            200: OpenApiResponse(
                description="Rows: title, authors, year, venue, doi, citations, in_library, library_id, addable"
            )
        },
        description=(
            "Discover papers around this one on OpenAlex: similar work, what it cites, or what "
            "cites it. Each row says whether it is already in the library; addable rows have a "
            "DOI and can be added with POST /references/by-doi/."
        ),
    )
    @action(detail=True, methods=["get"])
    def discover(self, request, pk=None):
        from literature import discover as discover_mod

        kind = request.query_params.get("kind", "similar")
        if kind not in discover_mod.KINDS:
            return Response({"detail": f"kind must be one of {discover_mod.KINDS}"}, status=400)
        try:
            limit = max(1, min(50, int(request.query_params.get("limit", 12))))
        except ValueError:
            limit = 12
        try:
            rows = discover_mod.discover(self.get_object(), kind, limit)
        except discover_mod.DiscoverError as exc:
            # 200 with an explanation: the pane shows *why* instead of an empty list
            return Response({"kind": kind, "results": [], "error": str(exc)})
        return Response({"kind": kind, "results": rows, "error": ""})

    @extend_schema(
        operation_id="v1_references_cite_one",
        parameters=[
            OpenApiParameter(
                "style", str, description="apa (default), mla, chicago, harvard, vancouver, ieee"
            )
        ],
        responses={200: OpenApiResponse(description="{style, label, text, html, intext}")},
        description="One formatted citation (bibliography entry + in-text form) for this reference.",
    )
    @action(detail=True, methods=["get"], url_path="cite")
    def cite_one(self, request, pk=None):
        from literature import citations

        style = request.query_params.get("style", "apa")
        if style not in citations.STYLES:
            return Response({"detail": f"style must be one of {citations.STYLES}"}, status=400)
        return Response(citations.cite(self.get_object(), style))

    @extend_schema(
        operation_id="v1_references_cite_many",
        parameters=[
            OpenApiParameter(
                "ids",
                str,
                description="Comma-separated reference ids (order matters for numbered styles)",
            ),
            OpenApiParameter(
                "style", str, description="apa (default), mla, chicago, harvard, vancouver, ieee"
            ),
        ],
        responses={200: OpenApiResponse(description="{style, label, entries[], text, html}")},
        description="A formatted bibliography for a set of references: alphabetical for author-date styles, numbered for Vancouver/IEEE.",
    )
    @action(detail=False, methods=["get"], url_path="cite")
    def cite_many(self, request):
        from literature import citations

        style = request.query_params.get("style", "apa")
        if style not in citations.STYLES:
            return Response({"detail": f"style must be one of {citations.STYLES}"}, status=400)
        wanted = [
            int(i)
            for i in (request.query_params.get("ids") or "").split(",")
            if i.strip().isdigit()
        ][:500]
        by_id = {r.pk: r for r in Reference.objects.filter(pk__in=wanted)}
        refs = [by_id[i] for i in wanted if i in by_id]
        return Response(citations.bibliography(refs, style))

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "ids",
                str,
                description="Comma-separated reference ids; omit to export the filtered list (same filters as the list endpoint)",
            ),
        ],
        responses={(200, "application/x-bibtex"): OpenApiResponse(description="BibTeX text")},
        description="Export references as BibTeX: an explicit id list, or everything matching the list filters (q, year, project, …).",
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        from django.http import HttpResponse

        from literature.library import export_bibtex, filter_references

        ids = request.query_params.get("ids")
        if ids:
            wanted = [int(i) for i in ids.split(",") if i.strip().isdigit()][:500]
            queryset = Reference.objects.filter(pk__in=wanted).order_by("bibtex_key")
        else:
            queryset = filter_references(Reference.objects.all(), request.query_params)[:500]
        response = HttpResponse(
            export_bibtex(list(queryset)), content_type="application/x-bibtex; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="atlas-library.bib"'
        return response

    @extend_schema(
        request=serializers.BulkReferenceActionSerializer,
        responses={200: OpenApiResponse(description="{action, affected, errors}")},
        description=(
            "One action over many references: link/unlink to a project, set reading status or "
            "priority within a project, delete, or find_metadata (recover metadata for stubs by "
            "DOI/arXiv id or a Crossref title search)."
        ),
    )
    @action(detail=False, methods=["post"])
    def bulk(self, request):
        from literature.library import bulk

        serializer = serializers.BulkReferenceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = bulk(
                data["ids"], data["action"], data.get("project") or None, data.get("value") or None
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @extend_schema(
        request=None,
        responses={
            200: serializers.ReferenceSerializer,
            400: OpenApiResponse(description="No confident metadata found"),
        },
        description="Recover/refresh metadata for one reference (by DOI, arXiv id, or Crossref title search).",
    )
    @action(detail=True, methods=["post"], url_path="find-metadata")
    def find_metadata(self, request, pk=None):
        from literature.library import find_metadata
        from literature.services import MetadataError

        reference = self.get_object()
        try:
            find_metadata(reference)
        except MetadataError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        reference.refresh_from_db()
        return Response(
            serializers.ReferenceSerializer(reference, context={"request": request}).data
        )

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
        request=serializers.ImportReferencesSerializer,
        responses={
            200: OpenApiResponse(
                description="Import summary: created/existing/failed + per-item results"
            )
        },
        description=(
            "Import references from dropped files (.pdf, .bib, .ris, CSL .json) and/or pasted "
            "text. PDFs are read for a DOI/arXiv id, their metadata fetched, and the file "
            "attached; papers without an id are kept as stubs flagged needs_metadata. Everything "
            "is deduplicated by DOI, arXiv id, or title+year. Optional project slug links the lot."
        ),
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="import",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def import_references(self, request):
        from literature import importers

        serializer = serializers.ImportReferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = None
        if data.get("project"):
            project = get_object_or_404(Project, slug=data["project"])
        summary = importers.ImportSummary()
        for upload in request.FILES.getlist("files"):
            summary.results.extend(
                importers.import_file(upload.name, upload.read(), project).results
            )
        text = (data.get("text") or "").strip()
        if text:
            fmt = data.get("format") or "auto"
            try:
                if fmt == "auto":
                    fmt = importers.sniff_format("pasted.txt", text.encode())
                summary.results.extend(importers.import_text(text, fmt, project).results)
            except (ValueError, KeyError) as exc:
                summary.results.append(importers.ImportResult(title="pasted text", error=str(exc)))
        if not summary.results:
            return Response({"detail": "Nothing to import: send files and/or text."}, status=400)
        return Response(summary.as_dict())

    @extend_schema(
        request=serializers.ImportZoteroSerializer,
        responses={
            200: OpenApiResponse(description="Import summary"),
            503: OpenApiResponse(description="Zotero is not reachable / its local API is off"),
        },
        description=(
            "Import the whole library from a Zotero 7 running on this machine (its local API on "
            "port 23119). Deduplicated like every other import; optional project slug to link."
        ),
    )
    @action(detail=False, methods=["post"], url_path="import-zotero")
    def import_zotero(self, request):
        from literature import importers

        serializer = serializers.ImportZoteroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = get_object_or_404(Project, slug=data["project"]) if data.get("project") else None
        try:
            summary = importers.import_from_zotero(
                project, data.get("base_url") or importers.ZOTERO_LOCAL_URL
            )
        except importers.ZoteroUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(summary.as_dict())

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
    # AUDIT #10: select_related kills the 48-query N+1 the nested serializer caused
    queryset = ProjectReference.objects.select_related("reference", "project")
    serializer_class = serializers.ProjectReferenceSerializer
    project_filter = "project__slug"

    def get_queryset(self):
        # Backlog #82: ?theme= narrows to unread papers that look like candidates for a
        # review-matrix theme, so the coverage-gap nudge can deep-link a prefilled queue.
        queryset = super().get_queryset()
        theme = self.request.query_params.get("theme", "").strip()[:120]
        if theme:
            from literature.selectors import theme_candidates

            queryset = theme_candidates(queryset, theme)
        return queryset


class LibraryTagViewSet(AtlasViewSet):
    """Library tags (global labels on references), with usage counts."""

    queryset = LibraryTag.objects.annotate(count=Count("references")).order_by("-count", "name")
    serializer_class = serializers.LibraryTagSerializer
    q_fields = ("name",)

    def perform_create(self, serializer):
        name = serializer.validated_data["name"]
        existing = LibraryTag.objects.filter(name__iexact=name.strip()).first()
        if existing:  # case-insensitive uniqueness: reuse instead of a near-duplicate
            serializer.instance = existing
            return
        serializer.save(name=" ".join(name.split()).strip())


class SavedViewViewSet(AtlasViewSet):
    """Smart views: named Library filter sets restored with one click from the rail."""

    queryset = SavedView.objects.all()
    serializer_class = serializers.SavedViewSerializer

    def perform_create(self, serializer):
        from django.db.models import Max

        top = SavedView.objects.aggregate(m=Max("position"))["m"] or 0
        serializer.save(position=top + 1)


class TodoItemViewSet(AtlasViewSet):
    """The owner's personal Today list (plain to-dos, not plan tasks)."""

    queryset = TodoItem.objects.select_related("project")
    serializer_class = serializers.TodoItemSerializer
    project_filter = "project__slug"
    q_fields = ("text",)

    def get_queryset(self):
        queryset = super().get_queryset()
        done = self.request.query_params.get("done")
        if done in ("true", "1"):
            queryset = queryset.filter(done=True)
        elif done in ("false", "0"):
            queryset = queryset.filter(done=False)
        return queryset

    def perform_create(self, serializer):
        from django.db.models import Max

        top = TodoItem.objects.aggregate(m=Max("position"))["m"] or 0
        serializer.save(position=top + 1)

    def perform_update(self, serializer):
        before = serializer.instance.done
        item = serializer.save()
        if item.done != before:
            item.mark(item.done)  # stamps/clears done_at

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description="{deleted}")},
        description="Delete every ticked-off item, leaving the open ones.",
    )
    @action(detail=False, methods=["post"], url_path="clear-done")
    def clear_done(self, request):
        deleted, _ = TodoItem.objects.filter(done=True).delete()
        return Response({"deleted": deleted})


class QuickCaptureViewSet(AtlasViewSet):
    queryset = QuickCapture.objects.all()
    serializer_class = serializers.QuickCaptureSerializer
    project_filter = "project__slug"


class HypothesisViewSet(AtlasViewSet):
    queryset = Hypothesis.objects.prefetch_related("evidence")
    serializer_class = serializers.HypothesisSerializer
    project_filter = "project__slug"
    q_fields = ("statement",)  # Backlog #100: search opt-in
    http_method_names = ["get", "head", "options"]  # read-only for now


class ExperimentEntryViewSet(AtlasViewSet):
    queryset = ExperimentEntry.objects.all()
    serializer_class = serializers.ExperimentEntrySerializer
    project_filter = "project__slug"
    http_method_names = ["get", "head", "options"]


class DatasetViewSet(AtlasViewSet):
    queryset = Dataset.objects.all()
    serializer_class = serializers.DatasetSerializer
    project_filter = "project__slug"
    q_fields = ("name", "description")  # Backlog #100: search opt-in
    http_method_names = ["get", "head", "options"]


class ProtocolViewSet(AtlasViewSet):
    # Writable (unlike the other research viewsets): protocols are a machine-friendly,
    # MCP-managed feature, so Claude can author and revise them through the API (#7).
    queryset = Protocol.objects.all()
    serializer_class = serializers.ProtocolSerializer
    project_filter = "project__slug"
    q_fields = ("title", "body")

    @extend_schema(
        request=inline_serializer("NewVersion", {"title": str, "body": str}),
        responses={201: serializers.ProtocolSerializer},
        description="Create the next version of a protocol (immutable history): clones this "
        "protocol with version+1 and parent set, applying any title/body overrides in the body.",
    )
    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, pk=None):
        changes = {k: request.data[k] for k in ("title", "body") if k in request.data}
        revision = self.get_object().new_version(**changes)
        serializer = self.get_serializer(revision)
        return Response(serializer.data, status=201)


class ManuscriptFileViewSet(AtlasViewSet):
    serializer_class = serializers.ManuscriptFileSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    project_filter = "manuscript__project__slug"

    def get_queryset(self):
        from writing.models import ManuscriptFile

        queryset = ManuscriptFile.objects.all()
        slug = self.request.query_params.get("project")
        if slug:
            queryset = queryset.filter(manuscript__project__slug=slug)
        manuscript = self.request.query_params.get("manuscript")
        if manuscript:
            queryset = queryset.filter(manuscript_id=manuscript)
        return queryset


class ManuscriptViewSet(AtlasViewSet):
    queryset = Manuscript.objects.all()
    serializer_class = serializers.ManuscriptSerializer
    project_filter = "project__slug"
    q_fields = ("title",)

    @extend_schema(
        request=None,
        responses={202: OpenApiResponse(description="Compile queued")},
        description="Queue a background LaTeX compile of the manuscript's current source. "
        "Poll compile-status for the result.",
    )
    @action(detail=True, methods=["post"])
    def compile(self, request, pk=None):
        from writing.tasks import compile_manuscript_task

        manuscript = self.get_object()
        if not manuscript.source_text().strip():
            return Response({"detail": "latex_source is empty."}, status=400)
        manuscript.compile_generation += 1
        manuscript.compile_status = Manuscript.CompileStatus.RUNNING
        manuscript.save(update_fields=["compile_generation", "compile_status", "updated_at"])
        compile_manuscript_task(manuscript.pk, manuscript.compile_generation)
        return Response({"status": "running"}, status=202)

    @extend_schema(
        responses={200: OpenApiResponse(description="Approx word/header/caption/math counts")},
        description="Approximate word count across the manuscript's text files (LaTeX detex).",
    )
    @action(detail=True, methods=["get"], url_path="word-count")
    def word_count(self, request, pk=None):
        from writing.wordcount import word_count as count

        manuscript = self.get_object()
        files = manuscript.files.filter(kind="tex")
        source = "\n".join(f.content for f in files) if files.exists() else manuscript.latex_source
        return Response(count(source))

    @extend_schema(
        responses={200: OpenApiResponse(description="Compile status, diagnostics, pdf url")},
        description="Compile state: status, parsed diagnostics [{level,file,line,message}], "
        "log tail on failure, and the PDF url when compiled. (No ETag — polling stays fresh.)",
    )
    @action(detail=True, methods=["get"], url_path="compile-status")
    def compile_status(self, request, pk=None):
        manuscript = self.get_object()
        return Response(
            {
                "status": manuscript.compile_status,
                "diagnostics": manuscript.compile_diagnostics,
                "compiled_at": manuscript.compiled_at,
                "pdf_url": manuscript.compiled_pdf.url if manuscript.compiled_pdf else None,
                "log": manuscript.compile_log[-3000:]
                if manuscript.compile_status == "failed"
                else "",
            }
        )


class PromptViewSet(AtlasViewSet):
    queryset = Prompt.objects.all()
    serializer_class = serializers.PromptSerializer
    q_fields = ("title", "body", "tags")


class NoteViewSet(AtlasViewSet):
    queryset = Note.objects.all()
    serializer_class = serializers.NoteSerializer
    project_filter = "project__slug"
    q_fields = ("title", "body")  # Backlog #100: search opt-in

    @extend_schema(
        description="Render a markdown body to sanitized HTML with [[wiki-links]] resolved "
        "against the given project — preview for the SPA editor.",
        responses={200: None},
    )
    @action(detail=False, methods=["post"])
    def preview(self, request):
        import re

        from core.templatetags.markdown_extras import markdownify
        from notes.services import WIKI_LINK_RE
        from projects.models import Project

        body = str(request.data.get("body", ""))[:50_000]
        project = Project.objects.filter(slug=request.data.get("project", "")).first()
        if project:
            by_title = {n.title.lower(): n for n in project.notes.all()}

            def replace(match: re.Match) -> str:
                title = match.group(1).strip()
                target = by_title.get(title.lower())
                if target:
                    return f"[{title}]({target.get_absolute_url()})"
                return f"*[[{title}]]*"

            body = WIKI_LINK_RE.sub(replace, body)
        return Response({"html": str(markdownify(body))})

    def perform_create(self, serializer):
        note = serializer.save()
        note_services.sync_note_links(note)

    def perform_update(self, serializer):
        note = serializer.save()
        note_services.sync_note_links(note)


@method_decorator(login_not_required, name="dispatch")
class SearchAPIView(APIView):
    authentication_classes = [APIKeyAuthentication, SessionAuthentication]

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
        description="Dashboard data: the needs-attention lead (overdue milestones, "
        "manuscript deadlines inside 14 days, untriaged inbox items), stats, active "
        "projects with progress, upcoming milestones and deadlines, inbox count.",
        responses={200: None},
    )
    def get(self, request):
        from django.urls import reverse

        from core.dashboard import dashboard_context

        data = dashboard_context()
        attention = data["attention"]
        return Response(
            {
                "stats": data["stats"],
                "inbox_count": data["inbox_count"],
                "attention": {
                    "empty": attention["empty"],
                    "overdue": [
                        {
                            "title": m.title,
                            "due_date": m.due_date.isoformat(),
                            "project": m.phase.project.name,
                            "url": reverse("plans:plan", args=[m.phase.project.slug]),
                        }
                        for m in attention["overdue"]
                    ],
                    "deadlines": [
                        {
                            "title": ms.title,
                            "deadline": ms.deadline.isoformat(),
                            "days_to_deadline": ms.days_to_deadline,
                            "project": ms.project.name,
                            "url": ms.get_absolute_url(),
                        }
                        for ms in attention["deadlines"]
                    ],
                    "inbox": [{"id": q.id, "text": q.text} for q in attention["inbox"]],
                },
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


class PetAPIView(APIView):
    """The pet's state for the SPA sidebar widget."""

    @extend_schema(description="Mochi's state: stage, mood, speech line.", responses={200: None})
    def get(self, request):
        from core.pet import pet_state

        return Response(pet_state())


class BotsAPIView(APIView):
    """Bots list with run history — the SPA automations page."""

    @extend_schema(
        description="All bots with enabled state and recent runs.", responses={200: None}
    )
    def get(self, request):
        from bots.models import Bot
        from bots.registry import BOTS

        states = {b.slug: b for b in Bot.objects.filter(slug__in=BOTS).prefetch_related("runs")}
        return Response(
            {
                "bots": [
                    {
                        "slug": slug,
                        "name": spec["name"],
                        "description": spec["description"],
                        "enabled": states[slug].enabled if slug in states else False,
                        "last_result": states[slug].last_result if slug in states else "",
                        "runs": [
                            {"ok": r.ok, "count": r.count, "started_at": r.started_at.isoformat()}
                            for r in (states[slug].runs.all()[:20] if slug in states else [])
                        ],
                    }
                    for slug, spec in BOTS.items()
                ]
            }
        )


class BotActionAPIView(APIView):
    """Toggle or run a bot from the SPA."""

    @extend_schema(
        description="action: 'toggle' or 'run'.",
        request=inline_serializer(
            "BotActionRequest",
            {"action": rf_serializers.ChoiceField(choices=["toggle", "run"])},
        ),
        responses={200: None},
    )
    def post(self, request, slug):
        from bots.models import Bot
        from bots.registry import BOTS, run_bot

        if slug not in BOTS:
            return Response({"detail": "Unknown bot."}, status=404)
        action_name = request.data.get("action")
        if action_name == "toggle":
            state, _ = Bot.objects.get_or_create(slug=slug)
            state.enabled = not state.enabled
            state.save(update_fields=["enabled", "updated_at"])
            return Response({"enabled": state.enabled})
        if action_name == "run":
            return Response({"result": run_bot(slug)})
        return Response({"detail": "action must be 'toggle' or 'run'."}, status=400)


class CommentsAPIView(APIView):
    """List + add comments on an Atlas object from the SPA (Owner idea #10)."""

    def _target(self, kind, object_id):
        from core.comments import _allowed_kinds

        model = _allowed_kinds().get(kind)
        if model is None:
            return None
        return model.objects.filter(pk=object_id).first()

    @extend_schema(
        description="Comments on a note/reference/manuscript/document.",
        request=None,
        responses={200: None},
    )
    def get(self, request, kind, object_id):
        from core.comments import comments_for

        target = self._target(kind, object_id)
        if target is None:
            return Response({"detail": "Unknown target."}, status=404)
        return Response(
            {
                "comments": [
                    {
                        "id": c.pk,
                        "body": c.body,
                        "line": c.page,  # page doubles as the editor line anchor (B6)
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in comments_for(target)
                ]
            }
        )

    @extend_schema(
        description="Add a comment (optionally anchored to a line).",
        request=inline_serializer(
            "CommentCreateRequest",
            {
                "body": rf_serializers.CharField(),
                "line": rf_serializers.IntegerField(required=False, allow_null=True),
            },
        ),
        responses={201: None},
    )
    def post(self, request, kind, object_id):
        from core.models import Comment

        target = self._target(kind, object_id)
        if target is None:
            return Response({"detail": "Unknown target."}, status=404)
        body = str(request.data.get("body", "")).strip()[:5000]
        if not body:
            return Response({"detail": "Empty comment."}, status=400)
        line = request.data.get("line")
        line = int(line) if str(line).isdigit() else None
        comment = Comment.objects.create(target=target, body=body, page=line)
        return Response(
            {
                "id": comment.pk,
                "body": comment.body,
                "line": comment.page,
                "created_at": comment.created_at.isoformat(),
            },
            status=201,
        )


class WeeklyReviewAPIView(APIView):
    """This week's research activity for the SPA review page (Owner idea #84)."""

    @extend_schema(
        parameters=[
            OpenApiParameter(name="project", type=str, required=False),
            OpenApiParameter(name="weeks_back", type=int, required=False),
        ],
        description="Papers read, notes written, milestones done, decisions, and experiments "
        "in a week window, optionally scoped to one project.",
        responses={200: None},
    )
    def get(self, request):
        from core.reviews import weekly_review
        from projects.models import Project

        project = None
        slug = request.query_params.get("project")
        if slug:
            project = get_object_or_404(Project, slug=slug)
        try:
            weeks_back = max(0, min(52, int(request.query_params.get("weeks_back", 0))))
        except ValueError:
            weeks_back = 0
        return Response(weekly_review(project=project, weeks_back=weeks_back))
