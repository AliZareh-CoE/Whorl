from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from core.models import TodoItem
from documents.models import Document, Folder, Tag
from literature.models import Highlight, LibraryTag, ProjectReference, Reference, SavedView
from notes.models import Note, QuickCapture
from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.models import DecisionRecord, Project


class ProjectSerializer(serializers.ModelSerializer):
    """Projects, with a read-only ``summary`` (UI audit 2026-09-06) so the Projects index can
    show phase, progress, health and counts per card without one request per project."""

    summary = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "status",
            "color",
            "position",
            "summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug"]

    def get_summary(self, project) -> dict:
        from plans import selectors as plan_selectors
        from plans.roadmap import project_roadmap

        done, total, percent = plan_selectors.project_progress(project)
        phase = plan_selectors.current_phase(project)
        health = None
        if phase is not None:
            row = next((r for r in project_roadmap(project)["phases"] if r["id"] == phase.pk), None)
            if row:
                health = {"state": row["state"], "label": row["label"]}
        return {
            "current_phase": phase.name if phase else None,
            "phase_progress": phase.progress if phase else None,
            "milestones_done": done,
            "milestones_total": total,
            "percent": percent,
            "health": health,
            "counts": {
                "papers": project.project_references.count(),
                "notes": project.notes.count(),
                "manuscripts": project.manuscripts.count(),
                "documents": project.documents.count(),
            },
        }


class ProjectSlugField(serializers.SlugRelatedField):
    def __init__(self, **kwargs):
        kwargs.setdefault("slug_field", "slug")
        kwargs.setdefault("queryset", Project.objects.all())
        super().__init__(**kwargs)


class PhaseSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()
    progress = serializers.IntegerField(read_only=True)

    class Meta:
        model = Phase
        fields = [
            "id",
            "project",
            "name",
            "order",
            "status",
            "objective",
            "target_start",
            "target_end",
            "progress",
            "created_at",
            "updated_at",
        ]


class MilestoneSerializer(serializers.ModelSerializer):
    # #512: dependencies — ids of the milestones this one waits for; `blocked` is live
    blocked_by = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Milestone.objects.all(), required=False
    )
    blocks = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    blocked = serializers.SerializerMethodField()

    class Meta:
        model = Milestone
        fields = [
            "id",
            "phase",
            "title",
            "due_date",
            "completed_at",
            "notes",
            "blocked_by",
            "blocks",
            "blocked",
            "created_at",
            "updated_at",
        ]

    def get_blocked(self, milestone) -> bool:
        if milestone.completed_at:
            return False
        open_blockers = getattr(milestone, "open_blockers", None)  # annotated by the selectors
        if open_blockers is not None:
            return open_blockers > 0
        return any(b.completed_at is None for b in milestone.blocked_by.all())

    def validate(self, attrs):
        blockers = attrs.get("blocked_by")
        if blockers is not None:
            from plans.dependencies import DependencyError, check_blockers

            target = self.instance
            if target is None:  # a new milestone: check against its phase's project
                phase = attrs.get("phase")
                target = Milestone(phase=phase)
                target.pk = -1
            try:
                check_blockers(target, list(blockers))
            except DependencyError as exc:
                raise serializers.ValidationError({"blocked_by": str(exc)}) from exc
        return attrs


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "milestone",
            "title",
            "done",
            "due_date",
            "order",
            "created_at",
            "updated_at",
        ]


class ResearchQuestionSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()

    class Meta:
        model = ResearchQuestion
        fields = ["id", "project", "question", "status", "phases", "created_at", "updated_at"]


class RenderedBodyMixin:
    """`<field>_html` companions (#407): the markdown body rendered with [[note]] and
    @cite-key mentions resolved, ready for the SPA to show. Read-only."""

    rendered_fields: tuple[str, ...] = ()
    soft_breaks = False

    def _rendered(self, obj, field: str) -> str:
        from core.rendering import render_body

        return render_body(
            getattr(obj, field, "") or "",
            getattr(obj, "project", None),
            soft_breaks=self.soft_breaks,
        )


