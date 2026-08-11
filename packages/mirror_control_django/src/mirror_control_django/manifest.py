"""Django control-plane interface manifest.

The framework-neutral control-plane catalog lives in ``mirror_control`` and is
shared by every interface. This module re-exports it and adds the Django
Admin-specific :class:`InterfaceManifest` entry point.
"""

from __future__ import annotations

from mirror_control.manifest import (
    CONTROL_PLANE_MANIFEST,
    ControlPlaneEntitySpec,
    ControlPlaneManifest,
    control_plane_manifest,
)
from mirror_core.extensions.models import InterfaceManifest

__all__ = [
    "CONTROL_PLANE_MANIFEST",
    "ControlPlaneEntitySpec",
    "ControlPlaneManifest",
    "control_plane_manifest",
    "interface",
]


interface = InterfaceManifest(
    name="dashboard",
    version="1.0.0",
    package_name="mirror-control-django",
    api_version="1.0",
    requires_core=">=0.1.0",
    settings_model=None,
    interface_type="dashboard",
    factory="mirror_control_django.admin:admin_site",
    requires_capabilities=[],
    metadata={
        "description": "Django Admin control-plane interface for Mirror metadata, pipelines, executions, workers, schedules, checkpoints, and dead letters.",
    },
)
