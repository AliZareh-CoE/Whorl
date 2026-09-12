import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from drf_spectacular.types import OpenApiTypes
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

from core.files import file_response
from core.models import TodoItem
from documents.models import Document, Folder, Tag
from literature import services as literature_services
from literature.models import Highlight, LibraryTag, ProjectReference, Reference, SavedView
from notes import services as note_services
from notes.models import Note, QuickCapture
from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.models import DecisionRecord, Project
from prompts.models import Prompt
from research.models import Dataset, Evidence, ExperimentEntry, Hypothesis, Protocol
from writing.models import Manuscript

from . import serializers
from .authentication import APIKeyAuthentication, QueryKeyAuthentication


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
        from core.versioning import data_version

        raw = f"{self.request.get_full_path()}|{agg['n']}|{agg['latest']}|{data_version()}"
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
        from core.versioning import data_version

        obj = self.get_object()
        updated = getattr(obj, "updated_at", None)
        etag = f'W/"{obj.pk}-{updated.timestamp()}-{data_version()}"' if updated else None
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
        from plans.focus import week_focus
        from plans.roadmap import project_roadmap
        from projects import overview as overview_extras

        project = self.get_object()
        done, total, percent = plan_selectors.project_progress(project)
        phase = plan_selectors.current_phase(project)
        health = None
        if phase is not None:
            row = next((r for r in project_roadmap(project)["phases"] if r["id"] == phase.pk), None)
            if row:
                health = {
                    "state": row["state"],
                    "label": row["label"],
                    "forecast_end": row["forecast_end"],
                    "start": row["start"],
                    "end": row["end"],
                }
        return Response(
            {
                "project": serializers.ProjectSerializer(project).data,
                "current_phase": serializers.PhaseSerializer(phase).data if phase else None,
                "health": health,
                "focus": week_focus(project),
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
                # Overview v2 (slice 1): what changed, what is open, what is due
                "week_digest": overview_extras.week_digest(project),
                "questions": overview_extras.open_questions(project),
                "manuscripts": overview_extras.manuscripts_glance(project),
                "hypotheses": overview_extras.hypotheses_summary(project),
                "themes": overview_extras.themes(project),
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
        responses={
            200: OpenApiResponse(
                description="overdue, due_this_week and next_up items (milestones and tasks with "
                "phase/milestone context and days-until-due), plus the current phase"
            )
        },
        description="This week's focus for the project: overdue first, then due within 7 days, "
        "then the next milestones of the current phase.",
    )
    @action(detail=True, methods=["get"])
    def focus(self, request, slug=None):
        from plans.focus import week_focus

        return Response(week_focus(self.get_object()))

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Phases as dated bars (real or inferred windows) with milestones, "
                "health (behind / on_track / ahead / blocked / overdue / upcoming / done / empty) "
                "and a finish forecast from the completion pace"
            )
        },
        description="Roadmap data for the plan's timeline view. Reschedule with PATCH /phases/{id}/ "
        "(target_start/target_end) and /milestones/{id}/ (due_date).",
    )
    @action(detail=True, methods=["get"])
    def roadmap(self, request, slug=None):
        from plans.roadmap import project_roadmap

        return Response(project_roadmap(self.get_object()))

    @extend_schema(
        request=serializers.PlanOutlineSerializer,
        responses={
            200: inline_serializer(
                "PlanOutlineResult",
                {
                    "markdown": rf_serializers.CharField(),
                    "applied": rf_serializers.BooleanField(),
                    "phases": rf_serializers.IntegerField(),
                    "milestones": rf_serializers.IntegerField(),
                    "tasks": rf_serializers.IntegerField(),
                    "created": rf_serializers.ListField(child=rf_serializers.CharField()),
                    "renamed": rf_serializers.ListField(child=rf_serializers.CharField()),
                    "deleted": rf_serializers.ListField(child=rf_serializers.CharField()),
                    "errors": rf_serializers.ListField(child=rf_serializers.DictField()),
                },
            )
        },
        description=(
            "GET: the plan as a Markdown outline. POST {markdown, dry_run}: make the plan match "
            "the outline (or, with dry_run, only report what would be created/renamed/deleted). "
            "Parse problems come back as 400 with per-line errors."
        ),
    )
    @action(detail=True, methods=["get", "post"])
    def outline(self, request, slug=None):
        from plans import outline as outline_mod

        project = self.get_object()
        if request.method == "GET":
            return Response({"markdown": outline_mod.plan_to_markdown(project)})
        serializer = serializers.PlanOutlineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text, dry_run = serializer.validated_data["markdown"], serializer.validated_data["dry_run"]
        try:
            summary = (
                outline_mod.preview(project, text) if dry_run else outline_mod.apply(project, text)
            )
        except outline_mod.OutlineError as exc:
            return Response({"errors": exc.errors}, status=400)
        return Response(
            {
                **summary,
                "applied": not dry_run,
                "markdown": text if dry_run else outline_mod.plan_to_markdown(project),
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
        for phase in project.phases.prefetch_related("milestones__tasks", "questions"):
            phases.append(
                {
                    "id": phase.pk,
                    "name": phase.name,
                    "order": phase.order,
                    "status": phase.status,
                    "progress": phase.progress,
                    # Plan v2 slice 4: the phase's own context, editable inline
                    "objective": phase.objective,
                    "target_start": phase.target_start,
                    "target_end": phase.target_end,
                    "questions": [
                        {"id": q.pk, "question": q.question, "status": q.status}
                        for q in phase.questions.all()
                    ],
                    "milestones": [
                        {
                            "id": m.pk,
                            "title": m.title,
                            "due_date": m.due_date,
                            "completed_at": m.completed_at,
                            "overdue": m.is_overdue,
                            "notes": m.notes,
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
                # every research question of the project, so a phase can adopt one in place
                "questions": [
                    {"id": q.pk, "question": q.question, "status": q.status}
                    for q in project.questions.all()
                ],
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
    @extend_schema(
        operation_id="v1_projects_phases_reorder",
        request=inline_serializer(
            "PhaseReorderRequest",
            {"ids": rf_serializers.ListField(child=rf_serializers.IntegerField())},
        ),
        responses={200: OpenApiResponse(description="{ordered: n}")},
        description="Put the project's phases in this order (#429): the given phase ids take "
        "positions 1..n in the order given; any phase not listed keeps its relative order after "
        "them.",
    )
    @action(detail=True, methods=["post"], url_path="phases/reorder")
    def reorder_phases(self, request, slug=None):
        from django.utils import timezone

        project = self.get_object()
        ids = request.data.get("ids") if isinstance(request.data, dict) else None
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            raise rf_serializers.ValidationError({"ids": ["Send a list of phase ids."]})
        if len(set(ids)) != len(ids):
            raise rf_serializers.ValidationError({"ids": ["An id appears twice."]})
        known = set(project.phases.values_list("pk", flat=True))
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise rf_serializers.ValidationError(
                {"ids": [f"Not this project's phase(s): {unknown}"]}
            )
        now = timezone.now()
        position = 0
        for phase_id in ids:
            position += 1
            Phase.objects.filter(pk=phase_id).update(order=position, updated_at=now)
        for phase in project.phases.exclude(pk__in=ids).order_by("order", "pk"):
            position += 1
            Phase.objects.filter(pk=phase.pk).update(order=position, updated_at=now)
        return Response({"ordered": len(ids)})

    @extend_schema(
        operation_id="v1_projects_vault",
        description="The project as a Markdown vault (#416): a zip of notes (with their "
        "[[wiki-links]]), decisions, the plan outline, the literature list + references.bib, "
        "hypotheses/experiments/datasets/protocols, manuscript source trees and the uploaded "
        "documents. Opens in Obsidian or any editor. ?documents=0 skips the uploaded files.",
        responses={200: OpenApiResponse(description="application/zip")},
    )
    @action(detail=True, methods=["get"], url_path="vault")
    def vault(self, request, slug=None):
        from django.http import HttpResponse

        from projects.vault import vault_bytes

        project = self.get_object()
        data, manifest = vault_bytes(
            project, include_documents=request.query_params.get("documents", "1") != "0"
        )
        response = HttpResponse(data, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{project.slug}-vault.zip"'
        response["X-Atlas-Vault-Files"] = str(manifest["files"])
        return response

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
        from literature.matrix import matrix as matrix_table
        from literature.selectors import theme_coverage

        return Response(
            {
                "themes": [t.name for t in themes],
                "papers": papers,
                "coverage": theme_coverage(project),
                # Matrix v2: the full table with ids, cells and per-theme coverage
                "table": matrix_table(project),
            }
        )

    @extend_schema(
        request=serializers.ReviewThemeInSerializer,
        responses={201: OpenApiResponse(description="{id, name, order}")},
        description="Add a review theme (a column of the matrix); an existing name is reused.",
    )
    @extend_schema(
        operation_id="v1_projects_review_matrix_suggest",
        description="Theme candidates that recur across the project's papers (title + abstract).",
        responses={200: None},
    )
    @action(detail=True, methods=["get"], url_path="review-matrix/suggest")
    def suggest_review_themes(self, request, slug=None):
        from literature.matrix import suggest_themes

        return Response({"suggestions": suggest_themes(self.get_object())})

    @action(detail=True, methods=["post"], url_path="review-matrix/themes")
    def add_review_theme(self, request, slug=None):
        from literature.matrix import add_theme

        serializer = serializers.ReviewThemeInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        theme = add_theme(
            self.get_object(),
            serializer.validated_data["name"],
            serializer.validated_data.get("order"),
        )
        return Response({"id": theme.pk, "name": theme.name, "order": theme.order}, status=201)

    @extend_schema(
        request=serializers.ReviewThemeInSerializer,
        responses={200: OpenApiResponse(description="{id, name, order}"), 204: None},
        description="Rename / reorder (PATCH) or delete (DELETE) a review theme.",
    )
    @action(
        detail=True, methods=["patch", "delete"], url_path=r"review-matrix/themes/(?P<theme_id>\d+)"
    )
    def review_theme(self, request, slug=None, theme_id=None):
        from literature.models import ReviewTheme

        theme = get_object_or_404(ReviewTheme, pk=theme_id, project=self.get_object())
        if request.method == "DELETE":
            theme.delete()
            return Response(status=204)
        serializer = serializers.ReviewThemeInSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "name" in serializer.validated_data:
            theme.name = serializer.validated_data["name"]
        if serializer.validated_data.get("order") is not None:
            theme.order = serializer.validated_data["order"]
        theme.save()
        return Response({"id": theme.pk, "name": theme.name, "order": theme.order})

    @extend_schema(
        request=serializers.ReviewMarkInSerializer,
        responses={200: OpenApiResponse(description="{reference_id, theme_id, marked, note}")},
        description="Set one matrix cell: mark (with an optional note — the extracted finding) or "
        "clear it. `theme` may be a name; unknown names create the theme.",
    )
    @action(detail=True, methods=["post"], url_path="review-matrix/mark")
    def set_review_mark(self, request, slug=None):
        from literature.matrix import set_mark

        serializer = serializers.ReviewMarkInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            out = set_mark(
                self.get_object(),
                data["reference"],
                data["theme"],
                marked=data["marked"],
                note=data.get("note"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(out)

    @extend_schema(
        responses={200: OpenApiResponse(description="Markdown table (text/markdown)")},
        description="The review matrix as a Markdown table.",
    )
    @action(detail=True, methods=["get"], url_path="review-matrix/markdown")
    def review_matrix_markdown(self, request, slug=None):
        from django.http import HttpResponse

        from literature.matrix import matrix_markdown

        project = self.get_object()
        response = HttpResponse(
            matrix_markdown(project), content_type="text/markdown; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="{project.slug}-review-matrix.md"'
        return response

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
        from django.http import Http404

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
        # #254/#434: uploaded files are immutable (edits create new files) — one shared policy
        # with document_download / document_preview: a day of caching, then a free 304.
        return file_response(
            request, doc.file, handle=handle, content_type=content_type, inline=True
        )


class ReferenceViewSet(AtlasViewSet):
    queryset = Reference.objects.prefetch_related("project_links__project", "tags")
    serializer_class = serializers.ReferenceSerializer
    project_filter = "project_links__project__slug"

    def get_queryset(self):
        # Library v2 workbench filters (q, year, year_min/max, entry_type, venue, has_pdf,
        # needs_metadata, project, reading_status, unfiled, sort) — see literature/library.py.
        from literature.library import filter_references

        queryset = Reference.objects.prefetch_related(
            "project_links__project", "tags"
        ).select_related("text")
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
        responses={
            200: OpenApiResponse(description="Groups of probable duplicates with a suggested keep")
        },
        description="Probable duplicate clusters in the library (same DOI or arXiv id, near-identical titles), each with the most complete record suggested as `keep`.",
    )
    @action(detail=False, methods=["get"])
    def duplicates(self, request):
        from literature.library import duplicate_groups

        return Response({"groups": duplicate_groups()})

    @extend_schema(
        request=serializers.MergeReferencesSerializer,
        responses={200: OpenApiResponse(description="{kept, merged, moved}")},
        description="Merge references: project links, tags, notes, manuscript bibliographies, evidence, citation edges, comments, and the PDF move onto `keep`; empty fields are filled in; the others are deleted.",
    )
    @action(detail=False, methods=["post"])
    def merge(self, request):
        from literature.library import merge_references

        serializer = serializers.MergeReferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not Reference.objects.filter(pk=data["keep"]).exists():
            return Response({"detail": "keep: no such reference"}, status=404)
        try:
            return Response(merge_references(data["keep"], data["merge"]))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

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
        parameters=[
            OpenApiParameter("q", str, required=True, description="Text to find inside PDFs"),
            OpenApiParameter("project", str, description="Optional project slug"),
            OpenApiParameter("limit", int, description="Max papers (default 30)"),
        ],
        responses={
            200: inline_serializer(
                "PdfTextSearchResult",
                {
                    "reference_id": rf_serializers.IntegerField(),
                    "title": rf_serializers.CharField(),
                    "year": rf_serializers.IntegerField(allow_null=True),
                    "bibtex_key": rf_serializers.CharField(),
                    "page": rf_serializers.IntegerField(allow_null=True),
                    "snippet": rf_serializers.CharField(),
                    "pages": rf_serializers.ListField(child=rf_serializers.IntegerField()),
                },
                many=True,
            )
        },
        description="Search inside the text of every attached PDF; each hit names the page.",
    )
    @action(detail=False, methods=["get"], url_path="text-search")
    def text_search(self, request):
        from literature.fulltext import search_library

        q = (request.query_params.get("q") or "").strip()[:200]
        queryset = Reference.objects.all()
        slug = request.query_params.get("project")
        if slug:
            queryset = queryset.filter(project_links__project__slug=slug)
        try:
            limit = max(1, min(int(request.query_params.get("limit", 30)), 100))
        except ValueError:
            limit = 30
        return Response(search_library(q, limit=limit, queryset=queryset))

    @extend_schema(
        operation_id="v1_references_text_search_in_pdf",
        parameters=[OpenApiParameter("q", str, required=True, description="Text to find")],
        responses={
            200: inline_serializer(
                "PdfPageHit",
                {"page": rf_serializers.IntegerField(), "snippet": rf_serializers.CharField()},
                many=True,
            )
        },
        description="Pages of this paper's PDF containing `q`, with a snippet each.",
    )
    @action(detail=True, methods=["get"], url_path="text-search")
    def text_search_one(self, request, pk=None):
        from literature.fulltext import search_pages

        q = (request.query_params.get("q") or "").strip()[:200]
        return Response(search_pages(self.get_object(), q))

    @extend_schema(
        responses={
            200: inline_serializer(
                "ReferenceTldr",
                {
                    "source": rf_serializers.CharField(),
                    "sections": rf_serializers.ListField(child=rf_serializers.DictField()),
                    "reason": rf_serializers.CharField(required=False),
                },
            )
        },
        description="tl;dr of the paper, section by section (#395): headings found in the "
        "extracted PDF text, each summarised extractively with the page it starts on; falls "
        "back to the abstract. Local, no model.",
    )
    @extend_schema(
        operation_id="v1_references_usage",
        description="Where this paper appears (#411): notes that link or cite it, decisions, "
        "experiment entries, protocols and captures that mention @key, manuscripts whose "
        "bibliography carries it, and evidence rows that point at it — each with the route "
        "to jump to.",
        responses={200: None},
    )
    @action(detail=True, methods=["get"], url_path="usage")
    def usage(self, request, pk=None):
        from literature.usage import usage_of

        return Response(usage_of(self.get_object()))

    @action(detail=True, methods=["get"], url_path="tldr")
    def tldr(self, request, pk=None):
        from literature.tldr import tldr

        return Response(tldr(self.get_object()))

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                "IndexTextResult",
                {
                    "page_count": rf_serializers.IntegerField(),
                    "char_count": rf_serializers.IntegerField(),
                    "error": rf_serializers.CharField(),
                },
            )
        },
        description="(Re)read this paper's PDF into searchable text.",
    )
    @action(detail=True, methods=["post"], url_path="index-text")
    def index_text(self, request, pk=None):
        from literature.fulltext import extract_text

        row = extract_text(self.get_object())
        if row is None:
            return Response({"detail": "No PDF attached."}, status=400)
        return Response(
            {"page_count": row.page_count, "char_count": row.char_count, "error": row.error}
        )

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                "FetchPdfResult",
                {
                    "outcome": rf_serializers.CharField(),
                    "attached": rf_serializers.BooleanField(),
                    "pdf": rf_serializers.CharField(allow_null=True),
                },
            )
        },
        description="Try to attach an open-access PDF (arXiv, then Unpaywall) to this reference.",
    )
    @action(detail=True, methods=["post"], url_path="fetch-pdf")
    def fetch_pdf(self, request, pk=None):
        from literature.oa import fetch_and_attach_pdf

        reference = self.get_object()
        outcome = fetch_and_attach_pdf(reference)
        reference.refresh_from_db()
        return Response(
            {
                "outcome": outcome,
                "attached": bool(reference.pdf),
                "pdf": reference.pdf.url if reference.pdf else None,
            }
        )

    @extend_schema(
        responses={
            200: inline_serializer(
                "HighlightsMarkdown",
                {"markdown": rf_serializers.CharField(), "count": rf_serializers.IntegerField()},
            )
        },
        description="All highlights of this paper as one Markdown block (quotes with page numbers).",
    )
    @action(detail=True, methods=["get"], url_path="highlights-markdown")
    def highlights_markdown(self, request, pk=None):
        from literature.reading import highlights_markdown

        reference = self.get_object()
        return Response(
            {"markdown": highlights_markdown(reference), "count": reference.highlights.count()}
        )

    @extend_schema(
        responses={
            200: inline_serializer(
                "ReadingNotes",
                {
                    "project_reference_id": rf_serializers.IntegerField(),
                    "project": rf_serializers.CharField(),
                    "project_name": rf_serializers.CharField(),
                    "reading_status": rf_serializers.CharField(),
                    "notes": rf_serializers.CharField(),
                },
                many=True,
            )
        },
        description="Per-project reading notes for this paper (edit via PATCH /project-references/{id}/).",
    )
    @action(detail=True, methods=["get"], url_path="reading-notes")
    def reading_notes(self, request, pk=None):
        from literature.reading import reading_notes

        return Response(reading_notes(self.get_object()))

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Reading-flow papers for a filtered library set")
        },
        description="#450: the reading flow over any Library filter (same query params as the "
        "list — q, tag, view, year…, project, reading_status). Each paper carries the project "
        "link the status applies through: the `project` filter's link, else the first unread "
        "link, else the first link; `id` is null when the paper is in no project yet.",
    )
    @action(detail=False, methods=["get"], url_path="reading-flow")
    def reading_flow(self, request):
        from literature.library import filter_references

        wanted = (request.query_params.get("project") or "").strip()
        refs = filter_references(
            Reference.objects.prefetch_related("project_links__project"), request.query_params
        )[:200]
        papers = []
        for ref in refs:
            links = list(ref.project_links.all())
            link = None
            if wanted:
                link = next((x for x in links if x.project.slug == wanted), None)
            if link is None:
                link = next((x for x in links if x.reading_status in ("to_read", "skimmed")), None)
            if link is None and links:
                link = links[0]
            papers.append(
                {
                    "id": link.pk if link else None,
                    "project": link.project.slug if link else None,
                    "reading_status": link.reading_status if link else "to_read",
                    "priority": link.priority if link else "normal",
                    "reference": {
                        "id": ref.pk,
                        "bibtex_key": ref.bibtex_key,
                        "title": ref.title,
                        "authors": ref.authors,
                        "year": ref.year,
                        "venue": ref.venue,
                        "abstract": ref.abstract,
                        "pdf": ref.pdf.url if ref.pdf else None,
                        "doi": ref.doi,
                    },
                }
            )
        return Response({"papers": papers})

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