class DecisionRecordSerializer(RenderedBodyMixin, serializers.ModelSerializer):
    project = ProjectSlugField()
    context_html = serializers.SerializerMethodField()
    decision_html = serializers.SerializerMethodField()
    alternatives_html = serializers.SerializerMethodField()

    class Meta:
        model = DecisionRecord
        fields = [
            "id",
            "project",
            "title",
            "context",
            "decision",
            "alternatives",
            "context_html",
            "decision_html",
            "alternatives_html",
            "decided_on",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.CharField())
    def get_context_html(self, obj):
        return self._rendered(obj, "context")

    @extend_schema_field(serializers.CharField())
    def get_decision_html(self, obj):
        return self._rendered(obj, "decision")

    @extend_schema_field(serializers.CharField())
    def get_alternatives_html(self, obj):
        return self._rendered(obj, "alternatives")


class FolderSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()

    class Meta:
        model = Folder
        fields = ["id", "project", "parent", "name", "created_at", "updated_at"]


class TagSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()

    class Meta:
        model = Tag
        fields = ["id", "project", "name", "color", "created_at", "updated_at"]


class DocumentSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()

    def validate_file(self, value):
        from django.core.exceptions import ValidationError as DjangoValidationError

        from core.security import validate_upload_size

        try:
            return validate_upload_size(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages[0]) from exc

    class Meta:
        model = Document
        fields = [
            "id",
            "project",
            "folder",
            "file",
            "title",
            "description",
            "tags",
            "file_size",
            "content_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["file_size", "content_type"]


class ReferenceSerializer(serializers.ModelSerializer):
    # Library v2: which projects hold this paper, with the per-project reading state — one
    # prefetch on the viewset, no per-row queries.
    projects = serializers.SerializerMethodField()
    # Library v2 slice 8: did the search term hit inside the PDF text? (only on filtered lists)
    pdf_match = serializers.SerializerMethodField()
    text_status = serializers.SerializerMethodField()
    # Library v2 slice 5: tags by name (writable: a list of names creates missing tags)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=60), required=False, write_only=True
    )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["tags"] = [t.name for t in instance.tags.all()]
        return data

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_pdf_match(self, obj):
        return getattr(obj, "pdf_match", None)

    @extend_schema_field(serializers.CharField())
    def get_text_status(self, obj):
        """'indexed' (searchable), 'error: …', 'pending' (PDF not read yet), or 'none' (no PDF)."""
        if not obj.pdf:
            return "none"
        try:
            text = obj.text
        except ObjectDoesNotExist:
            return "pending"
        return f"error: {text.error}" if text.error else "indexed"

    def _apply_tags(self, instance, names):
        from literature.models import LibraryTag

        if names is None:
            return
        instance.tags.set([LibraryTag.get_or_create_named(n) for n in names if n.strip()])

    def update(self, instance, validated_data):
        names = validated_data.pop("tags", None)
        instance = super().update(instance, validated_data)
        self._apply_tags(instance, names)
        return instance

    @extend_schema_field(
        serializers.ListField(
            child=inline_serializer(
                "ReferenceProjectLink",
                fields={
                    "slug": serializers.CharField(),
                    "name": serializers.CharField(),
                    "color": serializers.CharField(),
                    "reading_status": serializers.CharField(),
                    "priority": serializers.CharField(),
                },
            )
        )
    )
    def get_projects(self, obj) -> list[dict]:
        return [
            {
                "slug": link.project.slug,
                "name": link.project.name,
                "color": link.project.color,
                "reading_status": link.reading_status,
                "priority": link.priority,
            }
            for link in obj.project_links.all()
        ]

    def validate_pdf(self, value):
        from django.core.exceptions import ValidationError as DjangoValidationError

        from core.security import validate_pdf

        try:
            return validate_pdf(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages[0]) from exc

    class Meta:
        model = Reference
        fields = [
            "id",
            "doi",
            "arxiv_id",
            "openalex_id",
            "bibtex_key",
            "entry_type",
            "title",
            "authors",
            "year",
            "venue",
            "abstract",
            "url",
            "pdf",
            "raw_bibtex",
            "extra",
            "citation_count",
            "projects",
            "tags",
            "pdf_match",
            "text_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["bibtex_key", "projects"]

    def create(self, validated_data):
        from literature.services import generate_bibtex_key

        names = validated_data.pop("tags", None)
        validated_data["bibtex_key"] = generate_bibtex_key(
            validated_data.get("authors", []),
            validated_data.get("year"),
            validated_data.get("title", ""),
        )
        instance = super().create(validated_data)
        self._apply_tags(instance, names)
        return instance


class ReferenceSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = ["id", "bibtex_key", "title", "authors", "year", "venue"]


class ProjectReferenceSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()
    reference_summary = ReferenceSummarySerializer(source="reference", read_only=True)

    class Meta:
        model = ProjectReference
        fields = [
            "id",
            "project",
            "reference",
            "reference_summary",
            "reading_status",
            "priority",
            "notes",
            "created_at",
            "updated_at",
        ]


class QuickCaptureSerializer(RenderedBodyMixin, serializers.ModelSerializer):
    project = ProjectSlugField(required=False, allow_null=True)
    hint = serializers.SerializerMethodField()
    text_html = serializers.SerializerMethodField()
    soft_breaks = True  # captures are jotted, not typeset: every newline is a break

    class Meta:
        model = QuickCapture
        fields = [
            "id",
            "text",
            "text_html",
            "processed",
            "project",
            "snoozed_until",
            "became",
            "triaged_at",
            "link_title",
            "link_fetched_at",
            "hint",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["triaged_at", "link_title", "link_fetched_at"]

    became = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_became(self, obj):
        """#496: {kind, id, app_url} when the capture was converted, else null."""
        from notes.capture import became

        return became(obj)

    def update(self, instance, validated_data):
        """Filing or dismissing stamps `triaged_at`; putting it back clears it (#496)."""
        from django.utils import timezone

        if "processed" in validated_data and validated_data["processed"] != instance.processed:
            instance.triaged_at = timezone.now() if validated_data["processed"] else None
        return super().update(instance, validated_data)

    @extend_schema_field(serializers.CharField())
    def get_text_html(self, obj):
        return self._rendered(obj, "text")

    @extend_schema_field(serializers.DictField())
    def get_hint(self, obj):
        """Inbox v2: what the capture looks like (paper / note / todo / …) and any ids found;
        #494 adds `project` — the active project whose vocabulary the capture shares most
        (slug, name, score, terms), or null. The project index is built once per request."""
        from notes.capture import detect, project_index, suggest_project

        hint = detect(obj.text)
        index = self.context.get("_project_index")
        if index is None:
            index = project_index()
            self.context["_project_index"] = index
        hint["project"] = suggest_project(obj.text, index)
        return hint


class ConvertCaptureSerializer(serializers.Serializer):
    target = serializers.ChoiceField(choices=["paper", "note", "todo", "milestone", "decision"])
    project = ProjectSlugField(required=False, allow_null=True)
    phase = serializers.IntegerField(required=False, allow_null=True)
    due = serializers.DateField(required=False, allow_null=True)
    # #500: the caller's zone ("Europe/Berlin" or "+05:30") for a time written in the capture
    tz = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)


class BulkTriageSerializer(serializers.Serializer):
    """#497: many captures, one action — file (needs project), dismiss, snooze (until), todo,
    wake."""

    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    action = serializers.ChoiceField(choices=["file", "dismiss", "snooze", "todo", "wake"])
    project = ProjectSlugField(required=False, allow_null=True)
    until = serializers.CharField(required=False, allow_blank=True, default="")


class SnoozeCaptureSerializer(serializers.Serializer):
    """#495: `until` is tomorrow / monday / next-week / weekend / YYYY-MM-DD; blank wakes it."""

    until = serializers.CharField(required=False, allow_blank=True, default="")


class TodoItemSerializer(serializers.ModelSerializer):
    """The owner's Today list: text, done, optional project."""

    project = ProjectSlugField(required=False, allow_null=True)

    class Meta:
        model = TodoItem
        fields = [
            "id",
            "text",
            "done",
            "done_at",
            "position",
            "due_at",
            "project",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["done_at"]


class LibraryTagSerializer(serializers.ModelSerializer):
    count = serializers.IntegerField(read_only=True)

    class Meta:
        model = LibraryTag
        fields = ["id", "name", "color", "count", "created_at"]

    def validate_name(self, value):
        clean = " ".join((value or "").split()).strip()
        if not clean:
            raise serializers.ValidationError("A tag needs a name.")
        return clean

    def validate_color(self, value):
        """Blank (no colour) or a #rrggbb hex — the Library paints chips with it (#381)."""
        import re

        value = (value or "").strip().lower()
        if value and not re.fullmatch(r"#[0-9a-f]{6}", value):
            raise serializers.ValidationError("Use a #rrggbb colour, or leave it blank.")
        return value


class SavedViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedView
        fields = ["id", "name", "params", "position", "created_at", "updated_at"]


class ManuscriptReferenceInSerializer(serializers.Serializer):
    """Add a library paper to a manuscript's bibliography (Writing v2 slice 1)."""

    reference = serializers.PrimaryKeyRelatedField(queryset=Reference.objects.all())
    cite_key_override = serializers.CharField(required=False, allow_blank=True, max_length=120)


class SubmissionEventInSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=[
            "submitted",
            "desk_reject",
            "reviews_received",
            "revision_submitted",
            "accepted",
            "rejected",
            "published",
            "note",
        ]
    )
    date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True)


class ReviewThemeInSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    order = serializers.IntegerField(required=False, allow_null=True)


class ReviewMarkInSerializer(serializers.Serializer):
    """One matrix cell (Matrix v2)."""

    reference = serializers.CharField(help_text="Reference id or bibtex key")
    theme = serializers.CharField(help_text="Theme id or name (a name creates the theme)")
    marked = serializers.BooleanField(default=True)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=300)


class ReviewsInSerializer(serializers.Serializer):
    """Paste the reviews you received (Writing v2 slice 2)."""

    text = serializers.CharField(
        allow_blank=True,
        help_text="The reviews as received; 'Reviewer N' headings and numbered/bulleted points are recognised.",
    )
    date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class NoteFromTemplateSerializer(serializers.Serializer):
    """Create a note from a template (Notes v2 slice 3)."""

    project = ProjectSlugField()
    kind = serializers.ChoiceField(
        choices=["blank", "literature", "daily", "meeting", "experiment"],
        help_text="literature needs `reference`; daily returns today's note if it exists.",
    )
    reference = serializers.PrimaryKeyRelatedField(
        queryset=Reference.objects.all(), required=False, allow_null=True
    )


class PlanOutlineSerializer(serializers.Serializer):
    """Plan v2: the whole plan as a Markdown outline (see plans/outline.py for the grammar)."""

    markdown = serializers.CharField(
        help_text="'# phase [status] (start → end)', '> objective', '- [ ] milestone (due YYYY-MM-DD)', indented '- [ ] task'; keep the {#id} tokens to rename safely."
    )
    dry_run = serializers.BooleanField(
        default=False, help_text="Preview the changes without writing."
    )


