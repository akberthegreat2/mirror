"""DRF serializers for the Mirror control plane.

These serializers describe the unmanaged Django models that mirror Mirror's
database schema. Mutations that change control-plane state (pipeline version
creation) delegate to ``ControlPlaneRepository`` and therefore to
:class:`mirror_control.ControlService`; Django never writes operational state
directly.
"""

from __future__ import annotations

from mirror_control_django import models
from mirror_control_django.repository import ControlPlaneRepository
from rest_framework import serializers


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Project
        fields = "__all__"


class PipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Pipeline
        fields = "__all__"


class PipelineVersionSerializer(serializers.ModelSerializer):
    definition_text = serializers.CharField(write_only=True, required=False, allow_blank=True)
    definition_preview = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = models.PipelineVersion
        fields = (
            "id",
            "pipeline_id",
            "version",
            "definition_ref",
            "definition_hash",
            "definition_format",
            "metadata",
            "created_at",
            "updated_at",
            "definition_text",
            "definition_preview",
        )
        read_only_fields = (
            "id",
            "version",
            "definition_hash",
            "definition_ref",
            "definition_format",
            "created_at",
            "updated_at",
        )

    def get_definition_preview(self, obj: models.PipelineVersion) -> str:
        payload = ControlPlaneRepository().blob_store.get_bytes(obj.definition_ref)
        return "" if payload is None else payload.decode("utf-8")

    def create(self, validated_data):
        definition_text = validated_data.pop("definition_text", "")
        if not definition_text:
            raise serializers.ValidationError({"definition_text": "A pipeline version definition is required."})
        pipeline_id = validated_data["pipeline_id"]
        try:
            pipeline = models.Pipeline.objects.get(pk=pipeline_id)
        except models.Pipeline.DoesNotExist:
            raise serializers.ValidationError({"pipeline_id": "Pipeline does not exist."})
        if pipeline.is_read_only:
            raise serializers.ValidationError({"pipeline_id": "Code-defined pipelines are read-only; materialize a managed pipeline first."})
        project = models.Project.objects.get(pk=pipeline.project_id)
        repo = ControlPlaneRepository()
        definition = str(definition_text).encode("utf-8")
        _managed, version = repo.materialize_definition(
            project_slug=project.slug,
            pipeline_slug=pipeline.slug,
            definition=definition,
            name=pipeline.name,
            metadata=validated_data.get("metadata", {}) or {},
        )
        # Re-read the immutable version as a Django model instance for DRF.
        return models.PipelineVersion.objects.get(pk=str(version.id))

    def update(self, instance, validated_data):
        raise serializers.ValidationError("Pipeline versions are immutable; create a new version instead.")


class ExecutionRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ExecutionRun
        fields = "__all__"


class ExecutionStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ExecutionStep
        fields = "__all__"


class WorkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Worker
        fields = "__all__"


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Schedule
        fields = "__all__"


class CrawledURLSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CrawledURL
        fields = "__all__"


class ArchiveRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ArchiveRecord
        fields = "__all__"


class CheckpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Checkpoint
        fields = "__all__"


class DeadLetterSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DeadLetter
        fields = "__all__"