class HighlightViewSet(AtlasViewSet):
    """Passages marked while reading a PDF (Library v2 slice 7). Filter with `?reference=<id>`;
    `?project=<slug>` narrows to one project's highlights."""

    queryset = Highlight.objects.select_related("reference", "project")
    serializer_class = serializers.HighlightSerializer
    project_filter = "project__slug"
    q_fields = ("text", "comment")

    def get_queryset(self):
        queryset = super().get_queryset()
        reference = self.request.query_params.get("reference")
        if reference and reference.isdigit():
            queryset = queryset.filter(reference_id=int(reference))
        return queryset

    def perform_create(self, serializer):
        from literature.reading import HighlightError, add_highlight

        data = serializer.validated_data
        try:
            serializer.instance = add_highlight(
                data["reference"],
                data["text"],
                page=data.get("page"),
                project=data.get("project"),
                comment=data.get("comment", ""),
                color=data.get("color", Highlight.Color.YELLOW),
                rects=data.get("rects") or [],
            )
        except HighlightError as exc:
            raise rf_serializers.ValidationError({"text": str(exc)}) from exc


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

    def perform_update(self, serializer):
        name = serializer.validated_data.get("name")
        if name is not None:
            clash = (
                LibraryTag.objects.filter(name__iexact=name)
                .exclude(pk=serializer.instance.pk)
                .first()
            )
            if clash:
                raise rf_serializers.ValidationError(
                    {"name": [f"A tag called “{clash.name}” already exists."]}
                )
        serializer.save()
        # the tag's name is serialised on every reference carrying it (#381)
        from literature.library import touch_references

        touch_references(serializer.instance.references.values_list("pk", flat=True))

    def perform_destroy(self, instance):
        from literature.library import touch_references

        pks = list(instance.references.values_list("pk", flat=True))
        super().perform_destroy(instance)
        touch_references(pks)


