"""Fail-closed permissions for the Mirror control-plane REST API.

The control plane is an administrative surface (ADR-0045). These permissions
are safe by default: every view requires an authenticated user, mutating and
destructive actions require an elevated (staff) account, and object access is
isolated to the projects a user can reach. Hosts may relax the defaults only
by setting ``MIRROR_CONTROL_OPEN_API = True`` explicitly.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.conf import settings
from mirror_control_django import models
from rest_framework.permissions import BasePermission


def open_api_enabled(request: Any) -> bool:
    """Return True only when the host explicitly opted out of fail-closed."""

    return getattr(settings, "MIRROR_CONTROL_OPEN_API", False)


def accessible_project_ids(user: Any) -> frozenset[str]:
    """Project IDs a non-staff user may reach, via ``user.mirror_projects``.

    ``mirror_projects`` is a hook for the host's swappable user model: a
    collection of project slugs. Staff accounts bypass this and reach every
    project. When the user has no such hook, they can reach no projects.
    """

    slugs = getattr(user, "mirror_projects", None)
    if not slugs:
        return frozenset()
    return frozenset(
        str(pk)
        for pk in models.Project.objects.filter(slug__in=list(slugs)).values_list(
            "pk", flat=True
        )
    )


def _request_confirmed(request: Any) -> bool:
    confirmed = None
    try:
        confirmed = request.data.get("confirm")
    except AttributeError:
        pass
    if confirmed is None:
        confirmed = request.query_params.get("confirm")
    return confirmed is True or str(confirmed).lower() in ("true", "1")


class ControlPlaneAuthenticated(BasePermission):
    """Require an authenticated user unless the host opened the API."""

    message = "The Mirror control plane requires authentication."

    def has_permission(self, request: Any, view: Any) -> bool:
        if open_api_enabled(request):
            return True
        user = request.user
        return bool(user and user.is_authenticated)


class ControlPlaneElevated(BasePermission):
    """Mutating and destructive actions require an elevated (staff) account."""

    message = "Control-plane mutations require a staff account."

    def has_permission(self, request: Any, view: Any) -> bool:
        if open_api_enabled(request):
            return True
        user = request.user
        return bool(
            user and user.is_authenticated and (user.is_staff or user.is_superuser)
        )


class ControlPlaneDestroy(BasePermission):
    """Destructive actions require elevation and an explicit confirmation."""

    message = "Destructive actions require a staff account and confirm=true."

    def has_permission(self, request: Any, view: Any) -> bool:
        if open_api_enabled(request):
            return True
        user = request.user
        if not (user and user.is_authenticated and (user.is_staff or user.is_superuser)):
            return False
        return _request_confirmed(request)


class ControlPlaneObjectAccess(BasePermission):
    """Object-level project isolation for non-staff users."""

    message = "You do not have access to this entity's project."

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        if open_api_enabled(request):
            return True
        user = request.user
        if user.is_superuser or user.is_staff:
            return True
        allowed = accessible_project_ids(user)
        if not allowed:
            return False
        project_id = object_project_id(obj)
        return project_id is not None and project_id in allowed


def object_project_id(obj: Any) -> str | None:
    """Resolve the owning project for any control-plane entity.

    Workers are global administrative resources with no project, so they
    resolve to ``None`` and are therefore unreachable by non-staff users.
    """

    if isinstance(obj, models.Project):
        return str(obj.pk)
    if isinstance(obj, models.Pipeline):
        return str(obj.project_id)
    if isinstance(obj, models.PipelineVersion):
        pipeline = models.Pipeline.objects.filter(pk=obj.pipeline_id).first()
        return None if pipeline is None else str(pipeline.project_id)
    if isinstance(obj, models.ExecutionRun):
        pipeline = models.Pipeline.objects.filter(pk=obj.pipeline_id).first()
        return None if pipeline is None else str(pipeline.project_id)
    if isinstance(obj, models.ExecutionStep):
        run = models.ExecutionRun.objects.filter(pk=obj.run_id).first()
        pipeline = (
            models.Pipeline.objects.filter(pk=run.pipeline_id).first() if run else None
        )
        return None if pipeline is None else str(pipeline.project_id)
    if isinstance(obj, models.Schedule):
        pipeline = models.Pipeline.objects.filter(pk=obj.pipeline_id).first()
        return None if pipeline is None else str(pipeline.project_id)
    if isinstance(obj, models.CrawledURL):
        if not obj.pipeline_id:
            return None
        pipeline = models.Pipeline.objects.filter(pk=obj.pipeline_id).first()
        return None if pipeline is None else str(pipeline.project_id)
    if isinstance(obj, models.ArchiveRecord):
        if not obj.pipeline_id:
            return None
        pipeline = models.Pipeline.objects.filter(pk=obj.pipeline_id).first()
        return None if pipeline is None else str(pipeline.project_id)
    if isinstance(obj, models.Checkpoint):
        run = models.ExecutionRun.objects.filter(pk=obj.run_id).first()
        pipeline = (
            models.Pipeline.objects.filter(pk=run.pipeline_id).first() if run else None
        )
        return None if pipeline is None else str(pipeline.project_id)
    if isinstance(obj, models.DeadLetter):
        if not obj.pipeline_id:
            return None
        pipeline = models.Pipeline.objects.filter(pk=obj.pipeline_id).first()
        return None if pipeline is None else str(pipeline.project_id)
    return None


def isolate_queryset(qs: Any, model: Any, allowed: Iterable[str]) -> Any:
    """Filter a queryset down to entities within the accessible projects."""

    allowed_ids = frozenset(allowed)
    if model is models.Project:
        return qs.filter(pk__in=allowed_ids)
    if hasattr(model, "project_id"):
        return qs.filter(project_id__in=allowed_ids)
    pipeline_pks = list(
        models.Pipeline.objects.filter(project_id__in=allowed_ids).values_list(
            "pk", flat=True
        )
    )
    if hasattr(model, "pipeline_id"):
        if not pipeline_pks:
            return qs.none()
        return qs.filter(pipeline_id__in=pipeline_pks)
    if hasattr(model, "run_id"):
        run_pks = list(
            models.ExecutionRun.objects.filter(pipeline_id__in=pipeline_pks).values_list(
                "pk", flat=True
            )
        )
        if not run_pks:
            return qs.none()
        return qs.filter(run_id__in=run_pks)
    return qs.none()


__all__ = [
    "ControlPlaneAuthenticated",
    "ControlPlaneDestroy",
    "ControlPlaneElevated",
    "ControlPlaneObjectAccess",
    "accessible_project_ids",
    "isolate_queryset",
    "object_project_id",
    "open_api_enabled",
]
