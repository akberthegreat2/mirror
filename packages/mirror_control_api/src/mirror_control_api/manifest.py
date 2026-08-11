"""Manifest for the Mirror REST control-plane interface."""

from mirror_core.extensions.models import InterfaceManifest

interface = InterfaceManifest(
    name="rest",
    version="0.1.0",
    package_name="mirror-control-api",
    api_version="1.0",
    requires_core=">=0.1.0",
    settings_model=None,
    interface_type="api",
    factory="mirror_control_api.views:ManifestViewSet",
    requires_capabilities=[],
    metadata={"description": "Django REST Framework control-plane API for Mirror metadata and pipeline operations."},
)

__all__ = ["interface"]