class HighlightSerializer(serializers.ModelSerializer):
    """A passage marked while reading (Library v2 slice 7)."""

    project = ProjectSlugField(required=False, allow_null=True)
    project_name = serializers.CharField(source="project.name", read_only=True, default="")

    class Meta:
        model = Highlight
        fields = [
            "id",
            "reference",
            "project",
            "project_name",
            "page",
            "text",
            "comment",
            "color",
            "rects",
            "created_at",
            "updated_at",
        ]

    def validate_rects(self, value):
        if not isinstance(value, list) or len(value) > 200:
            raise serializers.ValidationError("rects must be a list of at most 200 boxes.")
        for box in value:
            if not isinstance(box, dict) or set(box) != {"x", "y", "w", "h"}:
                raise serializers.ValidationError("each box needs x, y, w, h.")
            if not all(isinstance(box[k], (int, float)) and -0.01 <= box[k] <= 1.01 for k in box):
                raise serializers.ValidationError("box values are fractions of the page (0..1).")
        return [{k: round(float(box[k]), 4) for k in ("x", "y", "w", "h")} for box in value]


class MergeReferencesSerializer(serializers.Serializer):
    keep = serializers.IntegerField(help_text="The reference that survives.")
    merge = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=50,
        help_text="Ids folded into `keep` and deleted.",
    )


class BulkReferenceActionSerializer(serializers.Serializer):
    """Library v2 bulk bar: one action over many references."""

    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=500)
    action = serializers.ChoiceField(
        choices=[
            "link",
            "unlink",
            "status",
            "priority",
            "delete",
            "find_metadata",
            "fetch_pdf",
            "tag",
            "untag",
        ]
    )
    project = serializers.SlugField(
        required=False, allow_blank=True, help_text="Needed for link/unlink/status/priority."
    )
    value = serializers.CharField(
        required=False, allow_blank=True, help_text="The reading status or priority to set."
    )


class ImportReferencesSerializer(serializers.Serializer):
    """Library import (Library v2): drop files and/or paste text in one call."""

    files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        help_text="Any mix of .pdf, .bib, .ris, or CSL .json files (multipart).",
    )
    text = serializers.CharField(
        required=False, allow_blank=True, help_text="Pasted BibTeX / CSL-JSON / RIS."
    )
    format = serializers.ChoiceField(
        choices=["auto", "bibtex", "csl-json", "ris"],
        default="auto",
        help_text="Format of `text`; 'auto' sniffs it.",
    )
    project = serializers.SlugField(
        required=False, allow_blank=True, help_text="Optional project slug to link everything to."
    )


