"""Django admin registrations for the Mirror control plane."""

from __future__ import annotations

try:
    from django.contrib import admin
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "The Django control-plane interface requires Django. "
        "Install it with: pip install 'mirror-control-django[django]'"
    ) from exc

from mirror_control_django import models
from mirror_control_django.forms import PipelineVersionForm
from mirror_control_django.repository import ControlPlaneRepository, content_hash


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "created_at", "updated_at")
    search_fields = ("slug", "name")
    list_filter = ("created_at",)


@admin.register(models.Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "slug",
        "name",
        "origin",
        "is_read_only",
        "current_version_number",
        "updated_at",
    )
    list_filter = ("origin", "is_read_only", "project")
    search_fields = ("slug", "name", "source_ref")
    readonly_fields = ("definition_ref", "current_version_hash")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.is_read_only:
            fields.extend(
                [
                    "project",
                    "slug",
                    "name",
                    "origin",
                    "source_ref",
                    "source_hash",
                    "metadata",
                ]
            )
        return tuple(dict.fromkeys(fields))


@admin.register(models.PipelineVersion)
class PipelineVersionAdmin(admin.ModelAdmin):
    form = PipelineVersionForm
    list_display = (
        "pipeline",
        "version",
        "definition_hash",
        "definition_format",
        "created_at",
    )
    list_filter = ("definition_format", "pipeline")
    search_fields = ("pipeline__slug", "definition_ref", "definition_hash")
    readonly_fields = ("definition_hash", "definition_ref")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        repo = ControlPlaneRepository()
        if not change:
            latest = obj.pipeline.versions.order_by("-version").first()
            obj.version = 1 if latest is None else latest.version + 1
        definition_text = form.cleaned_data.get("definition_text", "")
        payload = definition_text.encode("utf-8")
        if not obj.definition_ref:
            obj.definition_ref = repo._definition_blob_key(
                obj.pipeline.project.slug, obj.pipeline.slug, obj.version
            )
        repo.blob_store.put_bytes(obj.definition_ref, payload)
        obj.definition_hash = content_hash(payload)
        obj.definition_format = "json"
        super().save_model(request, obj, form, change)
        obj.pipeline.definition_ref = obj.definition_ref
        obj.pipeline.current_version_number = obj.version
        obj.pipeline.current_version_hash = obj.definition_hash
        obj.pipeline.save(
            update_fields=[
                "definition_ref",
                "current_version_number",
                "current_version_hash",
                "updated_at",
            ]
        )


@admin.register(models.ExecutionRun)
class ExecutionRunAdmin(admin.ModelAdmin):
    list_display = (
        "run_id",
        "pipeline_name",
        "pipeline_version",
        "status",
        "worker_id",
        "created_at",
    )
    list_filter = ("status", "execution_class")
    search_fields = ("run_id", "pipeline_name", "worker_id")


@admin.register(models.ExecutionStep)
class ExecutionStepAdmin(admin.ModelAdmin):
    list_display = ("run", "step_id", "capability", "provider", "status", "created_at")
    list_filter = ("status", "capability")
    search_fields = ("run__run_id", "step_id", "capability", "provider")


@admin.register(models.Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ("worker_id", "backend", "execution_class", "status", "heartbeat_at")
    list_filter = ("status", "backend", "execution_class")
    search_fields = ("worker_id",)


@admin.register(models.Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "pipeline", "cron", "enabled", "next_run_at")
    list_filter = ("enabled", "pipeline")
    search_fields = ("name", "cron")


@admin.register(models.CrawledURL)
class CrawledURLAdmin(admin.ModelAdmin):
    list_display = ("url", "status", "pipeline", "run_id", "discovered_at")
    list_filter = ("status",)
    search_fields = ("url",)


@admin.register(models.ArchiveRecord)
class ArchiveRecordAdmin(admin.ModelAdmin):
    list_display = ("resource_key", "storage_ref", "pipeline", "run_id", "created_at")
    search_fields = ("resource_key", "storage_ref")


@admin.register(models.Checkpoint)
class CheckpointAdmin(admin.ModelAdmin):
    list_display = ("run_id", "step_id", "created_at")
    search_fields = ("run_id", "step_id")


@admin.register(models.DeadLetter)
class DeadLetterAdmin(admin.ModelAdmin):
    list_display = (
        "run_id",
        "pipeline_name",
        "step_id",
        "terminal_status",
        "retry_count",
        "created_at",
    )
    list_filter = ("terminal_status",)
    search_fields = ("run_id", "pipeline_name", "step_id", "reason")


# The dashboard surface is Django Admin branded as the Mirror control plane.
admin.site.site_header = "Mirror Control Plane"
admin.site.site_title = "Mirror Control Plane"
admin.site.index_title = "Mirror Control Plane"

# Public interface entry point used by the control-plane manifest.
admin_site = admin.site
