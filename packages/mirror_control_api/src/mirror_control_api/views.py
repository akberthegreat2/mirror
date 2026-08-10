"""REST views for the Mirror control plane."""

from __future__ import annotations

from dataclasses import asdict

from mirror_control_django import models
from mirror_control_django.manifest import control_plane_manifest
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from mirror_control_api.serializers import (
    ArchiveRecordSerializer,
    CheckpointSerializer,
    CrawledURLSerializer,
    DeadLetterSerializer,
    ExecutionRunSerializer,
    ExecutionStepSerializer,
    PipelineSerializer,
    PipelineVersionSerializer,
    ProjectSerializer,
    ScheduleSerializer,
    WorkerSerializer,
)


class ManifestViewSet(viewsets.ViewSet):
    """Expose the shared interface manifest through REST."""

    def list(self, request):
        manifest = control_plane_manifest()
        return Response(
            {
                "name": manifest.name,
                "version": manifest.version,
                "entities": [asdict(entity) for entity in manifest.entities],
            }
        )


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = models.Project.objects.all()
    serializer_class = ProjectSerializer


class PipelineViewSet(viewsets.ModelViewSet):
    queryset = models.Pipeline.objects.all()
    serializer_class = PipelineSerializer

    @action(detail=True, methods=["post"])
    def materialize(self, request, pk=None):
        pipeline = self.get_object()
        definition_text = request.data.get("definition_text", "")
        if not definition_text:
            return Response({"detail": "definition_text is required"}, status=400)
        if pipeline.is_read_only:
            return Response({"detail": "Code-defined pipelines are read-only"}, status=400)
        from mirror_control_django.repository import ControlPlaneRepository

        project = models.Project.objects.get(pk=pipeline.project_id)
        repo = ControlPlaneRepository()
        managed, _version = repo.materialize_definition(
            project_slug=project.slug,
            pipeline_slug=pipeline.slug,
            definition=str(definition_text).encode("utf-8"),
            metadata=request.data.get("metadata") or {},
            notes=str(request.data.get("notes", "")),
        )
        # Re-read the managed pipeline as a Django model instance for DRF.
        managed = models.Pipeline.objects.get(pk=str(managed.id))
        return Response(
            PipelineSerializer(managed, context=self.get_serializer_context()).data,
            status=201,
        )


class PipelineVersionViewSet(viewsets.ModelViewSet):
    queryset = models.PipelineVersion.objects.all()
    serializer_class = PipelineVersionSerializer

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Pipeline versions are immutable; create a new version instead."},
            status=405,
        )

    partial_update = update

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Pipeline versions are immutable."}, status=405)


class ExecutionRunViewSet(viewsets.ModelViewSet):
    queryset = models.ExecutionRun.objects.all()
    serializer_class = ExecutionRunSerializer


class ExecutionStepViewSet(viewsets.ModelViewSet):
    queryset = models.ExecutionStep.objects.all()
    serializer_class = ExecutionStepSerializer


class WorkerViewSet(viewsets.ModelViewSet):
    queryset = models.Worker.objects.all()
    serializer_class = WorkerSerializer


class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = models.Schedule.objects.all()
    serializer_class = ScheduleSerializer


class CrawledURLViewSet(viewsets.ModelViewSet):
    queryset = models.CrawledURL.objects.all()
    serializer_class = CrawledURLSerializer


class ArchiveRecordViewSet(viewsets.ModelViewSet):
    queryset = models.ArchiveRecord.objects.all()
    serializer_class = ArchiveRecordSerializer


class CheckpointViewSet(viewsets.ModelViewSet):
    queryset = models.Checkpoint.objects.all()
    serializer_class = CheckpointSerializer


class DeadLetterViewSet(viewsets.ModelViewSet):
    queryset = models.DeadLetter.objects.all()
    serializer_class = DeadLetterSerializer
