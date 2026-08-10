"""Django admin registrations for the Mirror control plane.

Admin mutations call :class:`DjangoControlService` (which delegates to
:class:`mirror_control.ControlService`) instead of ``Model.save()`` directly,
so Django never bypasses Mirror semantics. Read-only list/detail views use the
unmanaged models for efficient admin rendering.
"""

from __future__ import annotations

from typing import Any, cast

try:
    from django.contrib import admin
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError("The Django control-plane interface requires Django. Install it with: pip install 'mirror-control-django[django]'") from exc

from mirror_control.service import content_hash

from mirror_control_django import models
from mirror_control_django.forms import PipelineVersionForm
from mirror_control_django.service import DjangoControlService

READONLY_FIELDS = ("id", "created_at", "updated_at")


def _model_values(obj: Any) -> dict[str, Any]:
    """Return the model's concrete field values as a plain mapping."""

    values: dict[str, Any] = {}
    for field in obj._meta.concrete_fields:
        values[field.name] = field.value_from_object(obj)
    return values


class _ServiceWriteAdmin(admin.ModelAdmin):
    """Base admin whose save/delete delegate to the control service."""

    entity_name: str
    readonly_fields: tuple[str, ...] = READONLY_FIELDS

    def save_model(self, request: Any, obj: Any, form: Any, change: bool) -> None:
        service = DjangoControlService()
        if change:
            service.update_entity(self.entity_name, obj.pk, _model_values(obj))
        else:
            service.create_entity(self.entity_name, _model_values(obj))

    def delete_model(self, request: Any, obj: Any) -> None:
        service = DjangoControlService()
        service.delete_entity(self.entity_name, obj.pk)


@admin.register(models.Project)
class ProjectAdmin(_ServiceWriteAdmin):
    entity_name = "project"
    list_display = ("slug", "name", "status", "created_at", "updated_at")
    search_fields = ("slug", "name")
    list_filter = ("status",)


@admin.register(models.Pipeline)
class PipelineAdmin(_ServiceWriteAdmin):
    entity_name = "pipeline"
    list_display = (
        "project_id",
        "slug",
        "name",
        "origin",
        "is_read_only",
        "current_version_number",
        "updated_at",
    )
    list_filter = ("origin", "is_read_only")
    search_fields = ("slug", "name", "source_ref")
    readonly_fields = READONLY_FIELDS + ("definition_ref", "current_version_hash")


@admin.register(models.PipelineVersion)
class PipelineVersionAdmin(admin.ModelAdmin):
    form = PipelineVersionForm
    list_display = (
        "pipeline_id",
        "version",
        "definition_hash",
        "definition_format",
        "created_at",
    )
    list_filter = ("definition_format",)
    search_fields = ("definition_ref", "definition_hash")
    readonly_fields = READONLY_FIELDS + ("definition_hash", "definition_ref")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # Add-only path: write the blob and record a new immutable version
        # through the service, never through Django's ORM.
        service = DjangoControlService()
        definition_text = form.cleaned_data.get("definition_text", "")
        payload = definition_text.encode("utf-8")
        blob_store = service.service.blob_store
        if not obj.definition_ref:
            pipeline = models.Pipeline.objects.get(pk=obj.pipeline_id)
            project = models.Project.objects.get(pk=pipeline.project_id)
            obj.definition_ref = f"pipelines/{project.slug}/{pipeline.slug}/v{obj.version}.json"
        blob_store.put_bytes(obj.definition_ref, payload)
        obj.definition_hash = content_hash(payload)
        obj.definition_format = "json"
        version = cast(Any, service.create_entity("pipeline-version", _model_values(obj)))
        service.update_entity(
            "pipeline",
            obj.pipeline_id,
            {
                "definition_ref": version.definition_ref,
                "current_version_number": version.version,
                "current_version_hash": version.definition_hash,
            },
        )


@admin.register(models.ExecutionRun)
class ExecutionRunAdmin(_ServiceWriteAdmin):
    entity_name = "execution_run"
    list_display = (
        "run_id",
        "pipeline_id",
        "pipeline_version",
        "status",
        "worker_id",
        "created_at",
    )
    list_filter = ("status", "execution_class")
    search_fields = ("run_id", "pipeline_id", "worker_id")


@admin.register(models.ExecutionStep)
class ExecutionStepAdmin(admin.ModelAdmin):
    """Execution steps are immutable records; the admin is read-only."""

    list_display = ("run_id", "step_id", "capability", "provider", "status", "created_at")
    list_filter = ("status", "capability")
    search_fields = ("step_id", "capability", "provider")
    readonly_fields = READONLY_FIELDS + (
        "run_id",
        "step_id",
        "capability",
        "provider",
        "status",
        "inputs",
        "error",
        "retry_count",
        "started_at",
        "finished_at",
        "metadata",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Worker)
class WorkerAdmin(_ServiceWriteAdmin):
    entity_name = "worker"
    list_display = ("worker_id", "backend", "execution_class", "status", "heartbeat_at")
    list_filter = ("status", "backend", "execution_class")
    search_fields = ("worker_id",)


@admin.register(models.Schedule)
class ScheduleAdmin(_ServiceWriteAdmin):
    entity_name = "schedule"
    list_display = ("name", "pipeline_id", "cron", "enabled", "status", "next_run_at")
    list_filter = ("enabled", "status")
    search_fields = ("name", "cron")


@admin.register(models.CrawledURL)
class CrawledURLAdmin(admin.ModelAdmin):
    """Crawled URLs are produced by the Crawl capability; the admin is read-only."""

    list_display = ("url", "status", "pipeline_id", "run_id", "discovered_at")
    list_filter = ("status",)
    search_fields = ("url",)
    readonly_fields = READONLY_FIELDS + (
        "pipeline_id",
        "run_id",
        "url",
        "status",
        "discovered_at",
        "crawled_at",
        "error",
        "metadata",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.ArchiveRecord)
class ArchiveRecordAdmin(admin.ModelAdmin):
    """Archive records are produced by Archive; the admin is read-only."""

    list_display = ("resource_key", "storage_ref", "content_type", "pipeline_id", "created_at")
    search_fields = ("resource_key", "storage_ref")
    readonly_fields = READONLY_FIELDS + (
        "pipeline_id",
        "run_id",
        "resource_key",
        "storage_ref",
        "content_hash",
        "content_type",
        "content_length",
        "metadata",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Checkpoint)
class CheckpointAdmin(admin.ModelAdmin):
    """Checkpoints are produced by execution; the admin is read-only."""

    list_display = ("run_id", "step_id", "created_at")
    search_fields = ("run_id", "step_id")
    readonly_fields = READONLY_FIELDS + ("run_id", "step_id", "payload", "metadata")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.DeadLetter)
class DeadLetterAdmin(admin.ModelAdmin):
    """Dead letters are terminal records; replay/discard go through the service."""

    list_display = (
        "run_id",
        "pipeline_id",
        "step_id",
        "terminal_status",
        "retry_count",
        "created_at",
    )
    list_filter = ("terminal_status",)
    search_fields = ("run_id", "pipeline_id", "step_id", "reason")
    readonly_fields = READONLY_FIELDS + (
        "run_id",
        "pipeline_id",
        "step_id",
        "terminal_status",
        "reason",
        "original_inputs",
        "policy_state",
        "provenance",
        "retry_count",
        "metadata",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# The dashboard surface is Django Admin branded as the Mirror control plane.
admin.site.site_header = "Mirror Control Plane"
admin.site.site_title = "Mirror Control Plane"
admin.site.index_title = "Mirror Control Plane"

# Public interface entry point used by the control-plane manifest.
admin_site = admin.site
