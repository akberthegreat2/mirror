"""Fail-closed REST views for the Mirror control plane.

Every endpoint is locked down by default (ADR-0045): authentication is
required, mutating and destructive actions require a staff account, destructive
actions additionally require an explicit ``confirm=true`` and are audit-logged,
and non-staff users only reach entities in projects they can access. The host
may relax these defaults only by setting ``MIRROR_CONTROL_OPEN_API = True``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, ClassVar
from uuid import UUID, uuid4

from mirror_control_django import models
from mirror_control_django.manifest import control_plane_manifest
from mirror_control_django.repository import ControlPlaneRepository
from mirror_control_django.service import DjangoControlService, default_metadata_store
from mirror_core.metadata.models import MetadataRecord
from mirror_core.metadata.store import MetadataStore
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from mirror_control_api.permissions import (
    ControlPlaneAuthenticated,
    ControlPlaneDestroy,
    ControlPlaneElevated,
    ControlPlaneObjectAccess,
    accessible_project_ids,
    isolate_queryset,
    open_api_enabled,
)
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

_CRUD_ACTIONS: dict[str, str] = {
    "list": "list",
    "retrieve": "get",
    "create": "create",
    "update": "update",
    "partial_update": "update",
    "destroy": "delete",
}


class _OperationNotAdvertised(BasePermission):
    """Deny operations the control-plane manifest does not expose."""

    message = "This operation is not exposed by the control-plane manifest."

    def has_permission(self, request: Any, view: Any) -> bool:
        return open_api_enabled(request)


def _actor(request: Any) -> str | None:
    user = request.user
    return user.username if user and user.is_authenticated else None


def _control_service() -> DjangoControlService:
    return DjangoControlService()


_audit_store_cache: list[MetadataStore] | None = None


def _audit_store() -> MetadataStore:
    """Return the shared audit metadata store, built once per process."""

    global _audit_store_cache
    if _audit_store_cache is None:
        _audit_store_cache = [default_metadata_store()]
    return _audit_store_cache[0]


class ControlPlaneViewSet(viewsets.ModelViewSet):
    """Base viewset enforcing the fail-closed control-plane contract.

    Subclasses declare ``advertised_actions`` (DRF action -> manifest
    operation); any action that is not advertised is denied. Non-advertised
    entities expose only their manifest operations.
    """

    permission_classes: ClassVar[list[Any]] = [
        ControlPlaneAuthenticated,
        ControlPlaneObjectAccess,
    ]
    advertised_actions: ClassVar[dict[str, str]] = _CRUD_ACTIONS
    elevated_actions: frozenset[str] = frozenset(
        {"create", "update", "partial_update", "destroy"}
    )
    confirmed_actions: frozenset[str] = frozenset()

    def get_permissions(self):
        if self.action is None:
            return [ControlPlaneAuthenticated(), ControlPlaneObjectAccess()]
        if self.action not in self.advertised_actions:
            return [_OperationNotAdvertised()]
        if self.action == "destroy" or self.action in self.confirmed_actions:
            return [ControlPlaneDestroy(), ControlPlaneObjectAccess()]
        if self.action in self.elevated_actions:
            return [ControlPlaneElevated(), ControlPlaneObjectAccess()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        request = getattr(self, "request", None)
        user = getattr(request, "user", None)
        if user is None or user.is_anonymous:
            return queryset
        if open_api_enabled(request) or user.is_superuser or user.is_staff:
            return queryset
        allowed = accessible_project_ids(user)
        return isolate_queryset(queryset, self.queryset.model, allowed)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.check_object_permissions(request, instance)
        _audit(instance, "delete", request)
        self.perform_destroy(instance)
        return Response(status=204)


def _audit(instance: Any, action: str, request: Any) -> None:
    store = _audit_store()
    subject = str(getattr(instance, "id", None) or instance.pk)
    store.put(
        MetadataRecord.audit_event(
            subject,
            action,
            payload={
                "actor": _actor(request) or "system",
                "action": action,
                "target": type(instance).__name__,
            },
        )
    )


class ManifestViewSet(viewsets.ViewSet):
    """Expose the shared interface manifest through REST."""

    permission_classes: ClassVar[list[Any]] = [ControlPlaneAuthenticated]

    def list(self, request):
        manifest = control_plane_manifest()
        return Response(
            {
                "name": manifest.name,
                "version": manifest.version,
                "entities": [asdict(entity) for entity in manifest.entities],
            }
        )


class ProjectViewSet(ControlPlaneViewSet):
    queryset = models.Project.objects.all()
    serializer_class = ProjectSerializer


class PipelineViewSet(ControlPlaneViewSet):
    queryset = models.Pipeline.objects.all()
    serializer_class = PipelineSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        **_CRUD_ACTIONS,
        "materialize": "materialize",
        "run": "run",
    }
    elevated_actions = frozenset(
        {"create", "update", "partial_update", "destroy", "materialize", "run"}
    )

    @action(detail=True, methods=["post"])
    def materialize(self, request, pk=None):
        pipeline = self.get_object()
        definition_text = request.data.get("definition_text", "")
        if not definition_text:
            return Response({"detail": "definition_text is required"}, status=400)
        if pipeline.is_read_only:
            return Response(
                {"detail": "Code-defined pipelines are read-only"}, status=400
            )
        project = models.Project.objects.get(pk=pipeline.project_id)
        repo = ControlPlaneRepository()
        managed, _version = repo.materialize_definition(
            project_slug=project.slug,
            pipeline_slug=pipeline.slug,
            definition=str(definition_text).encode("utf-8"),
            metadata=request.data.get("metadata") or {},
            notes=str(request.data.get("notes", "")),
        )
        managed = models.Pipeline.objects.get(pk=str(managed.id))
        return Response(
            PipelineSerializer(managed, context=self.get_serializer_context()).data,
            status=201,
        )

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        pipeline = self.get_object()
        version = int(
            request.data.get("version") or pipeline.current_version_number or 1
        )
        inputs = dict(request.data.get("inputs") or {})
        execution_class = request.data.get("execution_class") or "default"
        run = _control_service().submit_run(
            pipeline_id=UUID(str(pipeline.id)),
            pipeline_version=version,
            inputs=inputs,
            execution_class=execution_class,
            run_id=uuid4(),
            actor=_actor(request),
        )
        instance = models.ExecutionRun.objects.get(pk=str(run.id))
        return Response(
            ExecutionRunSerializer(instance, context=self.get_serializer_context()).data,
            status=201,
        )


class PipelineVersionViewSet(ControlPlaneViewSet):
    queryset = models.PipelineVersion.objects.all()
    serializer_class = PipelineVersionSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        "list": "list",
        "retrieve": "get",
        "create": "create",
    }


class ExecutionRunViewSet(ControlPlaneViewSet):
    queryset = models.ExecutionRun.objects.all()
    serializer_class = ExecutionRunSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        "list": "list",
        "retrieve": "get",
        "cancel": "cancel",
        "retry": "retry",
    }
    elevated_actions = frozenset({"cancel", "retry"})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        run = self.get_object()
        reason = str(request.data.get("reason") or "cancelled via API")
        updated = _control_service().cancel_run(
            UUID(str(run.run_id)), reason, actor=_actor(request)
        )
        instance = models.ExecutionRun.objects.get(pk=str(updated.id))
        return Response(
            ExecutionRunSerializer(instance, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        run = self.get_object()
        updated = _control_service().retry_run(
            UUID(str(run.run_id)), actor=_actor(request)
        )
        instance = models.ExecutionRun.objects.get(pk=str(updated.id))
        return Response(
            ExecutionRunSerializer(instance, context=self.get_serializer_context()).data,
            status=201,
        )


class ExecutionStepViewSet(ControlPlaneViewSet):
    queryset = models.ExecutionStep.objects.all()
    serializer_class = ExecutionStepSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        "list": "list",
        "retrieve": "get",
    }


class WorkerViewSet(ControlPlaneViewSet):
    queryset = models.Worker.objects.all()
    serializer_class = WorkerSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        "list": "list",
        "retrieve": "get",
        "disable": "disable",
    }
    elevated_actions = frozenset({"disable"})

    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        worker = self.get_object()
        updated = _control_service().disable_worker(
            UUID(str(worker.worker_id)), actor=_actor(request)
        )
        instance = models.Worker.objects.get(pk=str(updated.id))
        return Response(
            WorkerSerializer(instance, context=self.get_serializer_context()).data
        )


class ScheduleViewSet(ControlPlaneViewSet):
    queryset = models.Schedule.objects.all()
    serializer_class = ScheduleSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        **_CRUD_ACTIONS,
        "pause": "pause",
        "resume": "resume",
    }
    elevated_actions = frozenset(
        {"create", "update", "partial_update", "destroy", "pause", "resume"}
    )

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        schedule = self.get_object()
        updated = _control_service().pause_schedule(
            UUID(str(schedule.id)), actor=_actor(request)
        )
        instance = models.Schedule.objects.get(pk=str(updated.id))
        return Response(
            ScheduleSerializer(instance, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        schedule = self.get_object()
        updated = _control_service().resume_schedule(
            UUID(str(schedule.id)), actor=_actor(request)
        )
        instance = models.Schedule.objects.get(pk=str(updated.id))
        return Response(
            ScheduleSerializer(instance, context=self.get_serializer_context()).data
        )


class CrawledURLViewSet(ControlPlaneViewSet):
    queryset = models.CrawledURL.objects.all()
    serializer_class = CrawledURLSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        "list": "list",
        "retrieve": "get",
    }


class ArchiveRecordViewSet(ControlPlaneViewSet):
    queryset = models.ArchiveRecord.objects.all()
    serializer_class = ArchiveRecordSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        "list": "list",
        "retrieve": "get",
    }


class CheckpointViewSet(ControlPlaneViewSet):
    queryset = models.Checkpoint.objects.all()
    serializer_class = CheckpointSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        "list": "list",
        "retrieve": "get",
        "destroy": "delete",
    }


class DeadLetterViewSet(ControlPlaneViewSet):
    queryset = models.DeadLetter.objects.all()
    serializer_class = DeadLetterSerializer
    advertised_actions: ClassVar[dict[str, str]] = {
        "list": "list",
        "retrieve": "get",
        "retry": "retry",
        "discard": "discard",
    }
    elevated_actions = frozenset({"retry", "discard"})
    confirmed_actions = frozenset({"discard"})

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        dead = self.get_object()
        keep_original = bool(request.data.get("keep_original", True))
        run = _control_service().replay_dead_letter(
            UUID(str(dead.id)),
            keep_original=keep_original,
            actor=_actor(request),
        )
        instance = models.ExecutionRun.objects.get(pk=str(run.id))
        return Response(
            ExecutionRunSerializer(instance, context=self.get_serializer_context()).data,
            status=201,
        )

    @action(detail=True, methods=["post"])
    def discard(self, request, pk=None):
        dead = self.get_object()
        _audit(dead, "discard", request)
        discarded = _control_service().discard_dead_letter(
            UUID(str(dead.id)), actor=_actor(request)
        )
        return Response({"discarded": discarded})