class SavedViewViewSet(AtlasViewSet):
    """Smart views: named Library filter sets restored with one click from the rail."""

    queryset = SavedView.objects.all()
    serializer_class = serializers.SavedViewSerializer

    def perform_create(self, serializer):
        from django.db.models import Max

        top = SavedView.objects.aggregate(m=Max("position"))["m"] or 0
        serializer.save(position=top + 1)

    @extend_schema(
        request=inline_serializer(
            "SavedViewReorder",
            {"ids": rf_serializers.ListField(child=rf_serializers.IntegerField())},
        ),
        responses={200: OpenApiResponse(description="{ordered}")},
        description="Set the rail order of the smart views: the given ids take positions 1..n; "
        "the rest follow in their current order (drag-to-reorder, #400).",
    )
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        from django.utils import timezone

        ids = request.data.get("ids") if isinstance(request.data, dict) else None
        if (
            not isinstance(ids, list)
            or not all(isinstance(i, int) for i in ids)
            or len(set(ids)) != len(ids)
        ):
            raise rf_serializers.ValidationError({"ids": ["Send a list of distinct view ids."]})
        known = set(SavedView.objects.filter(pk__in=ids).values_list("pk", flat=True))
        if any(i not in known for i in ids):
            raise rf_serializers.ValidationError({"ids": ["Unknown view id."]})
        now = timezone.now()
        position = 0
        for view_id in ids:
            position += 1
            SavedView.objects.filter(pk=view_id).update(position=position, updated_at=now)
        for view in SavedView.objects.exclude(pk__in=ids).order_by("position", "id"):
            position += 1
            SavedView.objects.filter(pk=view.pk).update(position=position, updated_at=now)
        return Response({"ordered": len(ids)})


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

    @extend_schema(
        request=inline_serializer(
            "TodoReorder",
            {"ids": rf_serializers.ListField(child=rf_serializers.IntegerField())},
        ),
        responses={200: OpenApiResponse(description="{ordered}")},
        description="Set the list order: the given item ids take positions 1..n in that "
        "order; items not listed keep their relative order after them (drag-to-reorder, #383).",
    )
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        ids = request.data.get("ids") if isinstance(request.data, dict) else None
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            raise rf_serializers.ValidationError({"ids": ["Send a list of item ids."]})
        if len(set(ids)) != len(ids):
            raise rf_serializers.ValidationError({"ids": ["An id appears twice."]})
        known = set(TodoItem.objects.filter(pk__in=ids).values_list("pk", flat=True))
        missing = [i for i in ids if i not in known]
        if missing:
            raise rf_serializers.ValidationError({"ids": [f"Unknown item id(s): {missing}"]})
        from django.utils import timezone

        # updated_at moves too: the list ETag is built from it, and a bare update() would
        # leave the SPA reading the old order back out of the browser cache (see #381).
        now = timezone.now()
        position = 0
        for item_id in ids:
            position += 1
            TodoItem.objects.filter(pk=item_id).update(position=position, updated_at=now)
        rest = TodoItem.objects.exclude(pk__in=ids).order_by("position", "id")
        for item in rest:
            position += 1
            TodoItem.objects.filter(pk=item.pk).update(position=position, updated_at=now)
        return Response({"ordered": len(ids)})


