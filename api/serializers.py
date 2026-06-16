from rest_framework import serializers

from documents.models import Document, Folder, Tag
from literature.models import ProjectReference, Reference
from notes.models import Note, QuickCapture
from plans.models import Milestone, Phase, ResearchQuestion, Task
from projects.models import DecisionRecord, Project


class ProjectSerializer(serializers.ModelSerializer):
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug"]


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
    class Meta:
        model = Milestone
        fields = [
            "id",
            "phase",
            "title",
            "due_date",
            "completed_at",
            "notes",
            "created_at",
            "updated_at",
        ]


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


class DecisionRecordSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()

    class Meta:
        model = DecisionRecord
        fields = [
            "id",
            "project",
            "title",
            "context",
            "decision",
            "alternatives",
            "decided_on",
            "created_at",
            "updated_at",
        ]


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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["bibtex_key"]

    def create(self, validated_data):
        from literature.services import generate_bibtex_key

        validated_data["bibtex_key"] = generate_bibtex_key(
            validated_data.get("authors", []),
            validated_data.get("year"),
            validated_data.get("title", ""),
        )
        return super().create(validated_data)


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


class QuickCaptureSerializer(serializers.ModelSerializer):
    project = ProjectSlugField(required=False, allow_null=True)

    class Meta:
        model = QuickCapture
        fields = ["id", "text", "processed", "project", "created_at", "updated_at"]


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

    class Meta:
        model = Note
        fields = [
            "id",
            "project",
            "title",
            "body",
            "references",
            "backlinks",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"references": {"required": False}}

    def get_backlinks(self, note) -> list[dict]:
        return [
            {"id": link.source_id, "title": link.source.title}
            for link in note.incoming_links.select_related("source")
        ]


class HypothesisSerializer(serializers.ModelSerializer):
    supports = serializers.SerializerMethodField()
    contradicts = serializers.SerializerMethodField()

    class Meta:
        from research.models import Hypothesis

        model = Hypothesis
        fields = ["id", "statement", "status", "supports", "contradicts", "created_at"]

    def get_supports(self, obj) -> int:
        return sum(1 for e in obj.evidence.all() if e.direction == "supports")

    def get_contradicts(self, obj) -> int:
        return sum(1 for e in obj.evidence.all() if e.direction == "contradicts")


class ExperimentEntrySerializer(serializers.ModelSerializer):
    commit_label = serializers.CharField(read_only=True)

    class Meta:
        from research.models import ExperimentEntry

        model = ExperimentEntry
        fields = ["id", "date", "title", "body", "commit_url", "commit_label", "created_at"]


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        from research.models import Dataset

        model = Dataset
        fields = ["id", "name", "location", "version", "checksum", "description"]


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
                instance.manuscript.files.filter(is_main=True).update(is_main=False)
                return super().update(instance, validated_data)
        return super().update(instance, validated_data)


class ManuscriptFileSummarySerializer(serializers.ModelSerializer):
    class Meta:
        from writing.models import ManuscriptFile

        model = ManuscriptFile
        fields = ["id", "path", "kind", "is_main"]


class ManuscriptSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()
    events = SubmissionEventSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    files = ManuscriptFileSummarySerializer(many=True, read_only=True)

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
            "compile_status",
            "compile_diagnostics",
            "compiled_at",
            "events",
            "files",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["compile_status", "compile_diagnostics", "compiled_at"]


class PromptSerializer(serializers.ModelSerializer):
    class Meta:
        from prompts.models import Prompt

        model = Prompt
        fields = ["id", "title", "body", "tags", "created_at", "updated_at"]