class ImportZoteroSerializer(serializers.Serializer):
    project = serializers.SlugField(required=False, allow_blank=True)
    base_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="Zotero local API root (default http://127.0.0.1:23119).",
    )


class AddByDoiSerializer(serializers.Serializer):
    doi = serializers.CharField(help_text="DOI or arXiv ID, raw or as a URL.")
    project = serializers.SlugField(
        required=False,
        allow_blank=True,
        help_text="Optional project slug to link the reference to.",
    )


class NoteSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()
    backlinks = serializers.SerializerMethodField()
    references_detail = ReferenceSummarySerializer(source="references", many=True, read_only=True)

    class Meta:
        model = Note
        fields = [
            "id",
            "project",
            "title",
            "body",
            "references",
            "references_detail",
            "backlinks",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["tags"]
        extra_kwargs = {"references": {"required": False}}

    def get_backlinks(self, note) -> list[dict]:
        # `.all()` so the viewset's prefetch (incoming_links__source) is used — a
        # select_related() here built a fresh queryset per row (Audit #29)
        return [
            {"id": link.source_id, "title": link.source.title} for link in note.incoming_links.all()
        ]


class EvidenceSerializer(serializers.ModelSerializer):
    """One piece of evidence for a hypothesis (Research v2): a paper, a note or a document,
    with a direction and a one-line summary."""

    reference_detail = ReferenceSummarySerializer(source="reference", read_only=True)
    note_title = serializers.CharField(source="note.title", read_only=True, default="")
    document_title = serializers.CharField(source="document.title", read_only=True, default="")

    class Meta:
        from research.models import Evidence

        model = Evidence
        fields = [
            "id",
            "hypothesis",
            "direction",
            "summary",
            "reference",
            "reference_detail",
            "note",
            "note_title",
            "document",
            "document_title",
            "created_at",
        ]
        extra_kwargs = {
            "reference": {"required": False, "allow_null": True},
            "note": {"required": False, "allow_null": True},
            "document": {"required": False, "allow_null": True},
        }


class HypothesisSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()
    supports = serializers.SerializerMethodField()
    contradicts = serializers.SerializerMethodField()
    mixed = serializers.SerializerMethodField()
    suggested_status = serializers.SerializerMethodField()
    evidence = EvidenceSerializer(many=True, read_only=True)

    class Meta:
        from research.models import Hypothesis

        model = Hypothesis
        fields = [
            "id",
            "project",
            "statement",
            "status",
            "supports",
            "contradicts",
            "mixed",
            "suggested_status",
            "evidence",
            "created_at",
            "updated_at",
        ]

    def get_supports(self, obj) -> int:
        return sum(1 for e in obj.evidence.all() if e.direction == "supports")

    def get_contradicts(self, obj) -> int:
        return sum(1 for e in obj.evidence.all() if e.direction == "contradicts")

    def get_mixed(self, obj) -> int:
        return sum(1 for e in obj.evidence.all() if e.direction == "mixed")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_suggested_status(self, obj):
        return obj.suggested_status


class ExperimentEntrySerializer(RenderedBodyMixin, serializers.ModelSerializer):
    project = ProjectSlugField()
    commit_label = serializers.CharField(read_only=True)
    protocol_label = serializers.SerializerMethodField()
    body_html = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_body_html(self, obj):
        return self._rendered(obj, "body")

    hypotheses = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=__import__("research.models", fromlist=["Hypothesis"]).Hypothesis.objects.all(),
    )

    class Meta:
        from research.models import ExperimentEntry

        model = ExperimentEntry
        fields = [
            "id",
            "project",
            "date",
            "title",
            "body",
            "body_html",
            "commit_url",
            "commit_label",
            "protocol",
            "protocol_label",
            "hypotheses",
            "created_at",
        ]
        extra_kwargs = {
            "protocol": {"required": False, "allow_null": True},
            "date": {"required": False},
        }

    def get_protocol_label(self, obj) -> str:
        return str(obj.protocol) if obj.protocol_id else ""


class DatasetSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()

    class Meta:
        from research.models import Dataset

        model = Dataset
        fields = ["id", "project", "name", "location", "version", "checksum", "description"]


