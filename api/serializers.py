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


class ProjectReferenceSerializer(serializers.ModelSerializer):
    project = ProjectSlugField()

    class Meta:
        model = ProjectReference
        fields = [
            "id",
            "project",
            "reference",
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

    class Meta:
        model = Note
        fields = ["id", "project", "title", "body", "references", "created_at", "updated_at"]
        extra_kwargs = {"references": {"required": False}}