class QuickCaptureViewSet(AtlasViewSet):
    queryset = QuickCapture.objects.all()
    serializer_class = serializers.QuickCaptureSerializer
    project_filter = "project__slug"

    def get_queryset(self):
        queryset = super().get_queryset()
        processed = self.request.query_params.get("processed")
        if processed in ("true", "false"):
            queryset = queryset.filter(processed=(processed == "true"))
        run = self.request.query_params.get("run")  # #423: what one bot run filed
        if run and run.isdigit():
            queryset = queryset.filter(bot_run_id=int(run))
        return queryset

    @extend_schema(
        request=serializers.ConvertCaptureSerializer,
        responses={
            201: inline_serializer(
                "CaptureConverted",
                {
                    "kind": rf_serializers.CharField(),
                    "id": rf_serializers.IntegerField(),
                    "title": rf_serializers.CharField(),
                    "app_url": rf_serializers.CharField(),
                },
            )
        },
        description="Turn a capture into a first-class object and mark it processed: paper (by "
        "the DOI/arXiv id in the text, filed into `project` if given), note, todo (Today list), "
        "milestone (into `phase` or the project's current phase, optional `due`), decision.",
    )
    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        from literature.services import MetadataError
        from notes.capture import convert
        from plans.models import Phase

        capture = self.get_object()
        serializer = serializers.ConvertCaptureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        phase = Phase.objects.filter(pk=data.get("phase")).first() if data.get("phase") else None
        try:
            result = convert(
                capture, data["target"], data.get("project"), phase=phase, due=data.get("due")
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except MetadataError as exc:
            return Response({"detail": f"Could not fetch the paper: {exc}"}, status=502)
        return Response(result, status=201)


class HypothesisViewSet(AtlasViewSet):
    """Hypothesis ledger (Research v2): writable, with nested evidence and a suggested status."""

    queryset = Hypothesis.objects.prefetch_related(
        "evidence__reference", "evidence__note", "evidence__document"
    )
    serializer_class = serializers.HypothesisSerializer
    project_filter = "project__slug"
    q_fields = ("statement",)  # Backlog #100: search opt-in


class EvidenceViewSet(AtlasViewSet):
    """Evidence rows for hypotheses: a paper / note / document with a direction and summary."""

    queryset = Evidence.objects.select_related("reference", "note", "document", "hypothesis")
    serializer_class = serializers.EvidenceSerializer
    project_filter = "hypothesis__project__slug"
    q_fields = ("summary",)

    # Evidence changes must move the hypothesis' updated_at, or the hypothesis list/detail
    # ETag stays put and the SPA (and any polling MCP client) keeps getting 304s.
    def perform_create(self, serializer):
        _touch_hypothesis(serializer.save().hypothesis)

    def perform_update(self, serializer):
        _touch_hypothesis(serializer.save().hypothesis)

    def perform_destroy(self, instance):
        hypothesis = instance.hypothesis
        super().perform_destroy(instance)
        _touch_hypothesis(hypothesis)


def _touch_hypothesis(hypothesis) -> None:
    """Bump updated_at so hypothesis ETags change when evidence changes."""
    from django.utils import timezone

    type(hypothesis).objects.filter(pk=hypothesis.pk).update(updated_at=timezone.now())


class ExperimentEntryViewSet(AtlasViewSet):
    queryset = ExperimentEntry.objects.prefetch_related("hypotheses")
    serializer_class = serializers.ExperimentEntrySerializer
    project_filter = "project__slug"
    q_fields = ("title", "body")


class DatasetViewSet(AtlasViewSet):
    queryset = Dataset.objects.all()
    serializer_class = serializers.DatasetSerializer
    project_filter = "project__slug"
    q_fields = ("name", "description")  # Backlog #100: search opt-in


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


def _touch_manuscript(manuscript) -> None:
    """Bump updated_at so the detail ETag changes when a related row (event, bib entry) changes."""
    from django.utils import timezone

    type(manuscript).objects.filter(pk=manuscript.pk).update(updated_at=timezone.now())


def _bibliography_rows(manuscript) -> list[dict]:
    rows = []
    for link in manuscript.manuscriptreference_set.select_related("reference").order_by(
        "reference__bibtex_key"
    ):
        ref = link.reference
        rows.append(
            {
                "link_id": link.pk,
                "reference_id": ref.pk,
                "cite_key": link.cite_key,
                "bibtex_key": ref.bibtex_key,
                "title": ref.title,
                "year": ref.year,
                "authors": ", ".join(
                    a.get("family") or a.get("given") or "" for a in (ref.authors or [])[:3]
                ),
                "venue": ref.venue,
                "abstract": ref.abstract,  # #448: the rail can peek at it without leaving
            }
        )
    return rows


class ManuscriptViewSet(AtlasViewSet):
    queryset = Manuscript.objects.all().prefetch_related("word_samples")
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
        from writing.compile import source_hash
        from writing.tasks import enqueue_compile

        manuscript = self.get_object()
        if not manuscript.source_text().strip():
            return Response({"detail": "latex_source is empty."}, status=400)
        # #455: identical source is not compiled twice. A running compile of the same tree
        # absorbs the request; a successful one with the same tree is already the answer.
        data = request.data if isinstance(request.data, dict) else {}
        force = str(data.get("force", request.query_params.get("force", ""))).lower() in (
            "1",
            "true",
            "yes",
        )
        digest = source_hash(manuscript)
        if not force:
            if (
                manuscript.compile_status == Manuscript.CompileStatus.RUNNING
                and manuscript.compile_source_hash == digest
            ):
                return Response({"status": "running", "deduped": True}, status=202)
            if (
                manuscript.compile_status == Manuscript.CompileStatus.OK
                and manuscript.compiled_source_hash == digest
                and manuscript.compiled_pdf
            ):
                return Response(
                    {
                        "status": "ok",
                        "unchanged": True,
                        "compiled_at": manuscript.compiled_at,
                    }
                )
        manuscript.compile_generation += 1
        manuscript.compile_status = Manuscript.CompileStatus.RUNNING
        manuscript.compile_source_hash = digest
        manuscript.save(
            update_fields=[
                "compile_generation",
                "compile_status",
                "compile_source_hash",
                "updated_at",
            ]
        )
        enqueue_compile(manuscript.pk, manuscript.compile_generation)
        return Response({"status": "running"}, status=202)

    @extend_schema(
        request=serializers.ManuscriptReferenceInSerializer,
        responses={
            200: inline_serializer(
                "ManuscriptBibliographyEntry",
                {
                    "link_id": rf_serializers.IntegerField(),
                    "reference_id": rf_serializers.IntegerField(),
                    "cite_key": rf_serializers.CharField(),
                    "bibtex_key": rf_serializers.CharField(),
                    "title": rf_serializers.CharField(),
                    "year": rf_serializers.IntegerField(allow_null=True),
                    "authors": rf_serializers.CharField(),
                    "venue": rf_serializers.CharField(),
                },
                many=True,
            )
        },
        description="GET the manuscript's bibliography; POST {reference, cite_key_override?} adds "
        "a library paper to it (idempotent).",
    )
    @action(detail=True, methods=["get", "post"])
    def bibliography(self, request, pk=None):
        from writing.models import ManuscriptReference

        manuscript = self.get_object()
        if request.method == "POST":
            serializer = serializers.ManuscriptReferenceInSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            link, _ = ManuscriptReference.objects.get_or_create(
                manuscript=manuscript, reference=serializer.validated_data["reference"]
            )
            override = serializer.validated_data.get("cite_key_override")
            if override is not None and override != link.cite_key_override:
                link.cite_key_override = override
                link.save(update_fields=["cite_key_override"])
            _touch_manuscript(manuscript)
        return Response(_bibliography_rows(manuscript))

    @extend_schema(
        request=None,
        responses={204: None},
        description="Remove a paper from the manuscript's bibliography (the paper stays in the "
        "library).",
    )
    @action(detail=True, methods=["delete"], url_path=r"bibliography/(?P<reference_id>\d+)")
    def remove_reference(self, request, pk=None, reference_id=None):
        from writing.models import ManuscriptReference

        manuscript = self.get_object()
        ManuscriptReference.objects.filter(
            manuscript=manuscript, reference_id=reference_id
        ).delete()
        _touch_manuscript(manuscript)
        return Response(status=204)

    @extend_schema(
        responses={
            200: inline_serializer(
                "CiteCheckResult",
                {
                    "cited": rf_serializers.ListField(child=rf_serializers.CharField()),
                    "missing_from_bib": rf_serializers.ListField(child=rf_serializers.CharField()),
                    "uncited_in_bib": rf_serializers.ListField(child=rf_serializers.CharField()),
                    "matched": rf_serializers.ListField(child=rf_serializers.CharField()),
                    "resolvable": rf_serializers.DictField(child=rf_serializers.IntegerField()),
                    "tex_files": rf_serializers.IntegerField(),
                },
            )
        },
        description="\\cite keys in every .tex file (or latex_source) against the bibliography: "
        "missing keys, uncited entries, and `resolvable` — missing keys that match a library "
        "paper's bibtex_key, with its id, so they can be added in one call.",
    )
    @action(detail=True, methods=["get"], url_path="cite-check")
    def cite_check(self, request, pk=None):
        from writing.services import check_citations

        manuscript = self.get_object()
        files = list(manuscript.files.filter(kind="tex"))
        tex = "\n".join(f.content for f in files) if files else manuscript.latex_source
        result = check_citations(manuscript, tex)
        resolvable = {
            r.bibtex_key: r.pk
            for r in Reference.objects.filter(bibtex_key__in=result["missing_from_bib"])
        }
        return Response({**result, "resolvable": resolvable, "tex_files": len(files)})

    @extend_schema(
        responses={200: OpenApiResponse(description="BibTeX (text/x-bibtex)")},
        description="The manuscript bibliography as a .bib file, cite-key overrides applied.",
    )
    @action(detail=True, methods=["get"])
    def bib(self, request, pk=None):
        from django.http import HttpResponse

        from writing.services import export_manuscript_bib

        manuscript = self.get_object()
        response = HttpResponse(export_manuscript_bib(manuscript), content_type="text/x-bibtex")
        response["Content-Disposition"] = f'attachment; filename="manuscript-{manuscript.pk}.bib"'
        return response

    @extend_schema(
        request=serializers.SubmissionEventInSerializer,
        responses={201: serializers.SubmissionEventSerializer},
        description="Log a submission event (submitted, reviews received, accepted, …).",
    )
    @action(detail=True, methods=["post"])
    def events(self, request, pk=None):
        from writing.models import SubmissionEvent

        manuscript = self.get_object()
        serializer = serializers.SubmissionEventInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = SubmissionEvent.objects.create(manuscript=manuscript, **serializer.validated_data)
        _touch_manuscript(manuscript)
        return Response(serializers.SubmissionEventSerializer(event).data, status=201)

    @extend_schema(
        request=serializers.ReviewsInSerializer,
        responses={
            201: inline_serializer(
                "ReviewsLogged",
                {
                    "event": serializers.SubmissionEventSerializer(),
                    "note": rf_serializers.DictField(),
                    "points": rf_serializers.IntegerField(),
                },
            )
        },
        description="Log received reviews: creates the reviews_received event and a point-by-point "
        "'Response to reviewers' note (one checkbox per reviewer point) in the project.",
    )
    @action(detail=True, methods=["post"])
    def reviews(self, request, pk=None):
        from writing.reviews import log_reviews

        manuscript = self.get_object()
        serializer = serializers.ReviewsInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        event, note, points = log_reviews(
            manuscript, data["text"], received=data.get("date"), notes=data.get("notes", "")
        )
        _touch_manuscript(manuscript)
        return Response(
            {
                "event": serializers.SubmissionEventSerializer(event).data,
                "note": {
                    "id": note.pk,
                    "title": note.title,
                    "app_url": f"/projects/{manuscript.project.slug}/notes/{note.pk}",
                },
                "points": len(points),
            },
            status=201,
        )

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="{progress: {note_id, title, done, total, percent, app_url} | null} "
                "for the newest response note"
            )
        },
        description="How many reviewer points have a final response (ticked in the note).",
    )
    @action(detail=True, methods=["get"], url_path="response-progress")
    def response_progress(self, request, pk=None):
        from writing.reviews import response_progress

        return Response({"progress": response_progress(self.get_object())})

    @extend_schema(request=None, responses={204: None}, description="Delete a submission event.")
    @action(detail=True, methods=["delete"], url_path=r"events/(?P<event_id>\d+)")
    def remove_event(self, request, pk=None, event_id=None):
        from writing.models import SubmissionEvent

        manuscript = self.get_object()
        SubmissionEvent.objects.filter(manuscript=manuscript, pk=event_id).delete()
        _touch_manuscript(manuscript)
        return Response(status=204)

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="{venue, limits, usage, items[{key,label,used,limit,ratio,state}], "
                "over[], summary} — usage vs the venue limits (set via PATCH venue_limits)"
            )
        },
        description="The venue budget: words, abstract words, figures, tables, references and "
        "(after a compile) pages, each against the limit stored in `venue_limits`.",
    )
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "network",
                str,
                description="1 to also resolve DOIs and check retractions (slow, needs network)",
            )
        ],
        responses={200: None},
        description="Submission pre-flight (#466): every readiness check from real data — "
        "compiled PDF up to date, compile errors, undefined references, cite keys vs the "
        "bibliography, bibliography hygiene, venue limits, figure files, leftover TODO markers, "
        "the .bbl for arXiv, venue/deadline/abstract — each ok/warn/fail/skip with a detail and "
        "a fix pointer. `ready` is true when nothing fails.",
    )
    @extend_schema(
        request=inline_serializer(
            "SubmitManuscript",
            {
                "force": rf_serializers.BooleanField(required=False),
                "date": rf_serializers.DateField(required=False),
                "notes": rf_serializers.CharField(required=False, allow_blank=True),
            },
        ),
        responses={200: None, 409: None},
        description="Submit through the pre-flight (#469): runs the offline readiness checks; a "
        "blocking row (anything failing except a passed deadline) answers 409 with the full "
        "report unless `force` is true. Otherwise the status becomes submitted (from revision: "
        "under_review with a revision_submitted event), a submission event is logged with the "
        "readiness note, and the manuscript, the event and the report come back.",
    )
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        from writing.services import SubmissionBlocked, submit_manuscript

        data = request.data if isinstance(request.data, dict) else {}
        date = data.get("date") or None
        if date:
            try:
                date = datetime.date.fromisoformat(str(date))
            except ValueError:
                return Response({"detail": "date must be YYYY-MM-DD."}, status=400)
        try:
            out = submit_manuscript(
                self.get_object(),
                force=bool(data.get("force")),
                date=date,
                notes=str(data.get("notes") or ""),
            )
        except SubmissionBlocked as blocked:
            return Response(
                {"detail": blocked.preflight["summary"], "preflight": blocked.preflight},
                status=409,
            )
        return Response(
            {
                "manuscript": serializers.ManuscriptSerializer(
                    out["manuscript"], context={"request": request}
                ).data,
                "event": serializers.SubmissionEventSerializer(out["event"]).data,
                "preflight": out["preflight"],
                "forced": out["forced"],
            }
        )

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Style lint findings: file, line, col, rule, level (error/warning), "
                "message and a suggested fix where one is obvious; counts and the rule catalogue."
            )
        },
        description="Static LaTeX style lint over the manuscript's .tex files — the mistakes a "
        "compile never reports (unescaped %, \\label before \\caption, undefined/duplicate "
        "labels, plain spaces before \\ref and units, straight quotes, ..., $$, \\\\ in prose).",
    )
    @action(detail=True, methods=["get"])
    def lint(self, request, pk=None):
        from writing.lint import lint_manuscript

        return Response(lint_manuscript(self.get_object()))

    @action(detail=True, methods=["get"])
    def preflight(self, request, pk=None):
        from writing.preflight import preflight

        return Response(
            preflight(self.get_object(), network=request.query_params.get("network") == "1")
        )

    @action(detail=True, methods=["get"])
    def budget(self, request, pk=None):
        from writing.budget import budget

        return Response(budget(self.get_object()))

    @extend_schema(
        responses={200: OpenApiResponse(description="Approx word/header/caption/math counts")},
        description="Approximate word count across the manuscript's text files (LaTeX detex).",
    )
    @action(detail=True, methods=["get"], url_path="word-count")
    def word_count(self, request, pk=None):
        from writing.progress import progress, record_words
        from writing.wordcount import word_count as count

        manuscript = self.get_object()
        files = manuscript.files.filter(kind="tex")
        source = "\n".join(f.content for f in files) if files.exists() else manuscript.latex_source
        counts = count(source)
        record_words(manuscript, counts["words"])  # #413: opening the Studio logs today
        summary = progress(manuscript, days=7)
        counts.update(
            today_delta=summary["today_delta"],
            compiles_today=summary["compiles"]["today"],  # #460
            streak=summary["streak"],
            week_delta=summary["week_delta"],
        )
        return Response(counts)

    @extend_schema(
        request=inline_serializer(
            "ManuscriptDuplicate",
            {
                "title": rf_serializers.CharField(required=False),
                "project": rf_serializers.CharField(required=False),
                "bibliography": rf_serializers.BooleanField(required=False),
            },
        ),
        responses={201: serializers.ManuscriptSerializer},
        description="Duplicate this manuscript (#446): every source file and asset, the venue "
        "limits and (unless bibliography=false) the bibliography links go into a fresh "
        "manuscript in idea status — in the same project, or in `project` (a slug). Compile "
        "state, revisions, comments and submission events stay with the original.",
    )
    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request, pk=None):
        from projects.models import Project
        from writing.services import duplicate_manuscript

        source = self.get_object()
        data = request.data if isinstance(request.data, dict) else {}
        target = None
        if data.get("project"):
            target = Project.objects.filter(slug=data["project"]).first()
            if target is None:
                raise rf_serializers.ValidationError({"project": ["No project with that slug."]})
        copy = duplicate_manuscript(
            source,
            title=str(data.get("title") or "").strip(),
            project=target,
            bibliography=data.get("bibliography", True) is not False,
        )
        return Response(self.get_serializer(copy).data, status=201)

    @extend_schema(
        request=inline_serializer(
            "RelatedWorkDraft",
            {
                "path": rf_serializers.CharField(required=False),
                "overwrite": rf_serializers.BooleanField(required=False),
            },
        ),
        responses={
            200: OpenApiResponse(
                description="{path, file_id, themes, cited, linked_new, input_line, tex}"
            )
        },
        description="Draft a LaTeX `Related work` section from the project's review matrix (#437): "
        "one subsection per theme, each cell finding a sentence ending in \\citep{key}, written to "
        "`sections/related-work.tex` (or `path`) in this manuscript's source tree; every cited paper "
        "is added to the manuscript's bibliography. Refuses to replace an existing file unless "
        "`overwrite` is true.",
    )
    @action(detail=True, methods=["post"], url_path="related-work")
    def related_work(self, request, pk=None):
        from literature.selectors import related_work_latex
        from writing.models import ManuscriptFile, ManuscriptReference

        manuscript = self.get_object()
        data = request.data if isinstance(request.data, dict) else {}
        path = (data.get("path") or "sections/related-work.tex").strip().lstrip("/")
        if not path.endswith(".tex"):
            raise rf_serializers.ValidationError({"path": ["Must end in .tex."]})
        overwrite = bool(data.get("overwrite"))
        existing = ManuscriptFile.objects.filter(manuscript=manuscript, path=path).first()
        if existing is not None and not overwrite:
            return Response(
                {
                    "detail": f"{path} already exists — send overwrite=true to replace it.",
                    "path": path,
                },
                status=409,
            )
        tex, cited = related_work_latex(manuscript.project, manuscript)
        linked_new = 0
        for ref in cited:
            _, created = ManuscriptReference.objects.get_or_create(
                manuscript=manuscript, reference=ref
            )
            linked_new += int(created)
        if existing is None:
            existing = ManuscriptFile.objects.create(
                manuscript=manuscript, path=path, content=tex, kind="tex"
            )
        else:
            existing.content = tex
            existing.save(update_fields=["content", "updated_at"])
        _touch_manuscript(manuscript)
        return Response(
            {
                "path": path,
                "file_id": existing.pk,
                "themes": manuscript.project.review_themes.count(),
                "cited": len(cited),
                "linked_new": linked_new,
                "input_line": "\\input{" + path[:-4] + "}",
                "tex": tex,
            }
        )

    @extend_schema(
        operation_id="v1_manuscripts_comments",
        description="Every line-anchored comment across the manuscript's source files (#414): "
        "file id + path, line (null = general), body, created_at — newest first.",
        responses={200: None},
    )
    @action(detail=True, methods=["get"], url_path="comments")
    def comments(self, request, pk=None):
        from django.contrib.contenttypes.models import ContentType

        from core.models import Comment
        from writing.models import ManuscriptFile

        manuscript = self.get_object()
        files = {f.pk: f.path for f in manuscript.files.exclude(kind="asset")}
        ct = ContentType.objects.get_for_model(ManuscriptFile)
        rows = Comment.objects.filter(content_type=ct, object_id__in=files.keys()).order_by(
            "-created_at"
        )
        return Response(
            {
                "comments": [
                    {
                        "id": c.pk,
                        "file": c.object_id,
                        "path": files[c.object_id],
                        "line": c.page,
                        "body": c.body,
                        "created_at": c.created_at.isoformat(),
                        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
                    }
                    for c in rows
                ]
            }
        )

    @extend_schema(
        operation_id="v1_manuscripts_progress",
        description="Writing progress (#413): words per day for the last 30 days with deltas, "
        "today's delta, this week's total, the streak of consecutive writing days and the "
        "best day.",
        responses={200: None},
    )
    @action(detail=True, methods=["get"], url_path="progress")
    def writing_progress(self, request, pk=None):
        from writing.progress import progress

        days = min(max(int(request.query_params.get("days", 30) or 30), 7), 365)
        return Response(progress(self.get_object(), days=days))

    @extend_schema(
        responses={200: OpenApiResponse(description="Compile status, diagnostics, pdf url")},
        description="Compile state: status, parsed diagnostics [{level,file,line,message}], "
        "log tail on failure, and the PDF url when compiled. (No ETag — polling stays fresh.)",
    )
    @extend_schema(
        responses={200: OpenApiResponse(description="SyncTeX map of the last good compile")},
        description="SyncTeX map (#378): {files: [paths], pages: {n: [[file, line, x, y, w, h], "
        "…]}} in PDF points from the top-left, for PDF-click ↔ source-line in the studio. "
        "Empty when the manuscript has not compiled.",
    )
    @action(detail=True, methods=["get"], url_path="synctex")
    def synctex(self, request, pk=None):
        manuscript = self.get_object()
        return Response(manuscript.synctex or {"files": [], "pages": {}})

    @action(detail=True, methods=["get"], url_path="compile-status")
    def compile_status(self, request, pk=None):
        manuscript = self.get_object()
        return Response(
            {
                "status": manuscript.compile_status,
                "synctex": bool(manuscript.synctex),
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
        from core.rendering import render_body
        from projects.models import Project

        body = str(request.data.get("body", ""))[:50_000]
        project = Project.objects.filter(slug=request.data.get("project", "")).first()
        return Response({"html": render_body(body, project)})

    def perform_create(self, serializer):
        note = serializer.save()
        note_services.sync_note_links(note)
        note_services.sync_note_references(note)

    def perform_update(self, serializer):
        note = serializer.save()
        note_services.sync_note_links(note)
        note_services.sync_note_references(note)

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="outgoing, backlinks, references, unresolved [[titles]], "
                "unresolved @keys, and unlinked mentions of this note"
            )
        },
        description="The link panel of one note.",
    )
    @action(detail=True, methods=["get"])
    def links(self, request, pk=None):
        return Response(note_services.note_links(self.get_object()))

    @extend_schema(
        parameters=[
            OpenApiParameter("project", str, required=True),
            OpenApiParameter("q", str, description="Prefix typed so far"),
            OpenApiParameter("kind", str, description="note (default) or reference"),
        ],
        responses={
            200: inline_serializer(
                "NoteSuggestion",
                {
                    "id": rf_serializers.IntegerField(),
                    "label": rf_serializers.CharField(),
                    "sublabel": rf_serializers.CharField(),
                },
                many=True,
            )
        },
        description="Autocomplete for [[note titles]] and @cite-keys while writing.",
    )
    @action(detail=False, methods=["get"])
    def suggest(self, request):
        project = get_object_or_404(Project, slug=request.query_params.get("project", ""))
        kind = "reference" if request.query_params.get("kind") == "reference" else "note"
        return Response(
            note_services.suggest(project, request.query_params.get("q", "")[:100], kind)
        )

    @extend_schema(
        responses={
            200: inline_serializer(
                "NoteTemplate",
                {
                    "kind": rf_serializers.CharField(),
                    "label": rf_serializers.CharField(),
                    "description": rf_serializers.CharField(),
                },
                many=True,
            )
        },
        description="Available note templates.",
    )
    @action(detail=False, methods=["get"])
    def templates(self, request):
        from notes.templates import TEMPLATES

        return Response([{"kind": k, **v} for k, v in TEMPLATES.items()])

    @extend_schema(
        request=serializers.NoteFromTemplateSerializer,
        responses={201: serializers.NoteSerializer},
        description="Create a note from a template: literature (needs `reference`; pulls the "
        "paper's metadata, @key and highlights), daily (this week's focus as checkboxes; one per "
        "day), meeting, experiment, blank.",
    )
    @action(detail=False, methods=["post"], url_path="from-template")
    def from_template(self, request):
        from notes.templates import create_from_template

        serializer = serializers.NoteFromTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            note = create_from_template(
                data["kind"], data["project"], reference=data.get("reference")
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(serializers.NoteSerializer(note).data, status=201)

    @extend_schema(
        parameters=[OpenApiParameter("style", str, description="apa (default) … ieee")],
        responses={
            200: inline_serializer(
                "NoteExport",
                {
                    "markdown": rf_serializers.CharField(),
                    "style": rf_serializers.CharField(),
                    "references": rf_serializers.IntegerField(),
                },
            )
        },
        description="The note as portable Markdown with a formatted bibliography of its references.",
    )
    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        from notes.templates import export_note

        return Response(export_note(self.get_object(), request.query_params.get("style", "apa")))

    @extend_schema(
        parameters=[OpenApiParameter("project", str, required=True)],
        responses={
            200: inline_serializer(
                "UnwrittenNotes",
                {"titles": rf_serializers.ListField(child=rf_serializers.CharField())},
            )
        },
        description="[[Titles]] linked somewhere in the project that have no note yet.",
    )
    @action(detail=False, methods=["get"])
    def unwritten(self, request):
        project = get_object_or_404(Project, slug=request.query_params.get("project", ""))
        return Response({"titles": note_services.unwritten_note_titles(project)})


@method_decorator(login_not_required, name="dispatch")
class SearchAPIView(APIView):
    authentication_classes = [APIKeyAuthentication, SessionAuthentication]

    @extend_schema(
        parameters=[OpenApiParameter(name="q", type=str, required=True, description="Search text")],
        responses={
            200: OpenApiResponse(
                description="Ranked results: {type, id, label, project, project_name, url, "
                "app_url, snippet, page, where, meta} — snippet is the matching passage "
                "(for papers: from the PDF text with its page when the hit is inside the PDF)"
            )
        },
        description="Global full-text search across projects, references (title, abstract and "
        "PDF text), notes, documents, decisions, plans, hypotheses, experiments, questions, "
        "protocols, datasets and inbox captures.",
    )
    def get(self, request):
        from core.search import describe, search_all

        q = request.query_params.get("q", "")
        results = []
        for result in search_all(q):
            obj = result["object"]
            results.append(
                {
                    "type": result["type"],
                    "id": obj.pk,
                    "label": str(obj),
                    "project": result["project"].slug if result["project"] else None,
                    "project_name": result["project"].name if result["project"] else None,
                    "url": obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else None,
                    # Search v2: why it matched and where to open it in the app
                    **describe(result, q),
                }
            )
        return Response({"query": q, "results": results})


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

        from core.backups import backup_status
        from core.dashboard import dashboard_context, project_health, week_everywhere
        from core.models import TodoItem

        data = dashboard_context()
        attention = data["attention"]
        health = project_health(data["active"])
        return Response(
            {
                "stats": data["stats"],
                "inbox_count": data["inbox_count"],
                # Dashboard v2 slice 1: this week everywhere, per-project health, heatmap, today
                "week": week_everywhere(),
                "todos_open": TodoItem.objects.filter(done=False).count(),
                # backlog #300: the top of the Today list, tickable from the hero
                "todos": [
                    {
                        "id": t.id,
                        "text": t.text,
                        "due_at": t.due_at,  # #431
                        "project": t.project.slug if t.project_id else None,
                    }
                    for t in TodoItem.objects.filter(done=False)
                    .select_related("project")
                    .order_by("position", "id")[:4]
                ],
                "heatmap": [
                    [
                        {"date": c["date"].isoformat(), "count": c["count"], "level": c["level"]}
                        for c in week
                    ]
                    for week in data["heatmap"]
                ],
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
                    "backup": backup_status(),  # #424: a calm nudge when it has been a while
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
                        "health": health.get(row["project"].slug),
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

    @extend_schema(
        description="Mochi's state: stage, mood, speech lines, stats, streak, achievements.",
        responses={200: None},
    )
    def get(self, request):
        from core.pet import pet_state

        return Response(pet_state())

    @extend_schema(
        operation_id="v1_pet_rename",
        description='Rename the pet: {"name": "..."} (1-40 characters).',
        request=inline_serializer("PetRename", {"name": rf_serializers.CharField(max_length=40)}),
        responses={200: None},
    )
    def post(self, request):
        from core.achievements import set_souls_mode
        from core.pet import pet_state, rename_pet

        if "souls_mode" in request.data:
            set_souls_mode(bool(request.data.get("souls_mode")))
            if "name" not in request.data:
                return Response(pet_state())
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"name": ["A name is required."]}, status=400)
        rename_pet(name)
        return Response(pet_state())


class AchievementsAPIView(APIView):
    """The achievements ledger (owner, 2026-09-07): every achievement with tier, progress and
    unlock time, the score and rank, the souls counters."""

    @extend_schema(
        operation_id="v1_achievements",
        description="All achievements with tier (fun/steady/hard/souls), progress, unlock "
        "time; score, rank, next-up suggestions and the souls-mode counters.",
        responses={200: None},
    )
    def get(self, request):
        from core.achievements import ledger

        return Response(ledger())


class DemoAPIView(APIView):
    """First run (2026-09-06): an empty Atlas offers to load the demo project so every page has
    something to show. GET counts projects; POST seeds the demo (idempotent, single user)."""

    @extend_schema(
        operation_id="v1_demo_status", description="How many projects exist.", responses={200: None}
    )
    def get(self, request):
        return Response({"projects": Project.objects.count()})

    @extend_schema(
        operation_id="v1_demo_load",
        description="Create the demo research project (safe to repeat).",
        request=None,
        responses={200: None},
    )
    def post(self, request):
        from django.core.management import call_command

        call_command("seed_demo", verbosity=0)
        project = Project.objects.order_by("pk").first()
        return Response(
            {"project": project.slug if project else None, "projects": Project.objects.count()}
        )


class CalendarFeedView(APIView):
    """Milestones and manuscript deadlines as an iCalendar feed (subscribe by URL)."""

    authentication_classes = [QueryKeyAuthentication, APIKeyAuthentication, SessionAuthentication]

    @extend_schema(
        operation_id="v1_calendar_ics",
        description="VCALENDAR of milestones + manuscript deadlines; ?project=<slug> narrows, "
        "?key=<api key> authenticates calendar apps that cannot send headers.",
        responses={(200, "text/calendar"): OpenApiTypes.STR},
    )
    def get(self, request):
        from django.http import HttpResponse

        from core.calendar import build_ics

        projects = Project.objects.exclude(status=Project.Status.ARCHIVED)
        slug = request.query_params.get("project")
        if slug:
            projects = projects.filter(slug=slug)
        body = build_ics(projects, name=f"Atlas — {slug}" if slug else "Atlas — deadlines")
        response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = 'inline; filename="atlas.ics"'
        response["Cache-Control"] = "no-store"
        return response


class BackupView(APIView):
    """Everything as one zip: the database (consistent copy) and the media folder."""

    @extend_schema(
        operation_id="v1_backup_zip",
        description="Download a backup zip (database + media). Restore notes are inside.",
        responses={(200, "application/zip"): OpenApiTypes.BINARY},
    )
    def get(self, request):
        import io
        from datetime import UTC, datetime

        from django.http import HttpResponse

        from core.backup import build_backup
        from core.models import BackupRecord

        buf = io.BytesIO()
        manifest = build_backup(buf)
        data = buf.getvalue()
        BackupRecord.objects.create(  # #424: the app remembers when it was last backed up
            size_bytes=len(data),
            media_files=manifest.get("media_files", 0),
            database=manifest.get("database", ""),
        )
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
        response = HttpResponse(data, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="atlas-backup-{stamp}.zip"'
        response["Cache-Control"] = "no-store"
        return response


class SnapshotsAPIView(APIView):
    """Automatic snapshots (#462): the zips Atlas keeps in the data folder on its own."""

    @extend_schema(
        operation_id="v1_snapshots",
        description="Automatic snapshot status: the backups folder, how many are kept, the "
        "newest one, whether the desktop scheduler is running, the last failure — plus the "
        "list of snapshot files on disk (newest first).",
        responses={200: None},
    )
    def get(self, request):
        from core.snapshots import list_snapshots, snapshot_status

        status = snapshot_status()
        status["files"] = [
            {**row, "created_at": row["created_at"].isoformat()} for row in list_snapshots()
        ]
        return Response(status)

    @extend_schema(
        operation_id="v1_snapshot_now",
        description="Write a snapshot now (database + media as one zip in the backups folder) "
        "and rotate the old ones. Answers the file written and the names removed.",
        request=None,
        responses={201: None},
    )
    def post(self, request):
        from core.snapshots import snapshot_status, take_snapshot

        try:
            result = take_snapshot(kind="manual")
        except OSError as exc:
            return Response({"detail": f"Couldn't write the snapshot: {exc}"}, status=507)
        return Response(
            {
                "path": result["path"],
                "size_bytes": result["size_bytes"],
                "removed": result["removed"],
                "status": snapshot_status(),
            },
            status=201,
        )


class RestoreAPIView(APIView):
    """Restore from a backup zip (2026-09-07, #376): staged now, applied at the next launch."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        operation_id="v1_restore_status",
        description="The staged restore (if any) and the last restore's outcome.",
        responses={200: None},
    )
    def get(self, request):
        from core.backup import restore_status

        return Response(restore_status())

    @extend_schema(
        operation_id="v1_restore_stage",
        description="Upload a backup zip (multipart `file`) to stage it, or name one of the "
        'automatic snapshots on disk (`{"snapshot": "atlas-snapshot-….zip"}`, see '
        "/snapshots/). The desktop app applies it at the next launch (Diagnostics offers the "
        "restart); a server runs `manage.py restore_backup` while stopped.",
        request=None,
        responses={202: None, 400: None},
    )
    def post(self, request):
        from core.backup import RestoreError, stage_restore

        uploaded = request.FILES.get("file")
        name = request.data.get("snapshot") if hasattr(request.data, "get") else None
        if uploaded is None and name:
            # #463: restore one of the automatic snapshots on disk — by name, never by path
            from core.snapshots import list_snapshots

            match = next((row for row in list_snapshots() if row["name"] == name), None)
            if match is None:
                return Response({"detail": "No snapshot by that name."}, status=404)
            with open(match["path"], "rb") as fh:
                try:
                    manifest = stage_restore(fh)
                except RestoreError as exc:
                    return Response({"detail": str(exc)}, status=400)
            manifest["snapshot"] = name
            return Response({"staged": manifest}, status=202)
        if uploaded is None:
            return Response(
                {"detail": "Attach the backup zip as `file`, or name a `snapshot`."}, status=400
            )
        try:
            manifest = stage_restore(uploaded)
        except RestoreError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"staged": manifest}, status=202)

    @extend_schema(
        operation_id="v1_restore_cancel",
        description="Discard the staged restore.",
        responses={204: None},
    )
    def delete(self, request):
        from core.backup import cancel_restore

        cancel_restore()
        return Response(status=204)


class DiagnosticsAPIView(APIView):
    """Why didn't it work? Version, paths, engine, update feed, last compile failure, log tail."""

    @extend_schema(
        operation_id="v1_diagnostics",
        description="Diagnostics report; ?network=1 also probes the update feed.",
        responses={200: None},
    )
    def get(self, request):
        from core.diagnostics import as_text, collect

        report = collect(check_network=request.query_params.get("network") == "1")
        report["text"] = as_text(report)
        return Response(report)


class WatchFolderAPIView(APIView):
    """Watched folder (#406): a folder on this machine whose new PDFs land in the library."""

    @extend_schema(
        operation_id="v1_watch_folder",
        description="The watched folder: dir, project, enabled, whether the watcher runs, the last scan.",
        responses={200: None},
    )
    def get(self, request):
        from literature.watch import status

        return Response(status())

    @extend_schema(
        operation_id="v1_watch_folder_set",
        description="Set the watched folder: {dir, project (slug or null), enabled}. Starts or stops the watcher.",
        request=inline_serializer(
            "WatchFolderConfig",
            {
                "dir": rf_serializers.CharField(allow_blank=True),
                "project": rf_serializers.CharField(
                    required=False, allow_null=True, allow_blank=True
                ),
                "enabled": rf_serializers.BooleanField(required=False),
            },
        ),
        responses={200: None},
    )
    def post(self, request):
        from literature.watch import save_config, start_watcher, status, stop_watcher

        data = request.data if isinstance(request.data, dict) else {}
        try:
            config = save_config(
                str(data.get("dir") or ""),
                (data.get("project") or None) or None,
                bool(data.get("enabled", True)),
            )
        except ValueError as exc:
            raise rf_serializers.ValidationError({"dir": [str(exc)]}) from exc
        if config["enabled"]:
            start_watcher()
        else:
            stop_watcher()
        return Response(status())


class WatchFolderScanAPIView(APIView):
    """Scan the watched folder now (#406)."""

    @extend_schema(
        operation_id="v1_watch_folder_scan",
        description="Import the folder's new PDFs right now and return the scan summary.",
        request=None,
        responses={200: None},
    )
    def post(self, request):
        from literature.watch import scan_once

        return Response(scan_once())


class FeedTokenAPIView(APIView):
    """The calendar feed token (#401): the read-only secret in the .ics subscription URL."""

    @extend_schema(
        operation_id="v1_feed_token",
        description="The current calendar feed token and the subscription URL that carries it.",
        responses={200: None},
    )
    def get(self, request):
        from core.models import FeedToken

        token = FeedToken.current()
        base = f"{request.scheme}://{request.get_host()}".rstrip("/")
        return Response({"token": token, "url": f"{base}/api/v1/calendar.ics?key={token}"})

    @extend_schema(
        operation_id="v1_feed_token_rotate",
        description="Rotate the calendar feed token: every URL copied before stops working.",
        request=None,
        responses={200: None},
    )
    def post(self, request):
        from core.models import FeedToken

        token = FeedToken.rotate()
        base = f"{request.scheme}://{request.get_host()}".rstrip("/")
        return Response(
            {"token": token, "url": f"{base}/api/v1/calendar.ics?key={token}", "rotated": True}
        )


class AccessEventsAPIView(APIView):
    """The access log (#399): recent logins, lockouts and rejected API keys, with a summary."""

    @extend_schema(
        operation_id="v1_access_events",
        description="Recent access events (logins, failed logins, lockouts, rejected API keys) "
        "and a 7-day summary. ?limit=<n> (default 50, max 200).",
        responses={200: None},
    )
    def get(self, request):
        from core.access import recent, summary

        try:
            limit = max(1, min(200, int(request.query_params.get("limit", 50))))
        except ValueError:
            limit = 50
        return Response({"events": recent(limit), "summary": summary()})


class ClientErrorAPIView(APIView):
    """Front-end crash reports (#382): the SPA's boot watchdog, error boundary and global
    error handlers post here; each lands in the server log and the Diagnostics report."""

    @extend_schema(
        operation_id="v1_client_error",
        description="Record a front-end error report (where, url, errors[], version). "
        "It is written to the server log and kept for the Diagnostics report.",
        request=None,
        responses={204: None},
    )
    def post(self, request):
        from core.client_errors import record

        payload = request.data if isinstance(request.data, dict) else {}
        record(payload, user_agent=request.headers.get("User-Agent", ""))
        return Response(status=204)


class LatexWarmupAPIView(APIView):
    """Warm the LaTeX engine's bundle cache in the background (Diagnostics page)."""

    @extend_schema(
        operation_id="v1_latex_warmup_status",
        description="Engine cache state and the last warm-up outcome.",
        responses={200: None},
    )
    def get(self, request):
        from writing.warmup import status

        return Response(status())

    @extend_schema(
        operation_id="v1_latex_warmup",
        description="Start a background warm-up compile that downloads the common TeX packages "
        "so the first real compile is fast. Poll GET for progress.",
        request=None,
        responses={202: None},
    )
    def post(self, request):
        from writing.warmup import start_warm_up

        return Response(start_warm_up(), status=202)


class ConnectAPIView(APIView):
    """Connect Claude Code (SPA page): the exact `claude mcp add` line for this install, the
    MCP JSON for other clients, and the shipped skills with their install state."""

    @extend_schema(
        operation_id="v1_connect",
        description="Connection details for Claude Code / MCP clients plus the Atlas skills.",
        responses={200: None},
    )
    def get(self, request):
        from core.mcp_connect import connection_info
        from core.skills import list_skills, personal_skills_dir
        from core.tooling import detect_tools

        return Response(
            {
                **connection_info(request),
                "skills": list_skills(),
                "skills_dir": str(personal_skills_dir()),
                "tools": detect_tools(),
            }
        )


class ConnectTestAPIView(APIView):
    """Live connection test for the Connect page (backlog #290)."""

    @extend_schema(
        operation_id="v1_connect_test",
        description="Run the four connection checks: API key, API reachability with the key, "
        "the MCP command's --check self-test, and the claude CLI on PATH.",
        request=None,
        responses={200: None},
    )
    def post(self, request):
        from core.mcp_connect import test_connection

        return Response(test_connection(request))


class ConnectSkillsAPIView(APIView):
    """Install / update the Atlas skills into ~/.claude/skills."""

    @extend_schema(
        operation_id="v1_connect_install_skills",
        description="Copy the shipped Atlas skills into the personal Claude Code skills folder.",
        request=None,
        responses={200: None},
    )
    def post(self, request):
        from core.skills import install_skills, personal_skills_dir

        try:
            names = install_skills()
        except OSError as exc:
            return Response({"detail": f"Could not install the skills: {exc}"}, status=500)
        return Response({"installed": names, "dir": str(personal_skills_dir())})


class BotsAPIView(APIView):
    """Bots list with run history — the SPA automations page."""

    @extend_schema(
        description="All bots with enabled state and recent runs.", responses={200: None}
    )
    def get(self, request):
        from django.db.models import Count, Prefetch

        from bots.models import Bot, BotRun
        from bots.registry import BOTS

        states = {
            b.slug: b
            for b in Bot.objects.filter(slug__in=BOTS).prefetch_related(
                Prefetch("runs", queryset=BotRun.objects.annotate(filed=Count("captures")))
            )
        }
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
                            {
                                "id": r.pk,
                                "ok": r.ok,
                                "count": r.count,
                                "captures": r.filed,  # #423: what the run filed in the inbox
                                "started_at": r.started_at.isoformat(),
                            }
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
                        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
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


class CommentDeleteAPIView(APIView):
    """Remove one comment (#414) — or, since #439, resolve / reopen it with PATCH."""

    @extend_schema(
        description="Resolve or reopen a comment (#439): {resolved: true|false}. Resolved "
        "comments stay (and stay searchable) but drop out of the editor gutter.",
        request=inline_serializer(
            "CommentResolveRequest", {"resolved": rf_serializers.BooleanField()}
        ),
        responses={200: None},
    )
    def patch(self, request, pk):
        from django.utils import timezone

        from core.models import Comment

        comment = Comment.objects.filter(pk=pk).first()
        if comment is None:
            return Response({"detail": "No such comment."}, status=404)
        resolved = request.data.get("resolved")
        if not isinstance(resolved, bool):
            return Response({"detail": "Send {resolved: true|false}."}, status=400)
        comment.resolved_at = timezone.now() if resolved else None
        comment.save(update_fields=["resolved_at", "updated_at"])
        return Response(
            {
                "id": comment.pk,
                "resolved_at": comment.resolved_at.isoformat() if comment.resolved_at else None,
            }
        )

    @extend_schema(description="Delete a comment by id.", responses={204: None})
    def delete(self, request, pk):
        from core.models import Comment

        deleted, _ = Comment.objects.filter(pk=pk).delete()
        if not deleted:
            return Response({"detail": "No such comment."}, status=404)
        return Response(status=204)


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