class ProtocolSerializer(RenderedBodyMixin, serializers.ModelSerializer):
    project = ProjectSlugField()
    is_current = serializers.BooleanField(read_only=True)
    body_html = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_body_html(self, obj):
        return self._rendered(obj, "body")

    class Meta:
        from research.models import Protocol

        model = Protocol
        fields = [
            "id",
            "project",
            "title",
            "body",
            "body_html",
            "version",
            "parent",
            "is_current",
            "created_at",
            "updated_at",
        ]
        # version + parent form the immutable history chain; they're set by the model /
        # the new-version action, never edited directly through the API.
        read_only_fields = ["version", "parent"]


class SubmissionEventSerializer(serializers.ModelSerializer):
    class Meta:
        from writing.models import SubmissionEvent

        model = SubmissionEvent
        fields = ["id", "kind", "date", "notes"]


class ManuscriptFileSerializer(serializers.ModelSerializer):
    class Meta:
        from writing.models import ManuscriptFile

        model = ManuscriptFile
        fields = [
            "id",
            "manuscript",
            "path",
            "kind",
            "content",
            "asset",
            "is_main",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["kind"]  # derived from path

    def validate_path(self, value):
        from writing.models import validate_manuscript_path

        validate_manuscript_path(value)
        return value

    def validate_asset(self, value):
        if value is not None:
            from core.security import validate_upload_size

            validate_upload_size(value)
        return value

    def validate(self, attrs):
        if self.instance is not None and "manuscript" in attrs:
            if attrs["manuscript"] != self.instance.manuscript:
                raise serializers.ValidationError("Files can't move between manuscripts.")
        if self.instance is not None and self.instance.is_main and attrs.get("is_main") is False:
            raise serializers.ValidationError(
                "A manuscript keeps exactly one main file — promote another instead."
            )
        return attrs

    def update(self, instance, validated_data):
        from django.db import transaction

        if validated_data.get("is_main") and not instance.is_main:
            with transaction.atomic():
                from django.utils import timezone

                instance.manuscript.files.filter(is_main=True).update(
                    is_main=False, updated_at=timezone.now()
                )
                return super().update(instance, validated_data)
        return super().update(instance, validated_data)


class ManuscriptFileSummarySerializer(serializers.ModelSerializer):
    class Meta:
        from writing.models import ManuscriptFile

        model = ManuscriptFile
        fields = ["id", "path", "kind", "is_main"]


class ManuscriptSerializer(serializers.ModelSerializer):
    progress = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField())
    def get_progress(self, obj):
        """#413: the last 14 days of word samples (sparkline), today's delta and the streak."""
        from writing.progress import progress

        summary = progress(obj, days=14)
        return {
            "today_delta": summary["today_delta"],
            "week_delta": summary["week_delta"],
            "streak": summary["streak"],
            "words": summary["words"],
            "samples": [s["delta"] for s in summary["samples"]],
            "compiles": summary["compiles"],  # #460: per-day compiles, today, week
        }

    project = ProjectSlugField()
    events = SubmissionEventSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    files = ManuscriptFileSummarySerializer(many=True, read_only=True)
    clock = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField())
    def get_clock(self, obj):
        """#474: how long the paper has sat in its status — since (date), days, source
        (the event kind that started the clock, or "updated"), and a label like
        "42 d under review"."""
        from writing.clock import nudge, status_clock

        clock = status_clock(obj)
        clock["nudge"] = nudge(obj, clock)  # #475: due / after_days / basis / waited / last
        return clock

    class Meta:
        from writing.models import Manuscript

        model = Manuscript
        fields = [
            "id",
            "project",
            "project_name",
            "title",
            "status",
            "target_venue",
            "deadline",
            "abstract",
            "latex_source",
            "venue_limits",
            "auto_revisions_keep",
            "compile_status",
            "compile_diagnostics",
            "compiled_at",
            "events",
            "files",
            "progress",
            "clock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["compile_status", "compile_diagnostics", "compiled_at"]

    def validate_auto_revisions_keep(self, value):
        if value < 1 or value > 500:
            raise serializers.ValidationError("Keep between 1 and 500 automatic revisions.")
        return value

    def validate_venue_limits(self, value):
        from writing.budget import clean_limits

        return clean_limits(value)


class PromptSerializer(serializers.ModelSerializer):
    # #393: the placeholders with their defaults, so MCP clients can fill a prompt correctly
    variables = serializers.ListField(child=serializers.DictField(), read_only=True)

    class Meta:
        from prompts.models import Prompt

        model = Prompt
        fields = ["id", "title", "body", "tags", "variables", "created_at", "updated_at"]
